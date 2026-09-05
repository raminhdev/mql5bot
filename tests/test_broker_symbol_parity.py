"""AEGIS Phase 3 — broker/symbol parity machinery.

Pins the FIELD MAP (every mandated broker fact has a named owner-export
field, a Python SymbolSpec side or an explicit runtime-authority marker, and
a tolerance), the strict fail-fast export schema, the never-invent rule (no
owner export ⇒ PENDING, no fabricated numbers anywhere), the derived
tick-value P/L identity, and behavioural sizer parity against exported
grids.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "python"))

from broker_symbol_parity import (
    FIELD_MAP,
    REQUIRED_ASSET_CLASSES,
    compare_symbol,
    derived_pl_check,
    load_owner_export,
    render_markdown,
    sizer_behaviour_parity,
)

MQL5_EXPORT_SCRIPT = REPO / "mql5/Scripts/Mql5Bot/Mql5BotExportSymbolSpec.mq5"


def _synthetic_export(tmp_path, **over):
    sym = {
        "name": "EURUSD", "digits": 5, "point": 1e-05, "tick_size": 1e-05,
        "tick_value_profit": 1.0, "tick_value_loss": 1.0,
        "contract_size": 100000.0, "volume_min": 0.01, "volume_max": 100.0,
        "volume_step": 0.01, "volume_limit": 0.0, "stops_level_points": 0,
        "freeze_level_points": 0, "currency_profit": "USD",
        "trade_mode": 4, "filling_mode_mask": 1, "order_mode": 0,
        "expiration_mode_mask": 15, "margin_initial": 0.0,
        "margin_maintenance": 0.0,
    }
    sym.update(over)
    doc = {"schema": "mql5bot.broker_export/1", "symbol": sym}
    p = tmp_path / "EURUSD.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return doc


# ---------------------------------------------------------------------------
# field map completeness (the mandated parity surface)
# ---------------------------------------------------------------------------


def test_field_map_covers_every_mandated_broker_fact():
    mandated = {
        "tick_size", "tick_value_profit", "tick_value_loss", "contract_size",
        "volume_min", "volume_max", "volume_step", "volume_limit",
        "margin_initial", "margin_maintenance", "trade_mode",
        "filling_mode_mask", "order_mode", "stops_level_points",
        "freeze_level_points", "digits", "point", "currency_profit",
    }
    assert mandated <= set(FIELD_MAP)
    # every mapped field declares a tolerance and at least one consumer
    for _py, _mq, consumers, tag in FIELD_MAP.values():
        assert consumers, "field without consumer annotation"
        assert tag in ("exact", "rel1e-12", "rel1e-9")


def test_python_side_fields_exist_on_symbolspec():
    from mql5bot.symbolspec import SymbolSpec
    for py_attr, _mq, _c, _t in FIELD_MAP.values():
        if py_attr is not None:
            assert py_attr in SymbolSpec.__dataclass_fields__


def test_mql5_ssymbolspec_has_every_mapped_member():
    src = (REPO / "mql5/Include/Mql5Bot/SymbolSpec.mqh").read_text(encoding="utf-8")
    for field, (_py, mq_member, _c, _t) in FIELD_MAP.items():
        if mq_member is not None:
            assert mq_member in src, f"SSymbolSpec missing {mq_member} ({field})"


def test_export_script_dumps_every_mandated_field():
    src = MQL5_EXPORT_SCRIPT.read_text(encoding="utf-8")
    for field in FIELD_MAP:
        assert f'JsonQuote("{field}")' in src, f"export script misses {field}"
    # and an OrderCalcMargin probe so margin parity has runtime authority
    assert "OrderCalcMargin" in src


def test_required_asset_classes_pinned():
    assert REQUIRED_ASSET_CLASSES == ("FX", "METAL", "INDEX_CFD", "CRYPTO")


# ---------------------------------------------------------------------------
# strict schema — fail fast, never repair
# ---------------------------------------------------------------------------


def test_load_owner_export_rejects_wrong_schema_and_missing_fields(tmp_path):
    doc = _synthetic_export(tmp_path)
    doc["schema"] = "some/other"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="wrong schema"):
        load_owner_export(p)

    doc2 = _synthetic_export(tmp_path)
    del doc2["symbol"]["tick_value_loss"]
    p2 = tmp_path / "bad2.json"
    p2.write_text(json.dumps(doc2), encoding="utf-8")
    with pytest.raises(ValueError, match="missing fields"):
        load_owner_export(p2)


def test_missing_export_reports_pending_and_fabricates_nothing(capsys):
    from broker_symbol_parity import build_report
    exports, rows, coverage = build_report(
        REPO / "data/broker_exports/definitely-missing-dir")
    assert exports == [] and rows == []
    assert all(v.startswith("PENDING") for v in coverage.values())
    md = render_markdown([], [], coverage)
    assert "NOT VERIFIED" in md and "PENDING" in md
    out = capsys.readouterr()  # no exception; no invented numbers in doc
    assert out.err == ""


# ---------------------------------------------------------------------------
# comparison semantics
# ---------------------------------------------------------------------------


def test_compare_flags_mismatch_within_tolerance(tmp_path):
    from mql5bot.symbolspec import SymbolSpec
    model = SymbolSpec()  # defaults == the synthetic EURUSD export
    doc = _synthetic_export(tmp_path, tick_value_loss=1.0000000001)
    rows = compare_symbol(doc, model)
    by = {r.field: r for r in rows}
    assert by["tick_value_loss"].status == "MATCH"      # inside rel 1e-9
    doc_off = _synthetic_export(tmp_path, tick_value_loss=1.1)
    by_off = {r.field: r for r in compare_symbol(doc_off, model)}
    assert by_off["tick_value_loss"].status == "MISMATCH"  # outside tolerance
    doc2 = _synthetic_export(tmp_path, volume_step=0.001)
    by2 = {r.field: r for r in compare_symbol(doc2, model)}
    assert by2["volume_step"].status == "MISMATCH"      # exact-tolerance field


def test_runtime_authority_fields_marked_n_a_not_matched(tmp_path):
    doc = _synthetic_export(tmp_path)
    rows = compare_symbol(doc, None)
    by = {r.field: r for r in rows}
    for runtime_field in ("trade_mode", "filling_mode_mask", "margin_initial"):
        assert by[runtime_field].status == "N_A"
        assert "runtime" in by[runtime_field].python or \
            "runtime" in by[runtime_field].detail


def test_derived_tick_value_identity(tmp_path):
    doc = _synthetic_export(tmp_path)  # 100000 × 1e-5 × 1.0 = 1.0
    assert derived_pl_check(doc, fx_profit_to_deposit=1.0).status == "MATCH"
    assert derived_pl_check(doc, fx_profit_to_deposit=0.9).status == "MISMATCH"
    r = derived_pl_check(doc, fx_profit_to_deposit=None)
    assert r.status == "PENDING" and "fx" in r.detail


def test_derived_identity_cross_currency(tmp_path):
    # XAU-like: contract 100 oz, tick 0.01 → structural 1.0 USD/tick; with
    # deposit EUR the owner-supplied fx must reconcile
    doc = _synthetic_export(tmp_path, name="XAUUSD", contract_size=100.0,
                            tick_size=0.01, tick_value_loss=1.0,
                            currency_profit="USD")
    assert derived_pl_check(doc, fx_profit_to_deposit=1.0).status == "MATCH"
    assert derived_pl_check(doc, fx_profit_to_deposit=1.08).status == "MISMATCH"


def test_sizer_behaviour_parity_on_exported_grid(tmp_path):
    doc = _synthetic_export(tmp_path, tick_size=0.25, point=0.01,
                            volume_step=0.1, volume_min=0.1)
    rows = sizer_behaviour_parity(doc)
    by = {r.field: r for r in rows}
    # floor semantics: 0.1 + 0.4×0.1 = 0.14 → floored to 0.1 (never up)
    assert by["sizer.normalize_volume(floor)"].owner == pytest.approx(0.14)
    assert by["sizer.normalize_volume(floor)"].python == pytest.approx(0.1)
    assert by["sizer.loss_per_lot"].status == "MATCH"


def test_crypto_style_grid_non_point_tick_size(tmp_path):
    # index/crypto CFDs where tick_size is a multiple of point — the sizer
    # must use tick_size (not digits/point) for rounding
    doc = _synthetic_export(tmp_path, name="BTCUSD", digits=2, point=0.01,
                            tick_size=0.5, contract_size=1.0,
                            tick_value_loss=0.5)
    rows = sizer_behaviour_parity(doc)
    by = {r.field: r for r in rows}
    assert by["sizer.loss_per_lot"].status == "MATCH"
    # structural: contract 1.0 × tick 0.5 = 0.5 = exported tick value
    assert derived_pl_check(doc, fx_profit_to_deposit=1.0).status == "MATCH"
