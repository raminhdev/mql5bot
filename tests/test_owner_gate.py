"""Owner-evidence intake red team (FINAL REALITY GATE §24/§25).

These tests exercise the evidence CONSUMER with synthetic packages.
A green test here proves the verifier fails closed — it is NOT MT5
evidence and never a certification claim.

Every attack must fail closed with an explainable state/verdict:
missing, stale, wrong, partial or simulated evidence can never become
a positive verdict.
"""

from __future__ import annotations

import json
import os

import pytest
from mql5bot import owner_gate as og

FROZEN_COMMIT = "a" * 40
FROZEN = {
    "source": {"commit": FROZEN_COMMIT},
    "gold_1": {"fixture_sha256": "f1" * 32, "config_hash": "c1" * 32,
               "dataset_hash_from_manifest": "d1" * 32},
    "gold_2": {"fixture_sha256": "f2" * 32, "config_hash": "c2" * 32,
               "dataset_hash_from_manifest": "d2" * 32,
               "provenance_label": "GOLD_2_RECONSTRUCTED_NEW_PROVENANCE"},
    "symbolspec_expectations": {"point": 1e-05, "volume_min": 0.01,
                                "contract_size": 100000},
}


def _w(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, (dict, list)):
        content = json.dumps(content, indent=2)
    path.write_text(content, encoding="utf-8")


def build_package(root, *, diverge_gold2=None, coverage="FULL",
                  skip=(), source_commit=FROZEN_COMMIT,
                  ex5_stale=False, log_stale=False, model_wrong=False):
    """Build a synthetic owner package. Divergence/wrongness hooks let
    each attack mutate exactly one thing."""
    root = root if hasattr(root, "mkdir") else __import__("pathlib").Path(root)
    ex5_bytes = b"\x00EX5-FRESH-BINARY" if not ex5_stale else b"OLD-BINARY"
    # the FRESH log is what the metadata binds; a stale attack swaps the
    # bytes on disk so the recorded hash no longer matches
    _fresh_log = ("Mql5Bot.mq5 - 0 error(s), 0 warning(s)\n"
                  "compile ok\n")
    ex5 = root / "compile" / "Mql5Bot.ex5"
    log = root / "compile" / "compile.log"
    if "compile" not in skip:
        ex5.parent.mkdir(parents=True, exist_ok=True)
        ex5.write_bytes(ex5_bytes)
        if log_stale:
            log.write_text("STALE LOG FROM AN ATTEMPT LONG AGO\n",
                           encoding="utf-8")
        else:
            log.write_text(_fresh_log, encoding="utf-8")
        import hashlib
        from datetime import datetime, timezone
        _w(root / "compile" / "compile_metadata.json", {
            "SOURCE_COMMIT": source_commit,
            "COMPILER_VERSION": "MetaEditor 5 build 9999",
            "TERMINAL_BUILD": "MT5 build 9999",
            "EX5_SHA256": hashlib.sha256(
                b"\x00EX5-FRESH-BINARY").hexdigest(),
            "COMPILE_TIMESTAMP": datetime.now(timezone.utc).isoformat(),
            "COMPILER_LOG_SHA256": hashlib.sha256(
                _fresh_log.encode()).hexdigest(),
            "ERRORS": 0, "WARNINGS": 0,
        })
    if ex5_stale:
        # keep the EX5 file but predate it vs the compile timestamp
        ex5.parent.mkdir(parents=True, exist_ok=True)
        ex5.write_bytes(b"OLD-BINARY")
        os.utime(ex5, (1000000000, 1000000000))

    if "symbolspec" not in skip:
        _w(root / "symbolspec" / "symbolspec.json", {
            "broker": "DemoBroker", "server": "Demo-Live", "symbol":
            "EURUSD", "point": 1e-05, "tick_size": 1e-05,
            "tick_value_profit": 10.0, "contract_size": 100000,
            "volume_min": 0.01, "volume_max": 100.0,
            "volume_step": 0.01, "volume_limit": 0.0,
            "stops_level_points": 10, "freeze_level_points": 0,
            "trade_mode": 4, "filling_mode_mask": 3,
            "expiration_mode_mask": 15, "currency_profit": "USD",
            "timestamp": "2026-09-08T12:05:00+00:00",
            "terminal_build": "9999",
        })

    models = {"m1_ohlc": 1, "every_tick": 0, "real_ticks": 3}
    for gold in ("gold1", "gold2"):
        bindings = {
            "source_commit": FROZEN_COMMIT,
            "fixture_sha256": FROZEN[f"gold_{gold[-1]}"]["fixture_sha256"],
            "config_hash": FROZEN[f"gold_{gold[-1]}"]["config_hash"],
            "dataset_hash": FROZEN[f"gold_{gold[-1]}"]
            ["dataset_hash_from_manifest"],
            "symbolspec_sha256": "ab" * 32,
            "ex5_sha256": "cd" * 32,
            "report_sha256": "ef" * 32,
            "tester_models": {
                m: {"requested": mid,
                    "report_reported": og.MODEL_LABELS[mid],
                    "journal": og.MODEL_LABELS[mid]}
                for m, mid in models.items()},
        }
        if model_wrong and gold == "gold2":
            bindings["tester_models"]["real_ticks"]["report_reported"] = \
                "Every tick"  # the terminal actually ran a different model
        events = [
            {"index": i, "bar": 10 + i, "time": f"2026-01-01 08:{i:02d}",
             "symbol": "EURUSD",
             "fields": {
                 "signal": {"python": 1, "mt5": 1, "status": "MATCH"},
                 "volume": {"python": 0.1, "mt5": 0.1, "status": "MATCH"},
                 "sl": {"python": 1.05, "mt5": 1.05, "status": "MATCH"},
             }} for i in range(56)]
        if diverge_gold2 and gold == "gold2":
            field, py_v, mt5_v = diverge_gold2
            events[3]["fields"][field] = {"python": py_v, "mt5": mt5_v,
                                          "status": "DIVERGENT"}
        if f"reconciliation_{gold}" not in skip and "reconciliation" \
                not in skip:
            _w(root / "reconciliation" / f"{gold}.json",
               {"gold": gold, "bindings": bindings, "events": events})
        for m in models:
            if f"raw_{gold}_{m}" not in skip:
                _w(root / gold / f"{m}.htm",
                   "<table><tr><td>Symbol</td><td>EURUSD</td></tr></table>")
                _w(root / "parsed" / f"{gold}_{m}.json",
                   {"settings": {"symbol": "EURUSD",
                                  "model": og.MODEL_LABELS[models[m]]}})

    cov = {
        "leg": "gold2:real_ticks",
        "requested_model": "Every tick based on real ticks",
        "actual_model_from_report": "Every tick based on real ticks",
        "terminal_model_identifier": "model 3",
        "requested_interval": "2026-01-01..2026-01-04",
        "actual_interval": "2026-01-01..2026-01-04",
        "broker": "DemoBroker", "symbol": "EURUSD",
        "real_tick_availability_evidence":
            "journal: real ticks loaded for the full interval",
        "coverage": ("REAL_TICK_COVERAGE_FULL" if coverage == "FULL"
                     else f"REAL_TICK_COVERAGE_{coverage}"),
        "fallback_intervals": [],
        "tester_build": "9999", "terminal_build": "9999",
        "notes": "synthetic self-test record",
    }
    if coverage != "FULL":
        cov["real_tick_availability_evidence"] = ""
    if "real_tick_coverage" not in skip:
        _w(root / "real_tick_coverage.json", cov)

    for name in og.SAFETY_TESTS + ("netting", "hedging"):
        if name in skip or "safety" in skip:
            continue
        _w(root / "safety" / f"{name}.json", {
            "action": f"{name} procedure executed on demo",
            "initial_state": "documented",
            "resulting_state": "documented",
            "observed_result": "pass per procedure",
            "raw_evidence": f"journal:{name}.log",
        })

    if "environment" not in skip:
        _w(root / "environment.json", {"os": "Windows 11",
                                       "terminal_build": "9999"})
    if "archive_manifest" not in skip:
        _w(root / "archive_manifest.json", {"chain": "complete"})
    return root


def gate(root):
    return og.run_gate(root, FROZEN)


# ---------------------------------------------------------------------------
# happy path: a complete, consistent package reaches the ceiling verdict
# ---------------------------------------------------------------------------


def test_complete_valid_package_reaches_mt5_validated(tmp_path):
    report = gate(build_package(tmp_path))
    assert report["verdict"] == og.MT5_VALIDATED
    assert report["gold"]["gold1"]["result"] == "MATCH"
    assert report["gold"]["gold2"]["result"] == "MATCH"
    assert report["first_divergence"] == {"gold1": None, "gold2": None}


# ---------------------------------------------------------------------------
# §24 stale-artifact attack battery — all fail closed
# ---------------------------------------------------------------------------


def test_stale_ex5_fails_closed(tmp_path):
    report = gate(build_package(tmp_path, ex5_stale=True))
    assert report["compile"]["state"] in (og.MISMATCHED, og.STALE)
    assert report["verdict"] == og.NOT_VERIFIED_ARTIFACT_MISMATCH


def test_stale_compile_log_fails_closed(tmp_path):
    report = gate(build_package(tmp_path, log_stale=True))
    assert report["compile"]["checks"]["log_hash"] == og.MISMATCHED
    assert report["verdict"] == og.NOT_VERIFIED_ARTIFACT_MISMATCH


def test_wrong_source_commit_fails_closed(tmp_path):
    report = gate(build_package(tmp_path, source_commit="b" * 40))
    assert report["compile"]["checks"]["source_commit"] == og.MISMATCHED
    assert report["verdict"] == og.NOT_VERIFIED_ARTIFACT_MISMATCH


def test_model_identity_mismatch_fails_closed(tmp_path):
    report = gate(build_package(tmp_path, model_wrong=True))
    assert report["verdict"] == og.NOT_VERIFIED_ARTIFACT_MISMATCH
    assert any("MODEL_IDENTITY_MISMATCH" in r
               for r in report["reasons"])


def test_reconciliation_binding_mismatch_fails_closed(tmp_path):
    root = build_package(tmp_path)
    doc = json.loads((root / "reconciliation" / "gold2.json").read_text())
    doc["bindings"]["fixture_sha256"] = "99" * 32  # wrong fixture identity
    (root / "reconciliation" / "gold2.json").write_text(json.dumps(doc))
    report = gate(root)
    assert report["gold"]["gold2"]["state"] == og.MISMATCHED
    assert report["verdict"] == og.NOT_VERIFIED_ARTIFACT_MISMATCH


def test_symbolspec_missing_field_fails_closed(tmp_path):
    root = build_package(tmp_path)
    doc = json.loads((root / "symbolspec" / "symbolspec.json").read_text())
    del doc["volume_step"]
    (root / "symbolspec" / "symbolspec.json").write_text(json.dumps(doc))
    report = gate(root)
    assert report["symbolspec"]["state"] == og.INVALID
    assert report["verdict"] == og.NOT_VERIFIED_ARTIFACT_MISMATCH


def test_symbolspec_decision_changing_mismatch_stops(tmp_path):
    root = build_package(tmp_path)
    doc = json.loads((root / "symbolspec" / "symbolspec.json").read_text())
    doc["point"] = 1e-04  # decision-changing vs frozen 1e-05
    (root / "symbolspec" / "symbolspec.json").write_text(json.dumps(doc))
    report = gate(root)
    assert report["symbolspec"]["state"] == og.MISMATCHED
    assert any("DECISION_CHANGING_MISMATCH" in r
               for r in report["symbolspec"]["reasons"])
    assert report["verdict"] == og.NOT_VERIFIED_ARTIFACT_MISMATCH


def test_edited_report_parse_garbage_is_not_evidence(tmp_path):
    root = build_package(tmp_path)
    _w(root / "parsed" / "gold1_m1_ohlc.json", "{not json")
    # a broken parsed report does not silently pass: the artifact scan
    # keeps it PRESENT_UNVERIFIED and reconciliation identity (report
    # binding) is the proof path — gate stays non-positive without the
    # full chain
    report = gate(root)
    assert report["verdict"] != og.VERIFIED


# ---------------------------------------------------------------------------
# §25 partial packages — never VERIFIED, precise missing reasons
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skip", [
    ("hedging",),             # every single missing slot counts
    ("symbolspec",),
    ("reconciliation",),
    ("safety",),
    ("real_tick_coverage",),
    ("netting",),
    ("environment",),
])
def test_partial_packages_never_verify(tmp_path_factory, skip):
    root = tmp_path_factory.mktemp("pkg")
    report = gate(build_package(root, skip=skip))
    assert report["verdict"] not in og.POSITIVE_VERDICTS
    assert report["reasons"], "verdict must carry exact reasons"


def test_compile_only_package_reports_missing(tmp_path):
    root = build_package(tmp_path, skip=(
        "symbolspec", "reconciliation", "safety", "real_tick_coverage",
        "netting", "hedging", "environment", "archive_manifest"))
    report = gate(root)
    assert report["verdict"] in (og.NOT_VERIFIED_RECONCILIATION_MISSING,
                                 og.NOT_VERIFIED_MISSING_MT5_EVIDENCE)
    assert any("missing artifacts" in r for r in report["reasons"])


# ---------------------------------------------------------------------------
# §11 real-tick coverage — selection is not proof, UNKNOWN never promotes
# ---------------------------------------------------------------------------


def test_unknown_coverage_constrains_the_verdict(tmp_path):
    report = gate(build_package(tmp_path, coverage="UNKNOWN"))
    assert report["verdict"] == og.NOT_VERIFIED_REAL_TICK_COVERAGE_UNKNOWN


def test_partial_coverage_stays_limited(tmp_path):
    report = gate(build_package(tmp_path, coverage="PARTIAL"))
    assert report["verdict"] == og.NOT_VERIFIED_REAL_TICK_COVERAGE_UNKNOWN
    assert report["real_tick_coverage"]["coverage"] == \
        "REAL_TICK_COVERAGE_PARTIAL"


def test_full_coverage_without_evidence_is_rejected(tmp_path):
    root = build_package(tmp_path)
    doc = json.loads((root / "real_tick_coverage.json").read_text())
    doc["real_tick_availability_evidence"] = ""  # claim FULL, no proof
    (root / "real_tick_coverage.json").write_text(json.dumps(doc))
    report = gate(root)
    assert report["real_tick_coverage"]["state"] == og.INVALID
    assert report["verdict"] != og.MT5_VALIDATED


# ---------------------------------------------------------------------------
# §14/§15 first divergence + deterministic classification
# ---------------------------------------------------------------------------


def test_first_divergence_is_found_and_classified(tmp_path):
    report = gate(build_package(tmp_path,
                                diverge_gold2=("sl", 1.05, 1.06)))
    div = report["gold"]["gold2"]["first_divergence"]
    assert div is not None
    assert div["event_index"] == 3
    assert div["first_divergent_field"] == "sl"
    assert div["classification"] == og.ROUNDING_MISMATCH
    assert report["verdict"] == og.NOT_VERIFIED_ARTIFACT_MISMATCH


def test_first_divergence_earliest_event_wins(tmp_path):
    root = build_package(tmp_path)
    doc = json.loads((root / "reconciliation" / "gold2.json").read_text())
    doc["events"][9]["fields"]["signal"] = {"python": 1, "mt5": 0,
                                            "status": "DIVERGENT"}
    doc["events"][2]["fields"]["volume"] = {"python": 0.1, "mt5": 0.2,
                                            "status": "DIVERGENT"}
    (root / "reconciliation" / "gold2.json").write_text(json.dumps(doc))
    div = og.run_gate(root, FROZEN)["gold"]["gold2"]["first_divergence"]
    assert div["event_index"] == 2
    assert div["classification"] == og.SIZING_MISMATCH


def test_classification_is_deterministic_and_closed():
    assert og.classify_field("signal") == og.SIGNAL_MISMATCH
    assert og.classify_field("indicator_rsi") == og.INDICATOR_MISMATCH
    assert og.classify_field("session_state") == og.SESSION_MISMATCH
    assert og.classify_field("meta_weight") == og.META_MISMATCH
    assert og.classify_field("risk_veto") == og.RISK_MISMATCH
    assert og.classify_field("exit_reason") == og.EXECUTION_MISMATCH
    assert og.classify_field("timestamp") == og.TIMESTAMP_MISMATCH
    assert og.classify_field("position_identifier") == og.STATE_MISMATCH
    assert og.classify_field("broker_point") == og.BROKER_SPEC_MISMATCH
    assert og.classify_field("close") == og.DATA_MISMATCH
    assert og.classify_field("something_unmapped") == og.UNKNOWN
    assert og.UNKNOWN in og.TAXONOMY and len(og.TAXONOMY) == 14


# ---------------------------------------------------------------------------
# §20 safety evidence discipline
# ---------------------------------------------------------------------------


def test_screenshot_only_safety_evidence_is_invalid(tmp_path):
    root = build_package(tmp_path)
    _w(root / "safety" / "kill_switch.json", {
        "action": "latched", "initial_state": "flat",
        "resulting_state": "latched", "observed_result": "pass",
        "raw_evidence": "screenshot.png"})
    report = gate(root)
    assert report["safety"]["kill_switch"]["state"] == og.INVALID
    assert report["verdict"] == og.NOT_VERIFIED_ARTIFACT_MISMATCH


def test_hedging_may_be_blocked_but_nothing_else(tmp_path):
    root = build_package(tmp_path)
    _w(root / "safety" / "hedging.json",
       {"blocked_owner_environment": True,
        "reason": "netting-only account"})
    report = gate(root)
    assert report["safety"]["hedging"]["result"] == \
        "BLOCKED_OWNER_ENVIRONMENT"
    _w(root / "safety" / "kill_switch.json",
       {"blocked_owner_environment": True})
    report = gate(root)
    assert report["safety"]["kill_switch"]["state"] == og.INVALID


# ---------------------------------------------------------------------------
# §5 freeze-anchor change classification + §7 states + no-gold-upgrade
# ---------------------------------------------------------------------------


def test_anchor_change_classification():
    cls = og.classify_anchor_changes(
        ["docs/NOTE.md", "python/mql5bot/engine.py", "README.md"])
    assert cls["execution_relevant"] == ["python/mql5bot/engine.py"]
    assert cls["golds_still_frozen"] is False
    cls = og.classify_anchor_changes(["docs/NOTE.md", "HANDOFF.md"])
    assert cls["execution_relevant"] == []
    assert cls["golds_still_frozen"] is True


def test_validity_states_are_never_booleans():
    assert len(og.ARTIFACT_STATES) == 7
    assert og.PENDING_OWNER in og.ARTIFACT_STATES
    assert og.STALE in og.ARTIFACT_STATES


def test_gold_semantic_pass_never_upgrades_here():
    # a package with NO mt5 artifacts at all can never be positive —
    # gold fixtures alone are not runtime evidence
    report = og.run_gate("/nonexistent-dir", FROZEN)
    assert report["verdict"] == og.NOT_VERIFIED_MISSING_MT5_EVIDENCE
    assert report["verdict"] not in og.POSITIVE_VERDICTS


def test_scan_flags_ambiguous_directory_artifact(tmp_path):
    root = build_package(tmp_path)
    (root / "symbolspec" / "symbolspec.json").unlink()
    (root / "symbolspec" / "symbolspec.json").mkdir()  # dir, not file
    scan = og.scan_package(root)
    assert scan["symbolspec"]["state"] == og.INVALID
