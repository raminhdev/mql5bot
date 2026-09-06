"""Portfolio assembly — correlation-aware, concentration-capped, with
legitimate zero exposure (mission §38-§40/§66).

Gross exposure is a TARGET (10-20% by default) — never a minimum; the
portfolio is allowed to hold 0% when nothing qualifies or safety
demands it.  Risk% (portfolio heat) and gross% are DIFFERENT
quantities and never conflated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CandidatePortfolioEntry:
    strategy_id: str
    symbol: str
    direction: str                     # long|short|both
    asset_class: str                   # fx|metal|index|crypto|other
    weight: float                      # normalized weight [0, 1]
    score: float                       # discovery score
    returns: tuple[float, ...] = ()    # aligned daily returns (or None)
    correlation_penalty: float = 0.0
    marginal_heat: float = 0.0


def _same_dir(a: str, b: str) -> bool:
    """Opposite pure directions never share direction heat."""
    if a == "short" or b == "short":
        return a == b
    return True


def correlation(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    if len(a) != len(b) or len(a) < 3:
        return 1.0                     # unknown → assume worst
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    da = [x - ma for x in a]
    db = [x - mb for x in b]
    num = sum(x * y for x, y in zip(da, db))
    den = math.sqrt(sum(x * x for x in da) * sum(y * y for y in db))
    if den <= 1e-12:
        return 1.0
    rho = num / den
    return max(-1.0, min(1.0, rho))


@dataclass
class ConcentrationLimits:
    max_per_strategy_pct: float = 30.0
    max_per_symbol_pct: float = 40.0
    max_per_direction_pct: float = 65.0
    max_per_asset_class_pct: float = 60.0
    max_corr_avg: float = 0.70          # avg pairwise correlation cap
    corr_penalty_strength: float = 0.5
    redundant_corr: float = 0.95        # hard near-duplicate threshold

    def validate(self) -> None:
        for v in (self.max_per_strategy_pct, self.max_per_symbol_pct,
                  self.max_per_direction_pct, self.max_per_asset_class_pct):
            if not 0 < v <= 100:
                raise ValueError("concentration caps must be in (0,100]")
        if not 0 <= self.max_corr_avg <= 1:
            raise ValueError("correlation cap must be within [0,1]")


def _corr_penalty(entry: CandidatePortfolioEntry,
                  selected: list[CandidatePortfolioEntry],
                  strength: float) -> float:
    if not selected or not entry.returns:
        return 0.0
    rhos = []
    for s in selected:
        if s.returns and len(s.returns) == len(entry.returns):
            rhos.append(abs(correlation(entry.returns, s.returns)))
    if not rhos:
        return 0.0
    return strength * (sum(rhos) / len(rhos))


def build_portfolio(candidates: list[dict], *,
                    capital_gross_target_pct: float = 15.0,
                    limits: ConcentrationLimits | None = None,
                    min_score: float = 0.45,
                    max_positions: int = 8) -> dict:
    """Greedy correlation-aware assembly (deterministic: sort by
    (score desc, strategy_id)).  Candidates must already be
    stage-eligible (§29); scores rank, they never authorize."""
    limits = limits or ConcentrationLimits()
    limits.validate()
    target_frac = max(0.0, min(1.0, capital_gross_target_pct / 100.0))
    ranked = sorted((c for c in candidates
                     if float(c.get("score", 0.0)) >= min_score),
                    key=lambda c: (-float(c.get("score", 0.0)),
                                   str(c.get("strategy_id", ""))))
    selected: list[CandidatePortfolioEntry] = []
    excluded: list[tuple[str, str]] = []
    total_w = 0.0
    for c in ranked:
        if len(selected) >= max_positions:
            break
        sid = str(c["strategy_id"])
        w = float(c.get("weight", 1.0))
        entry = CandidatePortfolioEntry(
            strategy_id=sid, symbol=str(c.get("symbol", "?")),
            direction=str(c.get("direction", "both")),
            asset_class=str(c.get("asset_class", "other")),
            weight=w, score=float(c.get("score", 0.0)),
            returns=tuple(c.get("returns", ())))
        pen = _corr_penalty(entry, selected, limits.corr_penalty_strength)
        # hard near-duplicate rule (§64): lower-ranked clone excluded
        if selected and entry.returns:
            rhos = [abs(correlation(entry.returns, s.returns))
                    for s in selected if s.returns
                    and len(s.returns) == len(entry.returns)]
            if rhos and max(rhos) >= limits.redundant_corr:
                excluded.append((sid, (f"redundant: corr "
                                       f"{max(rhos):.3f} >= "
                                       f"{limits.redundant_corr}")))
                continue
        adj = entry.score - pen
        if adj < min_score and selected:
            excluded.append((sid, (f"correlation penalty {pen:.3f} "
                                   f"dropped score to {adj:.3f}")))
            continue
        # concentration checks vs CURRENT selection — shares are the
        # SCALED exposure (% of capital after gross-target scaling)
        tentative = total_w + entry.weight
        if tentative <= 0:
            excluded.append((sid, "non-positive weight"))
            continue

        sym, direc, cls = entry.symbol, entry.direction, entry.asset_class

        def _pct(pred, *, sym=sym, direc=direc, cls=cls,
                 new_weight=entry.weight, tot=tentative):
            base = sum(e.weight for e in selected if pred(e))
            return (base + new_weight) / tot * target_frac * 100

        if _pct(lambda e, sym=sym: True) > limits.max_per_strategy_pct:
            excluded.append((sid, "per-strategy cap"))
            continue
        if _pct(lambda e, sym=sym: e.symbol == sym) > \
                limits.max_per_symbol_pct:
            excluded.append((sid, "per-symbol cap"))
            continue
        if _pct(lambda e, direc=direc: _same_dir(e.direction, direc)) > \
                limits.max_per_direction_pct:
            excluded.append((sid, "per-direction cap"))
            continue
        if _pct(lambda e, cls=cls: e.asset_class == cls) > \
                limits.max_per_asset_class_pct:
            excluded.append((sid, "per-asset-class cap"))
            continue
        selected.append(entry)
        total_w += entry.weight
    # normalize weights into the gross target
    target_frac = max(0.0, min(1.0, capital_gross_target_pct / 100.0))
    scale = target_frac / total_w if total_w > 0 else 0.0
    portfolio = []
    for e in selected:
        portfolio.append({
            "strategy_id": e.strategy_id, "weight": round(e.weight, 6),
            "scaled_weight": round(e.weight * scale, 6),
            "score": round(e.score, 6),
            "correlation_penalty": round(
                _corr_penalty(e, [x for x in selected if x is not e],
                              limits.corr_penalty_strength), 6),
        })
    gross_pct = round(target_frac * 100 if total_w > 0 else 0.0, 4)
    heat = round(sum(p["scaled_weight"] * p["score"] for p in portfolio), 6)
    return {
        "gross_exposure_pct": gross_pct,   # §40: 0% is legitimate
        "portfolio_heat": heat,            # ≠ gross (§40)
        "positions": portfolio,
        "excluded": excluded,
        "zero_exposure": total_w == 0.0,
    }


def marginal_contribution(candidates: list[dict], new_candidate: dict,
                          *, base: dict | None = None) -> dict:
    """§39 marginal analysis: what does adding this candidate do to the
    portfolio (incremental score/heat/correlation)?"""
    base = base or build_portfolio(candidates)
    with_new = build_portfolio(
        candidates + [dict(new_candidate, strategy_id=new_candidate[
            "strategy_id"] + "__cand")],
        capital_gross_target_pct=base.get("gross_exposure_pct", 15.0))
    extra = [p for p in with_new["positions"]
             if str(p["strategy_id"]).endswith("__cand")]
    if not extra:
        return {"admitted": False, "reason": "did not survive portfolio "
                "assembly (score/correlation/caps)",
                "base_heat": base["portfolio_heat"]}
    return {"admitted": True,
            "delta_heat": round(with_new["portfolio_heat"]
                                - base["portfolio_heat"], 6),
            "base_heat": base["portfolio_heat"],
            "with_heat": with_new["portfolio_heat"],
            "avg_correlation": round(extra[0]["correlation_penalty"], 6)}
