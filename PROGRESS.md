# PROGRESS — AEGIS Phase 2.5 / Research Foundation Correction

- Branch: `arena/01a06cdc-mql5bot` (base `a7c9978` — hardening + tooling done)
- Phase: **1–7 python foundation built** (wrapper `345fb0e`, continuous
  WFA `3c46d08`, leakage controls `5306c47`); next: Phase 8 metrics upgrade
- Tests: **207 passed** (pytest tests/ exit 0, /tmp/venv-audit; ruff clean
  on changed files; 207 = 169 pre-engine + 29 engine + 9 phase 6/7)
- Compile: **NOT VERIFIED** (no MetaEditor here; owner round-trip via
  tools/compile.ps1 — unchanged, reported honestly every phase)
- UNPUSHED: `5306c47` committed (push pending)

## Next 3 steps
1. `python/mql5bot/backtest.py` — legacy `run_backtest` becomes a thin
   canonical single-symbol wrapper over the portfolio engine
   (sizer + costs + dayclock); deliberate documented updates only where a
   test pinned the removed over-risk direct-formula behaviour.
2. Phase 6 — continuous walk-forward on the engine (params frozen per OOS
   segment, capital/portfolio/risk carried forward, aggregate OOS equity =
   the continuous run); replace concatenating `walk_forward` internals.
3. Phase 7 — WFA overlap/leakage controls (purge gap, embargo, lookback
   warm-up) + automated leakage tests.

## Session log
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
