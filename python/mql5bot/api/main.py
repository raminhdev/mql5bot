"""Operator UI/API (mission §57-§59/§78/§80): FastAPI + Jinja2 +
HTMX.  NO React.  Every promotion goes through an EXPLICIT approval
button carrying actor + reason; the UI can never mark a strategy LIVE
(§73: enforced by source-scan test) and can never skip lifecycle
stages — it may only request the NEXT legal transition, which the
factory store re-validates server-side (state machine + evidence
gates + human approval).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

from ..discovery.safety import AllocationCircuitBreaker, KillSwitch
from ..factory.store import FactoryStore, StoreError

TEMPLATES_DIR = Path(__file__).parent / "templates"

KANBAN_COLUMNS = ("Inbox", "PARSED", "VALIDATED", "BACKTESTED",
                  "ROBUSTNESS_PASS", "OOS_SURVIVOR", "SHADOW", "DEMO",
                  "LIVE_SMALL", "LIVE", "RETIRED", "REJECTED")

# §73/§59: the UI may request at most the NEXT transition, and only
# the human-approval-gated ones are surfaced as buttons.  LIVE is
# deliberately absent — live activation is owner-only (MT5 phase).
UI_PROPOSABLE = {"SHADOW": "DEMO", "DEMO": "LIVE_SMALL"}


class SafetyHub:
    """Process-wide safety singletons exposed to routes (the kill
    switch itself stays independent — the UI only views/resets it)."""

    def __init__(self, kill_switch: KillSwitch,
                 breaker: AllocationCircuitBreaker):
        self.kill_switch = kill_switch
        self.breaker = breaker
        self.watchdog_alerts: list[dict] = []


def create_app(store: FactoryStore, safety: SafetyHub | None = None,
               *, score_fn: Callable[[str], dict] | None = None
               ) -> FastAPI:
    app = FastAPI(title="AEGIS Governance Console", version="1.0")
    env = Environment(autoescape=True,
                      loader=FileSystemLoader(str(TEMPLATES_DIR)))
    templates = Jinja2Templates(env=env)
    safety = safety or SafetyHub(KillSwitch(), AllocationCircuitBreaker())

    def _strategy_rows() -> list[dict]:
        rows = []
        for s in store.list_strategies():
            rows.append({
                "strategy_id": s["strategy_id"], "state": s["state"],
                "version": s.get("version"),
                "score": score_fn(s["strategy_id"]) if score_fn
                else None})
        return rows

    @app.get("/", response_class=HTMLResponse)
    def board(request: Request):
        rows = _strategy_rows()
        columns = []
        for col in KANBAN_COLUMNS:
            cards = [r for r in rows
                     if (col == "Inbox" and r["state"] == "DRAFT")
                     or r["state"] == col]
            columns.append({"name": col, "cards": cards})
        ks = safety.kill_switch
        return templates.TemplateResponse(request, "board.html", {
            "columns": columns,
            "kill_switch": ks.state.value,
            "kill_reason": ks.reason,
            "breaker_frozen": safety.breaker.st.frozen,
            "alerts": safety.watchdog_alerts[-10:],
        })

    @app.get("/strategies/{sid}", response_class=HTMLResponse)
    def strategy_detail(request: Request, sid: str):
        try:
            state = store.current_state(sid)
        except StoreError:
            raise HTTPException(404, "unknown strategy") from None
        history = [{"from": e.from_state, "to": e.to_state,
                    "kind": e.kind, "actor": e.actor,
                    "reason": e.reason, "ts": str(e.created_at)}
                   for e in store.history(sid)]
        proposable = UI_PROPOSABLE.get(state)
        return templates.TemplateResponse(request, "strategy.html", {
            "sid": sid, "state": state, "history": history,
            "proposable": proposable,
            "score": score_fn(sid) if score_fn else None,
            "error": None})

    @app.post("/approvals")
    def approve(sid: str = Form(...), decision: str = Form(...),
                actor: str = Form(...), reason: str = Form(...),
                evidence: str = Form(""), version: int = Form(0)):
        """§32 structured approval.  The UI NEVER targets LIVE (§73)
        and never skips stages: the target must be the UI-proposable
        next state, and store.transition re-validates the state
        machine, the evidence binding and the human-approval flag."""
        try:
            state = store.current_state(sid)
        except StoreError:
            raise HTTPException(404, "unknown strategy") from None
        target = UI_PROPOSABLE.get(state or "")
        if target is None:
            raise HTTPException(409, f"no UI-proposable transition from "
                                     f"{state!r}")
        if target == "LIVE" or decision not in ("APPROVED", "DENIED"):
            raise HTTPException(422, "invalid decision target")
        if not reason.strip() or not actor.strip():
            raise HTTPException(422, "approval requires actor + reason")
        version_no = version or _current_version(store, sid)
        refs = tuple(r.strip() for r in evidence.split(",") if r.strip())
        if decision == "DENIED":
            # a denial is recorded as an oversight event, never a state
            # change: refusals must be visible without mutating status
            store.alert("APPROVAL_DENIED", severity="INFO",
                        strategy_id=sid, message=f"{actor}: {reason}")
            return RedirectResponse(f"/strategies/{sid}", status_code=303)
        try:
            store.transition(sid, version_no, target, evidence_refs=refs,
                             actor=f"ui:{actor}", reason=reason,
                             human_approval=True)
        except StoreError as exc:
            raise HTTPException(409, str(exc)) from exc
        return RedirectResponse(f"/strategies/{sid}", status_code=303)

    @app.get("/safety", response_class=HTMLResponse)
    def safety_page(request: Request):
        ks = safety.kill_switch
        return templates.TemplateResponse(request, "safety.html", {
            "kill_switch": ks.state.value, "kill_reason": ks.reason,
            "kill_history": ks.history[-20:],
            "breaker_frozen": safety.breaker.st.frozen,
            "breaker_reason": safety.breaker.st.last_reason,
            "alerts": safety.watchdog_alerts[-20:]})

    @app.post("/safety/killswitch/reset")
    def killswitch_reset(actor: str = Form(...),
                         reason: str = Form(...)):
        """§42: explicit, audited reset — the ONLY path out of
        EMERGENCY_HALT; requires actor + reason."""
        if not actor.strip() or not reason.strip():
            raise HTTPException(422, "reset requires actor + reason")
        safety.kill_switch.explicit_reset(actor, reason)
        return RedirectResponse("/safety", status_code=303)

    return app


def _current_version(store: FactoryStore, sid: str) -> int:
    with store.session() as sess:
        from ..factory.models import StrategyVersion
        row = (sess.query(StrategyVersion)
               .filter_by(strategy_id=sid)
               .order_by(StrategyVersion.version.desc()).first())
        return row.version if row else 0


__all__ = ["KANBAN_COLUMNS", "SafetyHub", "create_app"]
