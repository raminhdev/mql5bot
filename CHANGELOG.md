# Changelog

All notable changes to mql5bot are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — Aegis Release A foundation (audit + canonical risk models + Phase-1 MQL5 hardening)

### AEGIS research — Phase 1–2 (headless compile + tester tooling)
- `tools/compile.ps1` — MetaEditor compile round-trip: locates
  `metaeditor64.exe` (explicit/env/registry/`origin.txt` portable roots/
  Program Files/Start-menu/PATH), installs repo `mql5/` sources into the
  resolved MT5 data folder, compiles every EA/script under
  `Experts\Mql5Bot` + `Scripts\Mql5Bot`, gates on real compiler output
  (fresh `.ex5` + verbatim log), fails on errors and on warnings with
  `-Strict`; one reproducible combined log (`logs/compile-<stamp>.log`,
  SHA-256 of produced `.ex5` files).  Owner round-trip required: no
  MetaEditor in this sandbox.
- `python/mql5bot/mt5tester.py` — headless Strategy Tester core: `.set`
  parse/render with optimization ranges (`||start||step||stop||Y/N`)
  preserved verbatim; deterministic `[Tester]`+`[TesterInputs]` ini
  generation; locale-tolerant MT5 HTML tester-report parser → canonical
  typed metrics (`settings`/`fields`/`metrics`; raw pairs never lost);
  Windows-guarded sequential run/batch with timeout, raw-report
  preservation and JSON artifacts.
- `tests/test_mt5tester.py` — 23 tests: preset round-trips, ini golden
  lines, config determinism/rejection matrix, report parsing incl.
  composite drawdown/won-% rows and old-style labels (no terminal needed).
- `tools/run_mt5_backtest.py` — CLI: `generate-set` / `generate-ini` /
  `matrix` (strategy × symbol × timeframe jobs) / `parse` / `run` /
  `batch`; exit codes 0/1/2/3 documented.  `tools/run_mt5_backtest.ps1` —
  strict logged PowerShell wrapper for the owner/Windows runner.
- `tools/README.md` — usage docs: compile round-trip, determinism
  contract, report parsing, owner round-trip protocol, troubleshooting.
- Suite now 143 tests (`pytest tests/` green in this environment).

### Added
- `docs/IMPLEMENTATION_AUDIT.md` — full evidence-based audit of the repository
  against `docs/SPEC.md` (v4): architecture, implemented features, release
  readiness (A ≈ 25–30 %, B–E 0 %), missing/broken requirements, safety-critical
  gaps (ranked S1–S11), and the exact recommended implementation order.
- `docs/DECISIONS.md` — decisions log (SPEC §24): layout-preservation decision,
  Python-first canonical model decision, SPEC §19 reconciliation, version
  naming; carries the earlier decisions from HANDOFF §4.
- `python/mql5bot/symbolspec.py` — canonical broker `SymbolSpec` + pure
  normalisers (tick rounding, stops-level enforcement, volume min/max/step/
  limit, profit-currency loss-per-lot) + FNV-1a 32-bit magic derivation with a
  persistent, collision-safe `MagicRegistry` (SPEC §3.3/§3.9/§3.10 seed).
- `python/mql5bot/sizer.py` — canonical risk sizer on injected specs: fixed
  lot, risk % equity/balance, fixed money, Kelly capped at 0.25 (off by
  default); floor-to-step volume (never over-risk), below-min rejection,
  max/limit clamping, injected margin-calc reduce/reject (SPEC §8.C).
- `tests/test_symbolspec.py`, `tests/test_sizer.py` — 41 new tests incl. the
  five synthetic broker specs (EURUSD 5-digit, USDJPY, XAUUSD, US30-like,
  BTCUSD-like), FNV-1a vectors, registry stability across removal/reload,
  margin rejection, risk-budget invariant sweep.
- Suite now 80 tests (`pytest tests/` green in this environment).

### MQL5 hardening — Phase-1 DoD (S4 SymbolSpec)
- `mql5/Include/Mql5Bot/SymbolSpec.mqh` — MQL5 port of the canonical broker
  `SymbolSpec`: runtime `BuildSymbolSpec` querying every broker fact
  (SPEC §3.3), tick-grid/volume/stop normalisers and loss-per-lot math
  (SPEC §3.10) byte-parallel to `python/mql5bot/symbolspec.py`; the pure
  helpers are verified by the existing synthetic-spec test vectors
  (`tests/test_symbolspec.py`) on the Python side, which the port mirrors.

### MQL5 hardening — Phase-1 DoD (S5 MagicMap)
- `mql5/Include/Mql5Bot/MagicMap.mqh` — stable per-strategy identity: FNV-1a
  32-bit hash of `strategy_id` into the reserved magic range
  [16777216, 17825791] (SPEC §3.9, DoD #21) with a persistent, strict-format
  `MAGICMAP v1` registry (`mql5bot/State/magicmap.txt`) so reloads, removals
  and re-adds never reassign magics; collisions probe to the next free slot.
  FNV vectors are pinned on the Python side in `tests/test_symbolspec.py`.

### MQL5 hardening — Phase-1 DoD (S1 SL remediation)
- `mql5/Include/Mql5Bot/SlGuard.mqh` — post-fill stop-loss enforcement
  (SPEC §3.2): pure `SlVerdict` (present, correct side, outside broker
  stops level) drives a sleep-free verify → one modify → re-verify → close
  pump from OnTimer; a position the guard can neither protect nor close
  escalates to the caller (CRITICAL + alert + `ENGINE_HALT`).
- `python/mql5bot/slguard.py` + `tests/test_slguard.py` — mirror of
  `SlVerdict` with a verdict matrix on the five synthetic broker specs and
  pinned pump-threshold invariants (the MQL port's acceptance tests).
- Trade operations go through the Sleep-free `CTradeManager` API
  (`ClosePosition(ticket, vol)` / `ModifySLTP(ticket, sl, tp)`) that lands
  with the RetryQueue commit; until then the guard is not wired into the EA.

### MQL5 hardening — Phase-1 DoD (S2 kill-switch persistence)
- `mql5/Include/Mql5Bot/StateStore.mqh` — crash-safe persistence of the
  fail-safe state: GlobalVariables carry the hot kill-switch state, reason,
  day key, day-start equity and equity peak; a strict `AEGIS_STATE v1`
  file carries the ticket registry with per-`POSITION_IDENTIFIER`
  management flags (`partialDone`, `beDone`). Restart NEVER resets the
  daily loss or forgets the drawdown peak (SPEC DoD #13/#14).
- `mql5/Include/Mql5Bot/RiskManager.mqh` — risk engine rewritten on the
  injected `SSymbolSpec`: mode-aware sizing over the enforced stop
  distance (FixedLot / RiskPercentOfEquity / RiskPercentOfBalance /
  FixedMoney / capped Kelly ≤ 0.25), runtime profit→deposit conversion,
  broker min/max/limit volume normalisation (never round up), margin check
  via `OrderCalcMargin` with bounded scale/walk-down, and the persisted
  state machine: `AdoptState` on startup, `SetState` hot-saves immediately,
  daily-loss pause expires only at the day rollover, drawdown breach trips
  `ENGINE_HALT` (explicit reset only).
- `mql5/Include/Mql5Bot/Config.mqh` — shared `ENUM_ENGINE_STATE` and
  success/retryable/fatal retcode classifiers for the execution rewrite.
- `mql5/Include/Mql5Bot/PositionGuard.mqh` — partial scale-out is now
  once-per-position across restarts via the persisted `partialAlreadyDone`
  flag (the in-process disarm already existed).
- `python/mql5bot/failsafe.py` + `tests/test_failsafe.py` — mirror of the
  state machine (rollover/guard/reset transition rules) and the strict
  `AEGIS_STATE v1` row codec (quarantine/malformed-row semantics).

### MQL5 hardening — Phase-1 DoD (S3 RetryQueue / Sleep removal)
- `mql5/Include/Mql5Bot/RetryQueue.mqh` — bounded sleep-free retry engine:
  32 slots, exponential backoff 500 ms × 2^n capped at 10 s, hard attempt
  cap, same-operation dedupe (action+symbol+ticket+comment) that refreshes
  the schedule without resetting the cap.
- `mql5/Include/Mql5Bot/TradeManager.mqh` — execution rewritten without a
  single `Sleep`: one attempt per call, a single REQUOTE re-send with a
  refreshed price, the bounded FOK→IOC→RETURN filling chain, verify-before-
  resend against deal history on TIMEOUT/RETRY, latency/slippage capture
  and one structured `[mql5bot] EXEC|…` audit line per action; close and
  SL/TP modify go through the same queue. Pending placement/cancel expire
  by bars with queued cancellation.
- `mql5/Experts/Mql5Bot/Mql5Bot.mq5` — EA wired to the hardened engine:
  OnTimer scheduler (queue pump, orphan-pending cancellation, ticket-
  registry sync + adoption, SL-protection pass, equity-limit checks, guard
  pump, state flush, heartbeat), 10 s kill-switch close cadence, entry
  gate chain on new bars, `ENUM_ENGINE_STATE` start-up adoption with the
  explicit one-shot kill-switch reset, FNV-1a magic allocation, input
  validation on `OnInit` (INIT_PARAMETERS_INCORRECT).
- `python/mql5bot/retryqueue.py` + `tests/test_retryqueue.py` — mirror of
  the backoff schedule and queue semantics (dedupe-without-reset, earliest-
  due pop, bounded slots).

### AEGIS research — Phase 1/4/5 canonical portfolio engine (python)
- `python/mql5bot/engine.py` — deterministic multi-position portfolio
  engine (netting and hedging): one book per symbol in netting (same-side
  merges keep per-leg attribution with a lots-weighted book SL/TP;
  opposite-side desires offset legs FIFO at the open and any remainder
  opens fresh), independent per-(symbol, strategy) books in hedging;
  `allow_signal_exit` flips, per-strategy risk overrides and explicit
  exposure caps (total / per-strategy positions, per-symbol / corr-group /
  currency notional shares, portfolio heat) evaluated on the post-action
  portfolio with rejection events.  Tick-valued PnL with profit-side tick
  values and profit→deposit conversion; sizing exclusively through
  `mql5bot.sizer` (no direct risk/stop/contract formula — guarded by a
  source test); server-time day rollovers with swap at boundaries,
  day-start daily-loss snapshot and drawdown kill switch (checks act at
  the bar open on prior-close equity); walk-forward `schedule` freezes
  params per segment; valuation/bar-order contract documented in the
  module docstring.
- `python/mql5bot/symbolspec.py` — `SymbolSpec` gains the optional
  profit-side tick value (`tick_value_profit`, default `None` = symmetric)
  and `tick_value(side, move)` (gains on the profit side, losses on the
  loss side).
- `tests/test_engine.py` — 29 tests: canonical-path source guard, tick
  value profit side, netting merge/partial-FIFO/full-offset/flip
  semantics, hedging simultaneous books, Phase-4 exposure caps,
  multisymbol notional with conversions, server-day daily-loss reset,
  permanent drawdown kill switch, variable spread / reject mask / gap /
  swap / round-trip commission / margin rejection, fixed-lot and
  below-min rejection, max-bars and trailing ratchet, walk-forward
  schedule freeze, engine validation.
- Suite: **172 tests** green in this environment (`pytest tests/`).

### Notes
- Suite: **143 tests** green in this environment (`pytest tests/`).
- Phase-1 DoD for this branch is complete (S4 SymbolSpec, S5 MagicMap, S1
  SL remediation, S2 kill-switch/day-loss/DD persistence, S3 RetryQueue /
  no-Sleep execution); status board + residual gaps in
  `docs/IMPLEMENTATION_AUDIT.md` §18.
- AEGIS research Phases 1–2 tooling is committed but **NOT verified on a
  Windows terminal** (no MetaEditor / terminal64.exe in this sandbox):
  `tools/compile.ps1 -Strict` and `tools/run_mt5_backtest.ps1 run|batch`
  require the owner round-trip before any compile/backtest claim.
- "MQL5 COMPILE RESULT: COMPILE NOT VERIFIED — MetaEditor unavailable in
  this environment." Owner-side compile + zero-warning pass and a strategy-
  tester run are still required (HANDOFF §10, audit §18).

## [1.0.0] — 2026-09-04

### Added

**MQL5 Expert Advisor** (`mql5/`)
- `Mql5Bot.mq5` main EA with 5 strategies: EMA crossover, RSI reversal,
  Donchian breakout, Bollinger reversal, MACD momentum
- `RiskManager.mqh` — risk-based position sizing, daily loss limit,
  drawdown kill-switch, spread guard
- `TradeManager.mqh` — market & pending stop-order execution with retry
  logic, fill verification via deal history, hedging/netting safe
- `PositionGuard.mqh` — ATR trailing stop, breakeven, partial scale-out
- `SignalEngine.mqh` — completed-bar-only strategy evaluation (no repaint)
- `Session.mqh` — days-of-week bitmask + intraday trading window
- `Logger.mqh` — leveled file + terminal logging
- `Telemetry.mqh` — HTTP heartbeat/trade/alert reporting (WebRequest)
- `Mql5BotDownloadData.mq5` script — export bar history to CSV for the
  Python toolkit
- Presets for all 5 strategies (`mql5/Presets/Mql5Bot/`)

**Python quant toolkit** (`python/mql5bot/`)
- Vectorized strategy twins with an identical evaluation contract
- Event-driven backtest engine: lookahead-proof entries, intrabar stop
  simulation, spread/slippage/commission cost model, risk-based sizing,
  trailing/breakeven/partial exits, daily-loss & drawdown kill switches
- Performance metrics: CAGR, Sharpe, Sortino, max drawdown & duration,
  Calmar, win rate, profit factor, payoff, expectancy
- Grid-search optimiser (multiprocessed) and walk-forward validation
- Self-contained interactive HTML reports
- Live web dashboard with simulated or MT5-bridged bar feed
- Telemetry bridge — HTTP collector for EA events (JSONL + SSE stream)
- CLI (`mql5bot`) with data / backtest / compare / optimize / walkforward /
  dashboard subcommands
- Reproducible synthetic OHLC generator, CSV loader, live MT5 bridge

**Tooling & QA**
- 36-test pytest suite, including a hard no-lookahead oracle test and an
  exact commission-accounting test
- GitHub Actions CI: test matrix (Python 3.10–3.12) + CLI smoke test
- `scripts/install_mql5.py` — one-command deployment into the MT5 data
  folder (auto-detection on Windows/macOS/Linux-Wine)

[1.0.0]: https://github.com/raminhdev/mql5bot/releases/tag/v1.0.0
