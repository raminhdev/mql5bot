# TASKS — AEGIS Research / Performance Upgrade

Mission checklist (docs/SPEC.md §16 style: phase report after each phase with
pushed hashes + tests + DoD status + 5-line Persian summary). Branch
`arena/01a06cdc-mql5bot`. Phase 0 done at session start; Phases 1–2 are this
session's scope; later phases stay unchecked until their session.

## Phase 0 — Verification of previous hardening (S1–S5)
- [x] pytest green, ruff scoped (new files clean; legacy findings untouched)
- [x] git status clean / git log reviewed / remote == local tip
- [x] Docs inspected: SPEC.md, HANDOFF.md, IMPLEMENTATION_AUDIT.md, DECISIONS.md
- [x] S1 SlGuard wired: Enqueue on entry (Mql5Bot.mq5:854) + adoption (:313),
      Pump in OnTimer (:625), escalation -> ENGINE_HALT
- [x] S2 persistence wired: HotStateLoad/AdoptState in OnInit (:478/:502),
      kill-switch 10 s close cadence (:581), explicit reset ack (:493)
- [x] S3 no-Sleep wired: ProcessQueue in OnTimer (:569), zero `Sleep(` in mql5/
- [x] S4/S5 wired: BuildSymbolSpec (:422) + MagicMap Allocate (:514+)
- [x] Trace evidence recorded in the session report

## Phase 1 — MetaEditor / MT5 compile round-trip preparation
- [x] tools/compile.ps1: locate MetaEditor, install sources, compile, capture
      log, fail on errors, fail on warnings when -Strict, reproducible log
- [ ] tools/README.md — exact usage documentation
- [ ] Owner runs it on Windows; feed errors back (blocked: no MetaEditor here)
- [ ] Do NOT mark Release A complete without compiler output

## Phase 2 — Headless MT5 Strategy Tester automation
- [ ] python/mql5bot/mt5tester.py: .set render/parse (pipe ranges preserved),
      [Tester] ini generator (+[TesterInputs]), batch matrix, MT5 HTML report
      parser -> canonical metrics, deterministic artifacts
- [ ] tests/test_mt5tester.py (fixtures; no terminal needed)
- [ ] tools/run_mt5_backtest.py — CLI: generate-set / generate-ini / run /
      batch / parse; launch headless portable terminal, completion watch,
      timeout, shutdown, raw report preservation
- [ ] tools/run_mt5_backtest.ps1 — PowerShell wrapper (strict, logged)
- [ ] Owner Windows round-trip: real terminal run + real report validation

## Phase 3 — Two-speed backtest architecture
- [ ] FAST mode: vectorized screening, cached/precomputed features, parallel
      candidates, early rejection
- [ ] TRUTH mode: real MT5 tester for survivors only (Phase 2 runner)
- [ ] Policy: fast results never the final live-validation authority

## Phase 4 — Execution realism (cost models)
- [ ] spread (variable), slippage, latency, commission, swap, partial fills,
      rejected fills, market gaps, session-open degradation, stop/freeze
- [ ] cost scenarios BASE / STRESSED / SEVERE; robustness gate

## Phase 5 — Robustness / overfitting
- [ ] CPCV, purging, embargo; PBO/CSCV; Deflated/Probabilistic Sharpe;
      Monte Carlo; parameter perturbation (SPP); White RC; Hansen SPA
- [ ] results feed promotion gates (never decorative)

## Phase 6 — MT5 report comparison harness
- [ ] python-vs-MT5 comparison: trades/net/gross/maxDD/equity shape/commission/
      swap/slippage/average trade/win rate; documented tolerances

## Phase 7 — Position sizing cross-check matrix
- [ ] FX/metals/index/crypto CFDs, currencies, tick sizes/values (asymmetric),
      volume grids/limits, commission, margin; independent reference vs
      canonical SymbolSpec/sizer; no upward-rounding over-risk

## Phase 8 — Feature engine (causal)
- [ ] ATR, ATR ratio, ADX, DI spread, RSI, Bollinger width, RV, vol percentile,
      EMA distance/slope, linreg slope/R2, KER, choppiness, session, weekday
- [ ] per-feature definition/lookback/timestamp/closed-bar/unit/leak tests;
      cache; no recompute per candidate

## Phase 9 — Meta-labeling (secondary filter only)
- [ ] orthogonal meta-features (regime, vol, spread, session, liquidity,
      market-state, strategy-state, execution context), NOT duplicated signal
      features; Risk Engine stays final authority

## Phase 10 — Triple-barrier labeling (research only)
- [ ] profit/stop/time barriers, signal_time/entry/SL/TP/time_limit/outcome,
      no future leakage

## Phase 11 — Probability calibration
- [ ] raw/Platt/isotonic; Brier, log loss, calibration error, EV after costs

## Phase 12 — ML model policy
- [ ] LR baseline -> LightGBM/XGBoost -> calibrated probs -> meta-labeling;
      NN/ONNX/ensembles only after measurable OOS gain; no RL/Transformer/
      LSTM/GNN/online learning without evidence

## Phase 13 — Regime engine parity
- [ ] production regime stays deterministic rule-based, EA/Python parity;
      ML may consume the label, never silently redefine it

## Phase 14 — Strategy selection
- [ ] gate status, regime fit, OOS recency, DD state, drift, correlation,
      execution quality, cost resilience; never pure max profit; equal-weight
      fallback

## Phase 15 — Fitness function
- [ ] configurable multi-factor score (expectancy, PF, DD, Sharpe/Sortino,
      recovery, trade count, cost resilience, regime/parameter stability,
      concentration penalty, MC risk); fragile-vs-stable ordering

## Phase 16 — Optimization speed
- [ ] feature/indicator caches, vectorized screening, multiprocessing,
      deterministic seeds, early rejection, staged optimization
      (screen -> robustness -> MT5 -> OOS -> demo); no repeated OOS tuning

## Phase 17 — Visual research
- [ ] replay layer: candles/entries/exits/SL/TP/regime/strategy/meta score/
      outcome/replay controls; local data-driven; no Selenium/Chrome

## Phase 18 — Performance profiling
- [ ] tools/profile_research.py; baseline/optimized/speedup/memory delta per
      stage; no optimization without benchmark evidence

## Phase 19 — Acceptance criteria (mission DoD)
- [ ] 1 MetaEditor compile verified or explicitly marked blocked
- [ ] 2 real MT5 headless backtest works
- [ ] 3 Python fast screening works
- [ ] 4 Python/MT5 comparison harness works
- [ ] 5 execution cost stress works
- [ ] 6 CPCV/WFA/Monte Carlo work
- [ ] 7 feature leakage tests work
- [ ] 8 meta-labeling works (research mode)
- [ ] 9 calibrated probabilities work
- [ ] 10 strategy selection has equal-weight fallback
- [ ] 11 optimization speed has measurable benchmark
- [ ] 12 no live risk rule bypassable by Python or ML
