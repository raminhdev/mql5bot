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
- Suite: **198 tests** green in this environment (`pytest tests/`
  --collect-only = 198; 169 at the pre-engine tree + these 29).

### AEGIS research — Phase 6 continuous walk-forward (python)
- `python/mql5bot/optimizer.py` — `walk_forward` rewritten on the engine's
  scheduled-parameter run: ONE continuous backtest over the full sample
  (capital/portfolio/costs/risk carried forward — the legacy concatenating
  per-window runs with capital resets are gone).  Rolling-origin IS
  windows feed per-window best params, frozen per OOS segment via
  `schedule=(oos_start - 1, params)`; geometry is documented
  (`warmup_bars`, `is_bars`, equal `segment_bars`, remainder absorbed by
  the last OOS segment); bars before the first OOS start warm the account
  with the registry defaults and are excluded from the OOS aggregates.
- Per-window reporting: IS dates, OOS dates, selected params, IS metrics,
  OOS metrics (continuous equity slice of the OOS span; trades attributed
  to the window of their ENTRY bar), WFE, OOS trade count, OOS max
  drawdown, cost and a price-regime breakdown (drift, annualised
  volatility, efficiency ratio, up-fraction, direction).
- `python/mql5bot/backtest.py` — `run_backtest` accepts the engine
  `schedule` passthrough (walk-forward freeze on the single-symbol path)
  and its trade rows now surface the engine's ledger columns.
- `python/mql5bot/engine.py` — trade rows gain two ledger columns: `fees`
  (entry + exit commission shares + allocated swap) and `costs` (`fees` +
  the tick-valued spread/slippage drag of both executions against the raw
  quote levels), so per-window/per-strategy cost accounting needs no fill
  replay.  Row PnL stays net.
- `tests/` — 203 tests green: engine ledger decomposition pinned exactly
  (7-tick surcharge x 2 legs on a flat round trip), walk-forward windows
  tile the OOS region contiguously, aggregate OOS equity is the unique
  continuous run over the OOS bars (no 10k resets), per-window reporting
  fields, too-little-data ValueError.

### AEGIS research — Phase 7 WFA leakage controls (python)
- `python/mql5bot/optimizer.py` — `walk_forward` gains two SELECTION-only
  leakage controls (signals in the continuous run always use everything
  already released):
  * `embargo_bars`: the IS selection window ends that many bars before the
    OOS start, so parameter choice never scores the bars adjacent to the
    test boundary (their trades would be force-closed at the boundary in
    an isolated run); geometry exposes `embargo_bars`/`purge_bars` and
    `train_end` moves with the embargo.
  * `purge_bars`: boundary-censored trades (those exiting within the last
    `purge_bars` of the embargoed IS window) are dropped from the IS
    metrics together with the equity tail carrying them; the number
    dropped is reported per window as `is_trades_purged`
    (`_selection_metrics` is unit-tested directly).
- `tests/test_strategies_optimizer.py` — automated leakage tests: per-window
  embargo geometry exactness; selection IS bars strictly before each OOS
  start; purge unit scenario (an isolated run force-closes its open
  position at the slice boundary with `end_of_data` and the purge drops
  exactly that trade); validation raises; and a signal-level causality
  test for every registered strategy (signal prefixes must be unchanged
  when the frame is truncated at a probe bar — no lookahead, which is what
  frozen OOS signals rely on).
- Suite: **207 tests** green in this environment (`pytest tests/` exit 0).

### AEGIS research — Phase 8 metrics upgrade (python)
- `python/mql5bot/metrics.py` — `compute_metrics` now returns the Phase-8
  statistics on top of every legacy key (nothing removed, empty report
  schema extended to match):
  * drawdown/return quality: `recovery_factor` (net return / |max DD|),
    `ulcer_index_pct` (rms of the drawdown series), `downside_deviation_pct`
    (semi-deviation, annualised, of intraday-return proxy).
  * tail risk: `var_95_pct`/`cvar_95_pct` and `var_99_pct`/`cvar_99_pct`
    from the empirical (unannualised) return distribution.
  * stability: `rolling_sharpe_median`/`rolling_sharpe_worst` on a
    half-period (50% of periods-per-year) rolling window; monthly
    consistency via `monthly_win_rate_pct`, `monthly_avg_pct`,
    `monthly_std_pct` over the existing `monthly_returns` resample.
  * trade-profile: `avg_trade`/`median_trade` (pnl per round trip) and
    `avg_trade_bars`/`median_trade_bars` (bars in market), `avg_win`/
    `avg_loss` unchanged.
  * capital efficiency: `exposure_pct` (union of in-market bars) and
    `turnover_pct` (closed-lot bars / total in-market bars), both as
    best-effort approximations tolerant of malformed log rows.
  * robustness/concentration: `max_consecutive_losses`,
    `return_concentration_hhi` (Herfindahl on |pnl| shares),
    `top5_trades_pct` (share of net pnl from the 5 best trades),
    `expectancy_last20`/`win_rate_last20_pct` (trailing-20 per-trade
    stats).  A `window = max(20, round(periods_per_year * 0.5))` helper is
    shared with the rolling calculation and regression is guarded by the
    `_r` value formatter staying on 4 dp.
- `tests/test_metrics.py` — 9 new hand-pinned tests (new dedicated file;
  every statistic checked against a directly recomputed fixture on small
  deterministic inputs; empty/short-series schema completeness included).
  Total suite: **216 tests** green (`pytest tests/` exit 0), ruff clean on
  changed files.

### AEGIS research — plan 0–8 gate closure (python)
- Owner pasted the canonical 0–20 execution plan; this section closes the
  exit-criteria gaps the gate audit found in the already-built research
  stack (plan phases 1–8 otherwise PASS with evidence).
- `python/mql5bot/costs.py` — four deterministic cost profiles via
  `cost_profile()`: `ZERO` (cost-free), `BASE`, `STRESSED`, `SEVERE`,
  escalating field-by-field (spread, slippage, commission + minimum, swap
  long/short, gap limit); profiles never inject a reject mask.  Tests pin
  preset values, determinism and validation; an engine integration test
  runs one identical round trip under all four and asserts ZERO costs
  zero and the ledger outcome is strictly monotone BASE < STRESSED <
  SEVERE at equal volume.
- `python/mql5bot/optimizer.py` + `strategies.py` — every walk-forward
  window now records `param_hash` (deterministic sha-1 of the selected
  params), `strategy_version` (declared in `STRATEGY_VERSIONS`,
  "undeclared" for ad-hoc registry entries; `list_strategies()` exposes
  it) and `dataset_version` (sha-1 content digest of the frame unless the
  caller passes an explicit tag); both tags repeat at the top level.
  `strategies.py` legacy ruff findings cleaned while touched.
- `tests/test_leakage_features.py` — adversarial future-data pins (plan
  Phase 8): extreme values injected into bars >= PROBE must not move any
  earlier output — parametrised over EMA/SMA/rolling std/RSI/ATR/
  Bollinger/Donchian/MACD/highest/lowest/crossover, every registered
  strategy signal, and per-span regime features (out-of-span mutation
  leaves the report identical; in-span mutation moves it — guard against
  vacuous tests).
- `docs/STATE_MODEL.md` (plan 4) — A market/account, B strategy, C
  research/training state classes mapped to engine objects, with carry
  rules and python lifecycle/restart semantics documented.
- `docs/WFA_CONTRACT.md` (plan 6) — mathematical contract of the
  implemented continuous walk-forward: exact interval geometry,
  freeze timing, CARRY_ALLOWED default / FORCE_FLAT never silently
  enabled, knowledge non-transfer, causal warmup, entry-bar attribution
  and continuous-ledger aggregation.
- Suite: **239 tests** green (`pytest tests/` exit 0), ruff clean on all
  changed files.

### AEGIS research — plan Phase 10: fast research engine benchmark (python)
- `python/mql5bot/perf.py` — deterministic measurement instruments:
  `ema_grid_axes` (factorises a requested parameter-set count into a valid
  fast/slow EMA grid), `single_run_metrics` (untimed wall/throughput
  measurement), `grid_metrics` (end-to-end grid_search timing at any
  `n_jobs` with parent-retention memory estimate via a capped 300-set
  tracemalloc probe scaled linearly) and `grid_signature` (top-N
  params+metric records for equivalence checks).  First cut timed under
  tracemalloc (~4x inflation) — fixed: timing runs clean.
- `tools/benchmark_research.py` — data-load + single-run + 100/1,000/
  10,000-set grid ladder at `n_jobs = 1` vs `n_jobs = cores`, reporting
  speedup, runs/sec, bars/sec, trades/sec, peak memory and a PASS/FAIL
  numerical-equivalence line; JSON export.
- `tests/test_perf.py` — axes factorisation, report shapes, and the
  parallel path reproducing the sequential ordering and values exactly.
- Measured evidence (480-bar synthetic hourly frame, seed 42, 2 cores,
  ema_crossover defaults): single run 22.6 ms (~21.3k bars/s, ~665
  trades/s); grid 100 sets seq 2.21 s / par 1.85 s, 1,000 sets seq
  22.2 s / par 18.6 s, 10,000 sets seq 296 s / par 250 s — parallel
  speedup 1.20x/1.19x/1.18x at 2 cores (~40 runs/s at 10k); parent
  retention ~90 MB estimated at 10k; equivalence PASS at every size.
  Further FAST-engine optimisations (indicator caching, pruning,
  vectorisation passes) are Phase-18 items to be measured the same way.
- Suite: **245 tests** green in this environment (`pytest tests/` exit 0),
  ruff clean on changed files.

### AEGIS research — plan Phase 11: statistical robustness gates (python)
- `python/mql5bot/robustness.py` — deterministic, seeded validation gates
  (research gates, not cosmetic report fields), each pinned by synthetic
  known-good/known-bad tests in `tests/test_robustness.py` (13 tests):
  * `psr` / `deflated_sharpe` — probabilistic and deflated Sharpe; DSR
    discounts honest trial multiplicity (n_trials=1 -> no discount).
  * `monte_carlo_pnl` — trade resampling: net-profit distribution,
    probability of a profitable path, percentile bands.
  * `perturbation_report` — parameter perturbation / systematic parameter
    permutation with a location-free flatness ratio (median-worst)/
    (best-worst) that exposes curve-fit spikes.
  * `combinatorial_purged_cv` + `probability_of_backtest_overshoot` —
    CPCV over configurations with an embargo control and the PBO
    estimate; calibrated edge-vs-noise separation across seeds.
  * `white_reality_check` / `hansen_spa` — multiple-testing reality
    checks via a seeded stationary bootstrap (fresh uniform origin per
    block; an early chained-origin version had zero bootstrap variance
    and was fixed); SPA is a documented studentised simplification.
  * `stamp_report` — every robustness report carries method, strategy,
    strategy_version and dataset_version (plan exit gate).
- Purge/embargo/WFA validation methods were already delivered in Phases
  6-8 with their leakage tests; Phase 11 therefore passes its gate.
- Suite: **258 tests** green (`pytest tests/` exit 0), ruff clean on all
  changed files.

### AEGIS research — plan Phase 12: portfolio research (python)
- `python/mql5bot/portfolio.py` — deterministic strategy-portfolio tools
  with 7 pinned tests in `tests/test_portfolio.py`:
  * `returns_frame` (aligned per-period returns), `correlation_matrix` /
    `covariance_matrix` (valid: symmetric, unit diagonal, finite),
    `portfolio_volatility` (pinned against direct numpy), `equal_weight`,
    `concentration_hhi`.
  * `currency_exposure` (per-profit-currency notional shares via the
    canonical specs) and `portfolio_heat` (gross notional / equity).
  * `strategy_overlap` — pairwise Jaccard overlap of in-market bars per
    symbol over engine trade ledgers (full/none/partial scenarios pinned,
    inclusive exit bars).
  * `apply_limits` — allocation veto against max_weight / currency caps:
    rejected proposals return the input untouched (zero accounting
    impact).  Execution-time caps remain enforced by the engine
    (per-symbol/currency/corr-group notionals, heat, position counts —
    test_engine.py), so portfolio limits cannot be exceeded.
- Suite: **265 tests** green (`pytest tests/` exit 0), ruff clean on all
  changed files.

### Performance & selection hardening — Phase A: repair verifiability (python)
- `pyproject.toml` — `pythonpath = ["python"]` under `[tool.pytest.ini_options]`
  so plain `pytest` from the repo ROOT works without installing the package
  (verified in a venv with mql5bot uninstalled); `bench` marker registered.
- `ruff check python tests` — fully clean (31 findings fixed: dead imports
  removed, `dict()` literals, unused `noqa` directives, quoted-annotation
  cleanup, unused locals, one RUF059 unpack; the two `BLE001` blind
  `except Exception` sites in dashboard.py are HTTP/refresh boundary
  handlers, narrowed to explicit exception types first with a documented
  guarded fallback that always surfaces the error).
- `tests/test_benchmark.py` (marked `bench`) — measurement harness:
  run_backtest wall + bars/sec + trades/sec, walk-forward s/window, peak
  memory; BEFORE table recorded in PROGRESS.md.
- Consumer audit of `exit_reason` / `max_drawdown_pct` documented in
  PROGRESS.md: cli/dashboard/report treat both as display-only; the
  Phase-4 re-pin (final reason `stop_loss`, DD band -9.0..-4.9) needs no
  consumer change.
- Suite: **268 tests** green from the repo root; ruff clean on `python/`
  and `tests/`.

### Notes






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
