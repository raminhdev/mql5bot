# PROGRESS — AEGIS Phase 2.5 / Research Foundation Correction

- Branch: `arena/01a06cdc-mql5bot`
- Plan: owner pasted the canonical **0–20 AEGIS execution plan** (new
  numbering supersedes the older TASKS/PROGRESS phase lists); phases are
  gated and executed in order, each with an evidence report.  Plan 0–8
  gate-audited against the committed research stack; the remaining plan
  gaps were closed in this session (see session log) — plan 0 baseline
  re-verified, gates 1–8 now PASS with evidence below.
- Tests: **265 passed** (pytest tests/ exit 0, /tmp/venv-mql5; ruff clean
  on changed files; 265 = 258 prior + 7 portfolio)
- Phase 9 (MT5 Truth Engine): **OPEN** — Windows/MetaEditor owner
  round-trip required (DECISIONS.md 2026-09-04 documents the parallel
  research protocol; python phases 10+ proceed, nothing claims MT5 truth)
- Phase 10 (fast research engine benchmark): measured evidence recorded in
  CHANGELOG (22.6 ms/run, ~21.3k bars/s, 100/1k/10k ladder, 1.18-1.20x
  parallel speedup at 2 cores, numerical equivalence PASS, ~90 MB parent
  retention at 10k sets); optimisation backlog (caching/pruning) deferred
  to Phase 18 with the same measurement harness
- Compile: **NOT VERIFIED** (no MetaEditor here; owner round-trip via
  tools/compile.ps1 — reported honestly, never guessed)

## Next 3 steps
1. MQL5-side metrics mirror (heartbeat JSON v2 with `total_return_pct`,
   `max_drawdown_pct`, `profit_factor`, `recovery_factor`, `ulcer_index`,
   `rolling_sharpe` etc.) + Aegis dashboard alignment — requires the
   owner round-trip (no MetaEditor here); python `metrics.py` is the
   canonical reference for the field list.
2. Optional: expose Phase-8 statistics in WFA/`optimizer.py` selection
   surface (cross-section ranking, robustness filters) now that
   `_selection_metrics` and walk-forward returns already carry full
   metric reports.
3. Sweep remaining phase backlog items listed in this file's phase
   checklists (verify against this file below).

## Phase A audit — exit_reason / max_drawdown_pct consumers (2026-09-04)
- Engine semantics (current): a DD-kill / daily-loss halt closes still-open
  books at the next open with `REASON_MAX_DRAWDOWN` / `REASON_DAILY_LOSS_LIMIT`;
  a position whose stop fills intrabar on the crossing bar exits as
  `stop_loss`.  The Phase-4 wrapper re-pin (tests/test_backtest.py
  test_max_drawdown_kill_switch) pins exactly that: final trade reason
  `stop_loss`, realised DD band loosened to -9.0..-4.9, halt acts at the
  open after the crossing close, no entry after the halt open.
- Consumer audit: `python/mql5bot/cli.py` (prints `max_drawdown_pct`,
  never reads `exit_reason`); `dashboard.py` (:120 renders the reason text
  in the trades table; :107 displays maxDD card); `report.py` (:99 renders
  `exit_reason` in the trade table; :131/:189 maxDD).  NO consumer branches
  on the reason vocabulary or on DD semantics — all display-only.  Impact
  of the re-pin on consumers: none (no code change needed); the reason
  vocabulary remains the engine's documented set
  (`EXIT_REASONS` in engine.py / costs.py).

## Benchmark harness — BEFORE table (2026-09-04, tests/test_benchmark.py, marked `bench`)
Row | value
--- | ---
run_backtest wall | 63.8 ms/run (3120 hourly bars)
bars/sec | 48,888
trades/sec | 1,457
peak memory (single run) | ~0.7 MB
walk_forward (2 windows, 2880 bars) | 0.32 s total = 0.16 s/window
grid 100 sets (seq / par-2) | 2.21 s / 1.85 s
grid 1,000 sets | 22.23 s / 18.64 s
grid 10,000 sets | 296.08 s / 250.02 s (~40 runs/s par)
equivalence parallel == sequential | PASS (all sizes)
Optimisation AFTER tables will be added here when phases C/D land.

- 2026-09-04: Phase-C milestone (FAST/TRUTH split): `fast_engine.py`
  NumPy-array single-line screening engine, wrapper-identical signature
  and result shape, reusing canonical sizer/costs/leg_cash math; scope
  gates raise NotImplementedError; equivalence pinned on 38 tests across
  5 strategies x cost/exit/halt/trail/partial knob sets + engine-style
  signal exits (random fixtures, exact trade rows, equity within 1e-8).
  Bench (3120 hourly bars, this sandbox, min-of-5):
  | engine | ms/run | bars/s | speedup |
  | --- | --- | --- | --- |
  | TRUTH run_backtest (BEFORE) | ~61-73 | 43k-51k | 1.0 |
  | FAST run_fast (AFTER) | ~38-42 | 75k-82k | ~1.6x |
  FAST results are screening-only, never final; certification remains
  TRUTH engine + MT5 tester.  Suite 312 tests green; ruff clean.
- 2026-09-04: Phase-B milestone (robust fitness): RobustFitnessConfig +
  composite_score pinned on hand fixtures; metric="composite" OPT-IN in
  grid_search/walk_forward with explicit config; OOS one-look policy
  documented; 273 tests green, ruff clean.
- 2026-09-04: Phase-A milestone (repair verifiability): root pytest via
  pythonpath, ruff clean python+tests, bench harness + BEFORE table,
  exit_reason/max_drawdown consumer audit; 268 tests green.
## Session log
## Session log
## Session log
- 2026-09-04: Phase-10 milestone: perf module + benchmark tool + tests
  committed; corrected benchmark measurement (untimed loops, scaled
  tracemalloc retention probe) and captured the phase evidence run
  (single run 22.6 ms ~21.3k bars/s; grid 100/1k/10k sets seq 2.2/22.2/
  296 s, par 1.9/18.6/250 s at 2 cores, equivalence PASS).  Phase-9
  blocker decision recorded in DECISIONS.md; 245 tests green.
## Session log
## Session log
## Session log
- 2026-09-04: Phase-B milestone (robust fitness): RobustFitnessConfig +
  composite_score pinned on hand fixtures; metric="composite" OPT-IN in
  grid_search/walk_forward with explicit config; OOS one-look policy
  documented; 273 tests green, ruff clean.
- 2026-09-04: Phase-A milestone (repair verifiability): root pytest via
  pythonpath, ruff clean python+tests, bench harness + BEFORE table,
  exit_reason/max_drawdown consumer audit; 268 tests green.
- 2026-09-04: Phase-12 milestone: portfolio research module (returns/
  correlation/covariance/vol, equal weight, HHI, currency exposure, heat,
  strategy overlap, allocation veto with zero-impact rejections) pushed;
  265 tests green.  Next: Phase 13 meta-layer.
- 2026-09-04: Phase-11 milestone: robustness gates module committed and
  pushed (PSR/DSR, trade MC, perturbation/SPP, CPCV+PBO, White RC/Hansen
  SPA, report stamping) with synthetic known-good/known-bad tests; 258
  tests green.
- 2026-09-04: Phase-10 benchmark milestone: perf module + tool committed
  (see log above); measured evidence recorded in CHANGELOG.
- 2026-09-04: Phase-9 blocker decision recorded (DECISIONS.md).
  Environment had been reset (local git truncated to base `817d20d`, 44
  dirty/untracked files, /tmp/venv gone): fetched origin, byte-verified
  all 75 files against `c0a49f6`, restored with `git reset --hard`, rebuilt
  /tmp/venv-mql5, re-verified 216 passed.  Phase-0 audit read
  HANDOFF/TASKS/PROGRESS/SPEC/IMPLEMENTATION_AUDIT/DECISIONS and traced
  engine/costs/dayclock/sizer/specs/optimizer/mt5tester.
- 2026-09-04: Plan-gap closures (6 commits, pushed): deterministic cost
  profiles ZERO/BASE/STRESSED/SEVERE with monotone-ledger engine test
  (plan 2 exit); WFA per-window param_hash/strategy_version/dataset_version
  + declared strategy versions (plan 7 outputs); adversarial future-mutation
  leakage pins across indicators/strategies/regime (plan 8 exit);
  docs/STATE_MODEL.md (plan 4) and docs/WFA_CONTRACT.md (plan 6).
  Suite: 239 green.
- 2026-09-04: Phase-8 metrics upgrade milestone committed/pushed: compute_metrics
  extended with recovery_factor, ulcer index, downside deviation, VaR/CVaR
  (95/99), rolling Sharpe median/worst, monthly win-rate/avg/std, trade
  median/avg pnl + duration, exposure/turnover approximations, max
  consecutive losses, HHI concentration, top-5 share, trailing-20
  expectancy/win rate — all legacy keys untouched (empty schema extended);
  9 new pinned tests in tests/test_metrics.py; 216 tests green.
- 2026-09-04: Phase-7 milestone `5306c47`: walk_forward leakage controls

  (embargo_bars keeps selection off OOS-adjacent bars; purge_bars drops
  boundary-censored selection trades with is_trades_purged reporting);
  automated leakage tests incl. a signal-level causality test for every
  registered strategy; 207 tests green.
- 2026-09-04: Phase-6 milestone `3c46d08`: `optimizer.walk_forward`
  rewritten on one scheduled engine run (no per-window capital resets);
  rolling-origin IS windows; per-window IS/OOS metrics, WFE, trade count,
  drawdown, cost, regime; engine rows carry `fees`/`costs` ledger columns
  (exact 7-tick x 2-leg decomposition pinned); `run_backtest` gained the
  engine `schedule` passthrough; 203 tests green.
- 2026-09-04: Phase-4 legacy wrapper milestone `345fb0e`: `backtest.py`
  rewritten as a thin canonical single-symbol wrapper over the portfolio
  engine (sizer + costs + DayClock; direct risk formula and calendar
  normalize() gone); `Instrument.params` channel on the engine (registry
  defaults < run-wide params < schedule segments); all 11 legacy tests
  green, two deliberately updated where they pinned removed legacy
  behaviour (below-min clamp-up to 0.01 lots; close-marked max-drawdown
  detection) — both documented in the commit message.  CHANGELOG suite
  count corrected to the authoritative 198 (previously asserted 172/143
  were stale); stale Notes line removed.
- 2026-09-04: Mission received. Phase 0 verified: tree clean at `1fc0289`,
  pytest 143, docs read; direct `risk/(stop*contract)` sizing confirmed in
  `backtest.open_trade`; single-`pos` engine; calendar-date resets;
  concatenating WFA confirmed in optimizer.walk_forward.
- 2026-09-04: Phases 1–3 committed (specs/sizer/dayclock/costs, 143 green).
- 2026-09-04: Canonical portfolio engine (`python/mql5bot/engine.py`) +
  profit-side tick value in `symbolspec.py` + 29 engine tests committed at
  `a77a5bf` and pushed (Phases 1/4/5 python): netting/hedging semantics,
  tick-valued PnL, exposure caps, server-day daily-loss/drawdown checks,
  swap/commission/reject/gap/margin costs, walk-forward param freeze.
  Engine validation fixes along the way: realized-PnL cash accounting,
  sub-tick PnL zeroing, tick-rounded fills, FIFO offset attribution,
  halt checks at bar open on prior-close equity.
