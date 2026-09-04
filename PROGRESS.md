# PROGRESS — AEGIS Phase 2.5 / Research Foundation Correction

- Branch: `arena/01a06cdc-mql5bot` (base `1fc0289` — hardening + tooling done)
- Phase: **1–5 python foundation built** (`a77a5bf`); next: Phase-4 legacy
  `run_backtest` canonical wrapper, then Phase 6 continuous WFA
- Tests: **172 passed** (pytest, /tmp/venv-audit; ruff clean on new files)
- Compile: **NOT VERIFIED** (no MetaEditor here; owner round-trip via
  tools/compile.ps1 — unchanged, reported honestly every phase)
- UNPUSHED: none (HEAD `a77a5bf` pushed)

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
