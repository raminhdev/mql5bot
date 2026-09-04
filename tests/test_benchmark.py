"""Benchmark harness (plan Phase A) — marked ``bench``.

Measurement-only tests: they report bars/sec, wall time per
``run_backtest``, wall time per walk-forward window, and peak memory,
and only assert that the instruments produced sane numbers.  Run with the
whole suite (``pytest``) or selectively (``pytest -m bench -s`` to see
the printed table).  The BEFORE/AFTER tables for optimisations live in
PROGRESS.md and are produced from this harness.
"""

import time

import pytest
from mql5bot.data import generate_ohlc
from mql5bot.optimizer import walk_forward
from mql5bot.perf import single_run_metrics

pytestmark = pytest.mark.bench


@pytest.fixture(scope="module")
def df():
    return generate_ohlc(days=130, seed=1)  # 3120 hourly bars


@pytest.fixture(scope="module")
def wf_df():
    return generate_ohlc(days=120, seed=21)


def test_bench_single_run_backtest_throughput(df):
    m = single_run_metrics(df, n_repeats=5, risk_percent=0.5)
    assert m["seconds"] > 0.0
    assert m["bars_per_sec"] > 100.0
    print("\n[BENCH] run_backtest "
          f"wall={m['seconds_per_run'] * 1000:.1f} ms/run | "
          f"{m['bars_per_sec']:,.0f} bars/s | "
          f"{m['trades_per_sec']:.1f} trades/s | "
          f"peak {m['peak_memory_mb']} MB")


def test_bench_walk_forward_window_wall(wf_df):
    t0 = time.perf_counter()
    wf = walk_forward(wf_df, "ema_crossover",
                      grid={"fast": [8, 12], "slow": [24, 40]},
                      n_windows=2, train_fraction=0.6, risk_percent=0.5,
                      max_bars=100)
    total = time.perf_counter() - t0
    n_windows = len(wf["windows"])
    assert n_windows >= 1 and total > 0.0
    print(f"\n[BENCH] walk_forward windows={n_windows} "
          f"total={total:.2f}s wall={total / n_windows:.2f}s/window "
          f"bars={wf['geometry']['bars']}")


def test_bench_peak_memory_single_run(df):
    m = single_run_metrics(df, n_repeats=2, risk_percent=0.5)
    assert m["peak_memory_mb"] is not None and m["peak_memory_mb"] >= 0.0
