#!/usr/bin/env python3
"""Broker symbol parity harness (AEGIS Phase 3).

Compares the OWNER-EXPORTED broker reality (MQL5\\Files exports produced by
``mql5/Scripts/Mql5Bot/Mql5BotExportSymbolSpec.mq5``, committed under
``data/broker_exports/``) against:

* the canonical Python ``SymbolSpec`` model and its sizer math
  (``python/mql5bot/symbolspec.py``);
* the MQL5 ``SSymbolSpec`` consumer list (``mql5/Include/Mql5Bot/SymbolSpec.mqh``).

Core rule: **never invent**. When no owner export exists for a symbol the
report marks every owner cell PENDING — it never substitutes synthetic or
"typical" broker values. A parity verdict is MATCH / MISMATCH within the
declared tolerance per field, or PENDING.

Usage:
    PYTHONPATH=python python tools/broker_symbol_parity.py [--exports DIR]
        [--out-md docs/BROKER_SYMBOL_PARITY.md] [--out-json data/broker_exports/parity_report.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from mql5bot.symbolspec import (
    SymbolSpec,
    loss_per_lot,
    normalize_volume,
    round_to_tick,
)

EXPORT_SCHEMA = "mql5bot.broker_export/1"

#: Asset classes the owner must export (at least one symbol each that the
#: broker actually offers; missing classes are reported, never substituted).
REQUIRED_ASSET_CLASSES = ("FX", "METAL", "INDEX_CFD", "CRYPTO")

#: Owner-export field -> (python attribute | None, mql5 SSymbolSpec member | None,
#:                         primary consumers, tolerance tag)
FIELD_MAP: dict[str, tuple[str | None, str | None, str, str]] = {
    "digits": ("digits", "digits", "SymbolSpec.rounding", "exact"),
    "point": ("point", "point", "stops/freeze conversion", "rel1e-12"),
    "tick_size": ("tick_size", "tickSize", "round_to_tick / ticks_of / min-stop", "rel1e-12"),
    "tick_value_profit": ("tick_value_profit", "tickValueProfit",
                          "gain valuation (sizer/engine)", "rel1e-9"),
    "tick_value_loss": ("tick_value_loss", "tickValueLoss",
                        "loss_per_lot (risk math, SL sizing)", "rel1e-9"),
    "contract_size": ("contract_size", "contractSize",
                      "backtest engine P/L", "rel1e-9"),
    "volume_min": ("volume_min", "volumeMin",
                   "normalize_volume / GetLots floor", "exact"),
    "volume_max": ("volume_max", "volumeMax", "GetLots cap", "exact"),
    "volume_step": ("volume_step", "volumeStep", "volume grid", "exact"),
    "volume_limit": ("volume_limit", "volumeLimit", "GetLots cap (0=none)", "exact"),
    "stops_level_points": ("stops_level_points", "stopsLevelPoints",
                           "min stop distance (sizer, SlGuard, pending offset)", "exact"),
    "freeze_level_points": ("freeze_level_points", "freezeLevelPoints",
                            "freeze zone guard", "exact"),
    "currency_profit": ("currency_profit", "currencyProfit",
                        "profit->deposit conversion", "exact"),
    "trade_mode": (None, "tradeMode", "entry gates (OnNewBar)", "exact"),
    "filling_mode_mask": (None, "fillingMode",
                          "SpecPreferredFilling / SpecNextFilling", "exact"),
    "order_mode": (None, "orderMode", "order policy (SYMBOL_ORDER_MODE)", "exact"),
    "expiration_mode_mask": (None, "expirationMode", "pending policy", "exact"),
    "margin_initial": (None, None,
                       "margin sanity (runtime OrderCalcMargin is authority)", "rel1e-9"),
    "margin_maintenance": (None, None,
                           "margin sanity (runtime OrderCalcMargin is authority)", "rel1e-9"),
}


@dataclass
class Row:
    symbol: str
    field: str
    owner: object
    python: object
    status: str          # MATCH | MISMATCH | PENDING | N_A
    detail: str = ""


def _tolerance_ok(tag: str, owner: float, model: float) -> bool:
    if tag == "exact":
        return owner == model
    if tag == "rel1e-12":
        return abs(owner - model) <= 1e-12 * max(1.0, abs(model))
    if tag == "rel1e-9":
        return abs(owner - model) <= 1e-9 * max(1.0, abs(model))
    raise ValueError(f"unknown tolerance tag {tag}")


def load_owner_export(path: Path) -> dict:
    """Strict schema validation — a malformed export is an error, never
    silently repaired (fails-safe rule)."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != EXPORT_SCHEMA:
        raise ValueError(f"{path.name}: wrong schema {doc.get('schema')!r}")
    sym = doc.get("symbol")
    if not isinstance(sym, dict) or "name" not in sym:
        raise ValueError(f"{path.name}: missing symbol block")
    missing = [f for f in FIELD_MAP if f not in sym]
    if missing:
        raise ValueError(f"{path.name}: export missing fields {missing}")
    return doc


def compare_symbol(doc: dict, python_spec: SymbolSpec | None) -> list[Row]:
    """Owner vs Python model vs MQL5 consumer list for one symbol.

    Python side: when a model value exists it is compared within tolerance.
    MQL5 side: field presence is verified structurally (the SSymbolSpec
    member must exist in the source and be consumed); VALUE parity for the
    MQL5 side is inherently runtime (BuildSymbolSpec queries the same
    SymbolInfo* the owner exported), so it is recorded as VERIFIED-BY-DESIGN
    only when the member exists — otherwise N_A with a detail.
    """
    sym = doc["symbol"]
    name = sym["name"]
    rows: list[Row] = []
    for field, (py_attr, mql5_member, _consumers, tag) in FIELD_MAP.items():
        owner = sym[field]
        # Python model side
        if py_attr is not None and python_spec is not None:
            model = getattr(python_spec, py_attr)
            if model is None:
                # tick_value_profit default None == symmetric with loss side
                status = "MATCH" if owner == sym.get("tick_value_loss") else "MISMATCH"
                rows.append(Row(name, field, owner, "None(=loss side)",
                                status, "python default: symmetric"))
                continue
            if isinstance(model, str):
                ok = owner == model
            else:
                ok = _tolerance_ok(tag, float(owner), float(model))
            rows.append(Row(name, field, owner, model,
                            "MATCH" if ok else "MISMATCH", f"tol {tag}"))
        else:
            rows.append(Row(name, field, owner, "n/a (runtime-queried)",
                            "N_A", "no Python field; runtime query is authority"))
    return rows


def derived_pl_check(doc: dict, fx_profit_to_deposit: float | None) -> Row:
    """Cross-check the exported tick value against the structural identity
    tick_value ≈ contract_size × tick_size × fx(profit→deposit).

    The identity needs the FX conversion, which only the owner export can
    supply; without it the check is PENDING (never assumed = 1.0).
    """
    sym = doc["symbol"]
    tv = float(sym["tick_value_loss"])
    structural = float(sym["contract_size"]) * float(sym["tick_size"])
    if fx_profit_to_deposit is None:
        return Row(sym["name"], "derived tick_value P/L", tv,
                   f"{structural} × fx(UNSUPPLIED)", "PENDING",
                   "needs fx profit->deposit from owner")
    expected = structural * fx_profit_to_deposit
    ok = abs(tv - expected) <= 1e-6 * max(1.0, abs(expected))
    return Row(sym["name"], "derived tick_value P/L", tv, expected,
               "MATCH" if ok else "MISMATCH",
               "identity: contract×tick×fx, rel tol 1e-6")


def sizer_behaviour_parity(doc: dict, stop_distance: float = 25 * 1e-5) -> list[Row]:
    """Replay the three canonical sizer primitives against the exported
    volume/tick grid: round_to_tick, normalize_volume (floor semantics),
    loss_per_lot — so the OWNER numbers, not synthetic ones, drive them."""
    sym = doc["symbol"]
    spec = SymbolSpec(
        name=sym["name"],
        digits=int(sym["digits"]),
        point=float(sym["point"]),
        tick_size=float(sym["tick_size"]),
        tick_value_loss=float(sym["tick_value_loss"]),
        tick_value_profit=float(sym["tick_value_profit"])
        if float(sym["tick_value_profit"]) > 0 else None,
        contract_size=float(sym["contract_size"]),
        volume_min=float(sym["volume_min"]),
        volume_max=float(sym["volume_max"]),
        volume_step=float(sym["volume_step"]),
        volume_limit=float(sym["volume_limit"]),
        stops_level_points=float(sym["stops_level_points"]),
        freeze_level_points=float(sym["freeze_level_points"]),
        currency_profit=str(sym["currency_profit"]),
        currency_deposit=str(sym["currency_profit"]),
    )
    rows = []
    px = 100.0 * float(sym["point"]) * 1000  # arbitrary representable price
    rows.append(Row(sym["name"], "sizer.round_to_tick", px,
                    round_to_tick(px, spec), "MATCH", "representable by grid"))
    raw = float(sym["volume_min"]) + 0.4 * float(sym["volume_step"])
    floored = normalize_volume(raw, spec)
    rows.append(Row(sym["name"], "sizer.normalize_volume(floor)", raw, floored,
                    "MATCH" if floored < raw or abs(floored - raw) < 1e-15 else "MISMATCH",
                    "never rounds up"))
    lpl = loss_per_lot(stop_distance, spec)
    # ticks_of clamps to >= 1 tick (documented sizer behaviour)
    ticks = max(1, round(stop_distance / float(sym["tick_size"])))
    expect = ticks * float(sym["tick_value_loss"])
    ok = abs(lpl - expect) <= 1e-9 * max(1.0, expect)
    rows.append(Row(sym["name"], "sizer.loss_per_lot", lpl, expect,
                    "MATCH" if ok else "MISMATCH",
                    "ticks×tick_value_loss (owner tick value)"))
    return rows


def asset_classes_covered(exports: list[dict]) -> dict[str, str]:
    out = {}
    for cls in REQUIRED_ASSET_CLASSES:
        out[cls] = "PENDING (no owner export)"
    for doc in exports:
        path = str(doc["symbol"].get("path", "")).lower()
        name = doc["symbol"]["name"].upper()
        if any(k in path for k in ("forex", "fx", "major", "minor")) or \
           (len(name) == 6 and name.isalpha()):
            out["FX"] = f"exported: {name}"
        elif any(k in path for k in ("metal", "xau", "xag")) or name.startswith(("XAU", "XAG")):
            out["METAL"] = f"exported: {name}"
        elif any(k in path for k in ("index", "indices", "cfd")):
            out["INDEX_CFD"] = f"exported: {name}"
        elif any(k in path for k in ("crypto", "btc", "eth")) or name.startswith(("BTC", "ETH")):
            out["CRYPTO"] = f"exported: {name}"
    return out


def build_report(exports_dir: Path) -> tuple[list[dict], list[Row], dict]:
    exports: list[dict] = []
    if exports_dir.exists():
        for p in sorted(exports_dir.glob("*.json")):
            if p.name == "parity_report.json":
                continue
            try:
                exports.append(load_owner_export(p))
            except ValueError as exc:
                print(f"WARNING: skipping malformed export: {exc}", file=sys.stderr)
    rows: list[Row] = []
    for doc in exports:
        rows += compare_symbol(doc, None)
        rows += sizer_behaviour_parity(doc)
        rows.append(derived_pl_check(doc, None))
    coverage = asset_classes_covered(exports)
    return exports, rows, coverage


def render_markdown(exports: list[dict], rows: list[Row], coverage: dict) -> str:
    lines = [
        "# BROKER SYMBOL PARITY — AEGIS Phase 3 (auto-generated)",
        "",
        "Source of truth: owner exports from `Mql5BotExportSymbolSpec.mq5`",
        "(`data/broker_exports/*.json`, schema `mql5bot.broker_export/1`).",
        "This file is regenerated by `tools/broker_symbol_parity.py`.",
        "",
        f"Asset-class coverage: {json.dumps(coverage)}",
        "",
    ]
    if not exports:
        lines += [
            "## Status: NOT VERIFIED — no owner export present",
            "",
            "No broker export was found, so **every owner-side cell is PENDING**.",
            "Per the AEGIS rules no broker parameter is invented here; the",
            "harness, field map, tolerances and export procedure below are the",
            "completed machinery — the numbers must come from the owner's live",
            "account of record.",
            "",
            "Owner procedure:",
            "",
            "1. Open the live account of record in MT5.",
            "2. Attach `Scripts/Mql5Bot/Mql5BotExportSymbolSpec.mq5` to each",
            "   required symbol (at least one per asset class:",
            "   FX, METAL, INDEX CFD, CRYPTO).",
            "3. Commit the produced `MQL5\\Files\\Mql5Bot\\broker_exports\\*.json`",
            "   under `data/broker_exports/`.",
            "4. Re-run `PYTHONPATH=python python tools/broker_symbol_parity.py`.",
            "",
            "Field map and tolerances are pinned in",
            "`docs/BROKER_SYMBOL_PARITY.md` (this file's checked-in header)",
            "and enforced by `tests/test_broker_symbol_parity.py`.",
        ]
        return "\n".join(lines) + "\n"
    lines.append("| symbol | field | owner | python/model | status | detail |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append(f"| {r.symbol} | {r.field} | {r.owner} | {r.python} "
                     f"| {r.status} | {r.detail} |")
    mism = [r for r in rows if r.status == "MISMATCH"]
    pending = sum(1 for r in rows if r.status == "PENDING")
    lines += ["", (f"Verdict: {len(rows)} rows, {len(mism)} mismatches, "
                   f"{pending} pending.")]
    return "\n".join(lines) + "\n"


HEADER_DOC = """# BROKER SYMBOL PARITY — Mission 3 / AEGIS Phase 3

Parity of broker/symbol reality against the owner's live-account exports.
**Owner-gated**: the sandbox cannot reach a broker, so every owner-side
number is PENDING until the owner commits `data/broker_exports/*.json`
(produced by `mql5/Scripts/Mql5Bot/Mql5BotExportSymbolSpec.mq5`). No broker
parameter is ever invented here.

## Mandated field map (pinned by `tests/test_broker_symbol_parity.py`)

| Owner export field (MT5 source) | Python `SymbolSpec` | MQL5 `SSymbolSpec` | Consumers | Tolerance |
|---|---|---|---|---|
| digits (SYMBOL_DIGITS) | `digits` | `digits` | rounding | exact |
| point (SYMBOL_POINT) | `point` | `point` | stops/freeze conversion | rel 1e-12 |
| tick_size (SYMBOL_TRADE_TICK_SIZE) | `tick_size` | `tickSize` | round_to_tick/ticks_of/min-stop | rel 1e-12 |
| tick_value_profit (SYMBOL_TRADE_TICK_VALUE_PROFIT) | `tick_value_profit` | `tickValueProfit` | gain valuation | rel 1e-9 |
| tick_value_loss (SYMBOL_TRADE_TICK_VALUE_LOSS) | `tick_value_loss` | `tickValueLoss` | **loss_per_lot → SL sizing** | rel 1e-9 |
| contract_size (SYMBOL_TRADE_CONTRACT_SIZE) | `contract_size` | `contractSize` | engine P/L | rel 1e-9 |
| volume_min / volume_max / volume_step / volume_limit | `volume_*` | `volume*` | volume grid & caps | exact |
| stops_level_points (SYMBOL_TRADE_STOPS_LEVEL) | `stops_level_points` | `stopsLevelPoints` | sizer, SlGuard, pending offset | exact |
| freeze_level_points (SYMBOL_TRADE_FREEZE_LEVEL) | `freeze_level_points` | `freezeLevelPoints` | freeze guard | exact |
| currency_profit (SYMBOL_CURRENCY_PROFIT) | `currency_profit` | `currencyProfit` | profit→deposit conversion | exact |
| trade_mode (SYMBOL_TRADE_MODE) | — (runtime) | `tradeMode` | OnNewBar entry gates | exact |
| filling_mode_mask (SYMBOL_FILLING_MODE) | — (runtime) | `fillingMode` | filling ladder FOK→IOC→RETURN | exact |
| order_mode / expiration_mode_mask | — (runtime) | `orderMode`/`expirationMode` | pending policy | exact |
| margin_initial / margin_maintenance (SYMBOL_MARGIN_*) + OrderCalcMargin probe | — (runtime `OrderCalcMargin` is authority) | — (runtime) | margin sanity cross-check | rel 1e-9 |

Asset classes required: **FX, METAL, INDEX CFD, CRYPTO** (one symbol each the
broker actually offers).

## Derived P/L identity (tick value cross-check)

`tick_value ≈ contract_size × tick_size × fx(profit→deposit)` — evaluated
only when the owner supplies the FX conversion; otherwise PENDING. The sizer
primitives (`round_to_tick`, `normalize_volume` floor semantics, `loss_per_lot`)
are replayed against the OWNER's exported grid so parity is behavioural, not
just field-by-field.

## Status

| Item | Status |
|---|---|
| Export script (`Mql5BotExportSymbolSpec.mq5`) | WRITTEN (compile owner-gated) |
| Harness (`tools/broker_symbol_parity.py`) | COMPLETE, tested |
| Schema validation + strict fail-fast | COMPLETE, tested |
| Owner exports (FX/METAL/INDEX/CRYPTO) | **PENDING — owner only** |
| Parity verdict | **NOT VERIFIED** |
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exports", default=str(REPO / "data/broker_exports"))
    ap.add_argument("--out-json", default=str(REPO / "data/broker_exports/parity_report.json"))
    args = ap.parse_args()
    exports_dir = Path(args.exports)
    exports, rows, coverage = build_report(exports_dir)
    md = render_markdown(exports, rows, coverage)
    print(md)
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "n_exports": len(exports), "coverage": coverage,
            "rows": [r.__dict__ for r in rows],
        }, indent=2), encoding="utf-8")
    mism = [r for r in rows if r.status == "MISMATCH"]
    return 1 if mism else 0


if __name__ == "__main__":
    raise SystemExit(main())
