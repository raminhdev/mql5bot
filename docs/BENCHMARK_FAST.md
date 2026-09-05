# FAST engine — scope, profile, benchmark (Phase 3 hardening, Blocker 4)

All numbers below are MEASURED in this repository's sandbox
(CPython 3.11, single core, shared environment).  **No engine-level
speedup is claimed** — the measured result is 1.001× (see §4).  The
benchmark harness is `tools/benchmark_fast.py`; every table here is
reproducible with the commands shown.

---

## 1. Documented scope (honest statement)

`mql5bot.fast_engine.run_fast` is a NumPy-array re-implementation of the
canonical engine's ORCHESTRATION for the single-(symbol, strategy)
netting screening case.  Accounting/sizing formulas are NOT duplicated —
`costs`, `sizer`, `leg_cash` and symbol rounding are called per event.

| Aspect | Status |
|---|---|
| Array-based (no per-bar pandas) | OHLC extraction, signal series, ATR(14), spread/reject series, server-day ids, equity/notional curves, timestamp strings (vectorised strftime on whole-second DatetimeIndex; exact per-element conversion otherwise) |
| Loops that REMAIN Python | the per-bar event loop (risk checks, reconciliation, fills, position management); per-event fill/valuation calls; per-trade row construction |
| Unsupported features (loud `NotImplementedError`) | walk-forward schedule; margin calculator; exposure caps; per-strategy risk map; swap |
| Numba / JIT | **NOT used** — pure Python + NumPy, no C extension |
| Certification | NEVER — TRUTH engine (`engine.py`) and the real MT5 tester are the only certification paths; equivalence pinned by `tests/test_fast_engine.py` |

## 2. Profiler findings (cProfile, 30k bars, 3 runs)

Per run ≈ 0.37 s on a trade-dense parameter set (1,436 trades):

| Hot path | share (cum) | note |
|---|---|---|
| `leg_cash` (via `mark()` per held bar + fills) | ~53 % | single-owner valuation — deliberately not vectorised |
| `run_fast` per-bar loop body | ~27 % (tottime) | pure Python event loop |
| timestamp formatting `[str(t) for t in index]` | ~13 % | pandas `Timestamp.__iter__` + per-element `str()` |
| `compute_metrics` | ~13 % | pandas, SHARED with the TRUTH path — left alone |
| `round()` calls (fills, rows) | ~8 % | exact-accounting rounding — kept |

## 3. Optimizations applied (measured at component level)

| Change | Component measurement | kept? |
|---|---|---|
| vectorised `index.strftime` replacing `[str(t) for t in index]` (whole-second guard, exact fallback) | 300k index: 469.7 ms → 99.0 ms (**4.7×**), strings identical | yes |
| constant spread/reject series via `np.full` instead of per-bar `cost_cfg.spread_at(i)` list-comp (fixed-cost mode only) | 300k bars: 7.18 ms → 0.09 ms (**78×**) | yes |
| hoisted per-entry `merged["sl_atr"/"tp_atr"]` dict lookups | sub-sum measurement noise | yes (trivial) |
| per-book `leg_cash` value cache | no engine-level gain (see §4) | **rejected** (invalidation complexity without measured benefit) |

## 4. Engine-level A/B: baseline vs optimized — MEASURED RESULT: NO SPEEDUP

Methodology (after two harness defects were fixed — see §5): the full
`tools/benchmark_fast.py` matrix run against `git stash`-applied
baseline and the optimized tree, interleaved over two rounds in one
session; identical parameter sets; trade counts verified identical
per cell.

| cell (bars × param sets) | base/opt wall ratio r1 | r2 |
|---|---:|---:|
| 3,000 × 1 | 1.027 | 0.907 |
| 3,000 × 100 | 0.978 | 0.917 |
| 3,000 × 1,000 | 1.052 | 0.979 |
| 30,000 × 1 | 0.982 | 1.059 |
| 30,000 × 100 | 1.105 | 0.948 |
| 300,000 × 1 | 1.156 | 0.937 |
| **geometric mean** | | **1.001** |

Ratio range 0.907–1.156 (environment noise is ±10 % run-to-run on this
shared sandbox — a fixed numpy control workload itself varied ±13 %
between processes).  **Conclusion: no engine-level speedup is
resolvable; the component-level wins (§3) are real but the per-bar
Python loop and the shared valuation calls dominate, exactly as the
profile predicts.**  Memory: single-run peak on 300k bars is 70.97 MB
(baseline) vs 70.75 MB (optimized) — a −0.3 % delta; results are
trade-for-trade identical in every cell (9,855 trades on the 300k run;
29,914 on the 30k×100 sweep).

## 5. Harness defects found while measuring (fixed in
`tools/benchmark_fast.py`)

1. `tracemalloc` enabled around the TIMED loop inflated wall time ~19×
   (3k×100: 49 s traced vs 2.5 s untraced).  Timing and memory probing
   are now separate.
2. The first baseline run was left running as an orphan process during
   early comparisons, skewing them; it was killed and the A/B redone.
3. An early A/B loop omitted `git stash pop`, comparing baseline against
   itself; detected via the ~1.0 ratios and redone correctly.

These are documented because a "speedup" claimed from any of the
affected runs would have been fabricated.

## 6. Absolute numbers (fixed harness, optimized tree, single core)

| bars | param sets | wall s | bars/s | trades/s | peak MB | cpu/wall |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,000 | 1 | 0.033 | 91,735 | 7,185.9 | 0.8 | 1.00 |
| 3,000 | 100 | 2.870 | 104,537 | 3,791.2 | 0.8 | 1.00 |
| 3,000 | 1,000 | 28.600 | 104,894 | 3,551.6 | 0.8 | 0.99 |
| 30,000 | 1 | 0.252 | 119,286 | 9,201.0 | 8.4 | 1.00 |
| 30,000 | 100 | 23.065 | 130,068 | 5,148.8 | 8.4 | 0.99 |
| 300,000 | 1 | 2.562 | 117,112 | 11,677.6 | 89.6 | 1.00 |

(The 1,000-set sweep at 300k bars is omitted from the default matrix:
~40 min single-core; `--full` runs it.  Absolute wall times vary ±10 %
between sessions on this shared sandbox — the ratios of §4 are the
only meaningful comparison.)

Reproduce:

```bash
PYTHONPATH=python python tools/benchmark_fast.py --output results.json
pytest -m bench -s            # measurement-only bench tests
```
