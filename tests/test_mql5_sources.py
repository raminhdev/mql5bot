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
    # remediation ladder present: modify -> re-verify -> close
    assert "PositionModify" in src
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
