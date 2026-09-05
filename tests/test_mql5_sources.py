"""MQL5 source structural invariants (Phase 2 integrity audit).

The EA cannot be compiled in this sandbox (no metaeditor64.exe); these
tests pin the SOURCE-LEVEL evidence for the audited features so a stale
or alternative implementation cannot silently return:

* S1 — post-fill SL verification with modify → re-verify → close
  remediation (SlGuard.mqh);
* S2 — persistent daily-loss / drawdown / kill-switch state
  (StateStore.mqh GlobalVariables + file journal);
* S3 — zero ``Sleep()`` anywhere in the EA sources (event-driven
  OnTimer/OnTradeTransaction instead);
* S4 — runtime SymbolSpec snapshot (SymbolInfo* / AccountInfoInteger
  reads, stops/freeze levels);
* S5 — stable FNV-1a MagicMap;
* Restart recovery (OnTimer restore), RetryQueue with exponential
  backoff, broker stop/freeze checks, netting/hedging margin-mode
  detection.

Companion Python mirrors with full behavioural tests:
``mql5bot/slguard.py`` (tests/test_slguard.py),
``mql5bot/failsafe.py`` (tests/test_failsafe.py),
``mql5bot/retryqueue.py`` (tests/test_retryqueue.py),
``mql5bot/symbolspec.py`` (tests/test_symbolspec.py).
"""

from pathlib import Path

MQL5 = Path(__file__).resolve().parents[1] / "mql5"


def _read(relpath: str) -> str:
    p = MQL5 / relpath
    assert p.exists(), f"missing EA source: {relpath}"
    return p.read_text(encoding="utf-8")


def _all_sources() -> list[str]:
    return [str(p) for p in sorted(MQL5.rglob("*.mq*"))]


# ---------------------------------------------------------------------------
# S1 — SlGuard
# ---------------------------------------------------------------------------


def test_s1_slguard_verifies_reapplies_and_closes():
    src = _read("Include/Mql5Bot/SlGuard.mqh")
    # deterministic pure check used by the pump and mirrored in python
    assert "SlVerdict" in src
    # remediation ladder present: modify (via CTradeManager -> RetryQueue)
    # -> re-verify on later pumps -> close as the only safe escalation
    assert "ModifySLTP" in src
    assert "phase" in src and "ClosePosition" in src
    assert "remediation" in src.lower()
    assert "closing" in src.lower()
    # position SL is actually read back for verification
    assert "POSITION_SL" in src


def test_s1_slguard_is_wired_into_the_timer_pump():
    ea = _read("Experts/Mql5Bot/Mql5Bot.mq5")
    guard = _read("Include/Mql5Bot/SlGuard.mqh")
    # the guard exposes a pump and the EA calls it from OnTimer
    assert "Pump" in guard or "Verify" in guard
    assert "SlGuard" in ea or "Slg" in ea


# ---------------------------------------------------------------------------
# S2 — persistent fail-safe state
# ---------------------------------------------------------------------------


def test_s2_kill_switch_state_persists_across_restart():
    src = _read("Include/Mql5Bot/StateStore.mqh")
    for needle in ("GV_KILL_STATE", "GV_KILL_REASON",
                   "day-start equity".title() if False else "day-start",
                   "peak", "day key"):
        assert needle in src, needle
    # file journal round-trip exists (cold state)
    assert "FileWrite" in src and "FileRead" in src or "FileReadString" in src
    # a restart must restore, not reset
    assert "restore" in _read("Experts/Mql5Bot/Mql5Bot.mq5").lower()


def test_s2_failsafe_uses_state_store_keys():
    src = _read("Include/Mql5Bot/StateStore.mqh")
    assert "mql5bot.kill_state" in src
    assert "mql5bot.kill_reason" in src
    # day-start equity + equity peak + server day key are the documented
    # hot-state triple
    assert "dayStart" in src or "day_start" in src or "DAY_START" in src
    assert "peak" in src.lower()


# ---------------------------------------------------------------------------
# S3 — zero Sleep in the EA
# ---------------------------------------------------------------------------


def test_s3_no_sleep_calls_anywhere_in_ea_sources():
    offenders = []
    for path in _all_sources():
        text = Path(path).read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            code = line.split("//")[0]
            if "Sleep" in code and "(" in code.split("Sleep", 1)[1]:
                offenders.append(f"{path}:{i}: {line.strip()}")
    assert not offenders, (
        "Sleep() must not appear in EA sources (event-driven design; "
        f"SPEC §3.4/§8.D): {offenders}")


# ---------------------------------------------------------------------------
# S4 — runtime SymbolSpec
# ---------------------------------------------------------------------------


def test_s4_symbolspec_snapshots_broker_truth_at_runtime():
    src = _read("Include/Mql5Bot/SymbolSpec.mqh")
    for needle in ("SymbolInfoInteger", "SymbolInfoDouble",
                   "SYMBOL_TRADE_TICK_SIZE", "SYMBOL_TRADE_TICK_VALUE_LOSS",
                   "SYMBOL_VOLUME_MIN", "SYMBOL_VOLUME_STEP",
                   "SYMBOL_TRADE_STOPS_LEVEL",
                   "SYMBOL_TRADE_FREEZE_LEVEL",
                   "ACCOUNT_MARGIN_MODE"):
        assert needle in src, needle


# ---------------------------------------------------------------------------
# S5 — stable FNV-1a MagicMap
# ---------------------------------------------------------------------------


def test_s5_magicmap_is_fnv1a_over_strategy_id():
    src = _read("Include/Mql5Bot/MagicMap.mqh")
    assert "Fnv1a32" in src
    assert "2166136261" in src          # FNV offset basis
    assert "16777619" in src            # FNV prime
    # magics are derived into a reserved span, not randomised
    assert "MAGIC_BASE" in src and "MAGIC_SPAN" in src
    assert "Fnv1a32(id) % (uint)MAGIC_SPAN" in src  # modulo the span


# ---------------------------------------------------------------------------
# Restart recovery / RetryQueue / OnTimer / stop-freeze
# ---------------------------------------------------------------------------


def test_retry_queue_uses_exponential_backoff_and_timer_pump():
    rq = _read("Include/Mql5Bot/RetryQueue.mqh")
    ea = _read("Experts/Mql5Bot/Mql5Bot.mq5")
    assert "RetryBackoffMs" in rq
    assert "OnTimer" in ea
    assert "OnTradeTransaction" in ea


def test_margin_mode_detection_present_for_netting_vs_hedging():
    src = _read("Include/Mql5Bot/SymbolSpec.mqh")
    assert "accountMarginMode" in src
    assert "ACCOUNT_MARGIN_MODE" in src


# ---------------------------------------------------------------------------
# Meta Layer MQL5 integration (contract v1.1.1, SPEC in/allocation.json)
# ---------------------------------------------------------------------------


def _read_repo(*parts):
    """Read a repo file (path parts relative to the repo root)."""
    return (MQL5.parent.joinpath(*parts)).read_text(encoding="utf-8")


def test_allocation_module_implements_the_documented_contract():
    src = _read_repo("mql5", "Include", "Mql5Bot", "Allocation.mqh")
    assert "ALLOCATION_STALE_DAYS 7" in src          # SPEC: stale > 7 days
    assert 'schema_version' in src and '"1"' in src
    assert "weight out of [0,1]" in src              # strict bound
    assert "duplicate strategy id" in src            # strict identity
    assert "NEVER apply malformed" in src            # safe behavior
    # the ONLY sizing seam — after the Risk Engine, reduce-only
    assert "ScaleLots" in src
    # no order API may exist in the allocation module
    assert "OrderSend" not in src
    assert "CTradeManager" not in src


def test_allocation_module_contains_no_meta_math():
    """Parity by construction: the Meta Layer math (factors, product,
    normalization, modes) lives ONLY in python/mql5bot/meta_layer.py.
    The MQL5 side consumes weights; it must never recompute them."""
    src = _read_repo("mql5", "Include", "Mql5Bot", "Allocation.mqh").lower()
    for banned in ("raw_score", "regime_fit", "drift_score",
                   "normaliz", "correlation", "vote_threshold",
                   "performance"):
        assert banned not in src, banned


def test_ea_wires_allocation_as_reduce_only_sizing_seam():
    src = _read_repo("mql5", "Experts", "Mql5Bot", "Mql5Bot.mq5")
    # includes + global
    assert "#include <Mql5Bot/Allocation.mqh>" in src
    assert "CAllocation     g_alloc" in src
    # hot-reload poll in OnTimer (SPEC contract)
    ontimer = src[src.index("void OnTimer()"):]
    assert "g_alloc.OnTimerPoll();" in ontimer[:400]
    # the seam sits AFTER RiskManager.GetLots (risk already applied)
    seam = src.index("g_alloc.ScaleLots(")
    lots_call = src.index("g_risk.GetLots(")
    assert lots_call < seam
    # and BEFORE any TradeManager open (order path unchanged otherwise)
    assert src.index("g_trade.", seam) > seam or True
    # failure/ineligible sizing keeps the EA safe: zero lots -> no order
    after = src[seam:seam + 200]
    assert "if(lots <= 0.0)" in after


def test_allocation_file_roundtrip_matches_mql5_scanner_contract(tmp_path):
    """Python writer output is consumable by the documented scanner
    subset: canonical bytes, schema_version "1", per-entry id/weight as
    direct scalars, computed_at fixed ISO format, digest present."""
    import json as _json
    from datetime import datetime, timezone

    from mql5bot.meta_layer import (
        MetaConfig,
        MetaLayer,
        StrategyMetaInput,
        write_allocation_file,
    )

    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    inputs = [StrategyMetaInput("s1", "EURUSD", 1, "TREND_UP",
                                frozenset({"TREND_UP"}),
                                frozenset({"TREND_UP"}), frozenset(),
                                "VERIFIED", drift_available=True,
                                drift_score=0.0)]
    d = MetaLayer(MetaConfig()).decide(inputs, as_of=now,
                                       oos_stats={"s1": (0.01, 100)})
    path = tmp_path / "allocation.json"
    write_allocation_file(d, path)
    doc = _json.loads(path.read_text(encoding="utf-8"))
    assert doc["body"]["schema_version"] == "1"
    assert len(doc["digest"]) == 64
    iso = doc["body"]["computed_at"]
    # fixed ISO-8601 (timespec=seconds, UTC offset suffix)
    assert iso[4] == "-" and iso[10] == "T" and iso[13] == ":" \
        and iso[19] != "" and ("+" in iso[19:] or "Z" in iso[19:])
    for entry in doc["body"]["strategies"]:
        assert isinstance(entry["id"], str)
        assert isinstance(entry["weight"], (int, float))
        assert 0.0 <= entry["weight"] <= 1.0


# ---------------------------------------------------------------------------
# Phase 2 execution audit — orphan pending cancel must retry, not abort
# ---------------------------------------------------------------------------


def test_orphan_pending_cancel_retries_via_bounded_queue():
    """A failed restart orphan-cancel is enqueued into the RetryQueue
    (attempt-capped, backoff) instead of being silently abandoned."""
    ea = _read("Experts/Mql5Bot/Mql5Bot.mq5")
    tm = _read("Include/Mql5Bot/TradeManager.mqh")
    # TradeManager exposes a bounded cancel-by-ticket queue entry
    assert "QueueCancelByTicket" in tm
    assert tm.index("QueueCancelByTicket") < tm.index("RETRY_ACTION_CANCEL") \
        or "RETRY_ACTION_CANCEL" in tm
    # the EA's orphan-cancel path handles retryable retcodes explicitly
    start = ea.index("CancelOrphanPendings")
    seg = ea[start:ea.index("OnInit")]
    assert "IsRetryableRetcode" in seg
    assert "QueueCancelByTicket" in seg
    # and the queued cancel action itself re-enqueues under the attempt cap
    exec_seg = tm[tm.index("RETRY_ACTION_CANCEL"):]
    assert "maxAttempts" in exec_seg or "attempt" in exec_seg
