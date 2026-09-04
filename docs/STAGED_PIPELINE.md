# Staged pipeline & run manifests (plan Phase D)

`mql5bot.pipeline` implements the certified research funnel. One file,
no new strategies, no ML. Every stage emits a `RunManifest` whose
`manifest_id` is a deterministic sha-1 of stage, strategy, params,
engine, data version, cost config, seed, status and metrics — enough to
reproduce the run exactly (params + data digest + cost config + seed).

## Stages

| # | Stage | Engine | Output |
|---|-------|--------|--------|
| S1 | `screen_stage` — grid sweep, `top_k` by an explicit rank metric | FAST (default) or TRUTH | ranked `RunManifest`s |
| S2 | `cost_stress_stage` — every survivor at cost ×2 (spread AND commission doubled) | TRUTH (default) | `ok`/`dropped` manifests |
| S3 | `purged_cv_stage` — own trade-level purge + embargo combinatorial CV | TRUTH (default) | OOS-Sharpe distribution over folds + per-fold selection log |
| S4 | `mt5_stage` — headless MetaTrader 5 tester ticks | MT5 terminal host only | manifest; `skipped` with honest reason when no terminal |
| S5 | `oos_stage` — ONE final TRUTH run on never-touched OOS data | TRUTH only | certified manifest, recorded in the one-look registry |

`run_stages` chains S1 → S2 → S3 (→ S5 when an OOS frame + registry are
given) with an on-disk cache keyed by content digests. S4 is never
invoked implicitly — certification ticks belong to a terminal host.

## Survival gate (S2, documented)

A configuration survives ×2 cost stress when, on identical fills:
stressed end equity > initial capital, trades ≥ `min_trades`, and the
stressed max drawdown is no worse than twice the unstressed drawdown.
Surviving is a screening filter, not a profit promise.

## Purge + embargo semantics (S3, own implementation)

Concept: López de Prado's purged k-fold idea (referenced, not copied).
The bar axis is cut into `n_splits` contiguous blocks; every combination
of `n_splits // 2` test blocks is one fold. For each fold and each
configuration, a trade whose lifetime `[entry bar, exit bar)` intersects
an embargoed test span (test block ± `embargo_bars`) is LEAKY and is
excluded from that fold's in-sample selection score. Trades that do not
touch the test span stay selectable (verified both ways in
`tests/test_pipeline.py::test_purged_cv_purge_and_embargo_semantics`).
Each fold selects the best IS configuration among the survivors and
scores it on its own test blocks; pnl is attributed to the ENTRY bar
(the same convention as the walk-forward contract). The reported
OOS-Sharpe distribution is a development-data diagnostic and never
replaces S5.

## One-look OOS policy (S5, enforced in code)

Never optimise on the same OOS certification slice more than once per
(dataset_version, strategy) — recorded, persisted, enforced:
`OosRegistry.certify` raises `OosOneLookViolation` on any second look at
the same data version, whatever the parameters. `oos_stage` checks the
registry BEFORE running. A certification is only ever written after a
successful TRUTH-engine run, and the persisted entry carries the full
manifest (params, data digest/tag, cost config, metrics).

## Optional Optuna (never core)

`optuna_optimize` requires the `optimize` extra
(`pip install mql5bot[optimize]`); importing the pipeline never imports
Optuna and calling the stage without it raises ImportError with an
install hint. When present: seeded TPE sampler + Hyperband-compatible
study shape, deterministic under the seed, FAST engine only — a
screening signal, never a certification.
