"""mql5bot.optimizer — parameter optimisation and walk-forward analysis."""

from __future__ import annotations

import itertools
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import BacktestResult, run_backtest
from .strategies import default_params


@dataclass
class Run:
    params: dict
    result: BacktestResult

    def summary(self) -> dict:
        return {"params": self.params, **{k: v for k, v in self.result.metrics.items()}}


def _expand(grid: dict) -> list[dict]:
    keys = list(grid)
    if not keys:
        return [{}]
    values = [v if isinstance(v, (list, tuple, range)) else [v] for v in grid.values()]
    combos = list(itertools.product(*values))
    return [dict(zip(keys, combo)) for combo in combos]


def grid_search(
    df: pd.DataFrame,
    strategy_name: str,
    grid: dict | None = None,
    *,
    metric: str = "sharpe",
    minimize: bool = False,
    n_jobs: int = 1,
    **kwargs,
) -> list[Run]:
    """Run every parameter combination and return runs sorted by `metric`.

    ``grid`` maps parameter names to lists of candidate values. Parameters
    not present in the grid take their strategy defaults.
    """
    base = default_params(strategy_name)
    combos = _expand(grid or {})
    param_sets = [{**base, **combo} for combo in combos]

    if n_jobs > 1 and len(param_sets) > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as pool:
            futures = [
                pool.submit(run_backtest, df, strategy_name, ps, **kwargs)
                for ps in param_sets
            ]
            results = [f.result() for f in futures]
    else:
        results = [run_backtest(df, strategy_name, ps, **kwargs) for ps in param_sets]

    runs = [Run(ps, res) for ps, res in zip(param_sets, results)]
    runs.sort(
        key=lambda r: _metric_value(r.result.metrics.get(metric), minimize),
        reverse=not minimize,
    )
    return runs


def _metric_value(value, minimize: bool):
    if value is None:
        return float("inf") if minimize else float("-inf")
    return float(value)


def walk_forward(
    df: pd.DataFrame,
    strategy_name: str,
    grid: dict | None = None,
    *,
    train_fraction: float = 0.6,
    n_windows: int = 3,
    metric: str = "sharpe",
    **kwargs,
) -> dict:
    """Walk-forward analysis: optimise on a training window, trade the next
    window with the best parameters, and roll forward.

    Returns a dict with per-window summaries, out-of-sample results, and an
    aggregate out-of-sample equity curve.
    """
    n = len(df)
    step = int(n * (1.0 - train_fraction) / max(n_windows, 1))
    if step < 2:
        raise ValueError("not enough bars for walk-forward windows")

    windows = []
    oos_equity_parts: list[pd.Series] = []
    start = 0
    w = 0
    while start + step <= n and w < n_windows:
        train_end = start + int(step * train_fraction)
        if train_end <= start + 20 or train_end >= n:
            break
        train = df.iloc[start:train_end]
        test = df.iloc[train_end : min(train_end + step, n)]
        runs = grid_search(train, strategy_name, grid, metric=metric, **kwargs)
        best = runs[0]
        test_result = run_backtest(test, strategy_name, best.params, **kwargs)
        windows.append(
            {
                "window": w,
                "train_start": str(train.index[0]),
                "train_end": str(train.index[-1]),
                "test_start": str(test.index[0]),
                "test_end": str(test.index[-1]),
                "best_params": best.params,
                "train_metric": best.result.metrics.get(metric),
                "test_metrics": test_result.metrics,
            }
        )
        oos_equity_parts.append(test_result.equity)
        start = train_end
        w += 1

    oos_equity = pd.concat(oos_equity_parts) if oos_equity_parts else pd.Series(dtype=float)
    from .metrics import compute_metrics

    oos_metrics = (
        compute_metrics(oos_equity, periods_per_year=_pph(df.index))
        if len(oos_equity) > 1
        else {}
    )
    return {
        "strategy": strategy_name,
        "metric": metric,
        "windows": windows,
        "oos_metrics": oos_metrics,
        "oos_equity": oos_equity,
    }


def _pph(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 252.0
    delta = index.to_series().diff().dt.total_seconds().median()
    if pd.isna(delta) or delta <= 0:
        return 252.0
    return 365.25 * 24 * 3600 / delta


def runs_to_frame(runs: list[Run]) -> pd.DataFrame:
    """Flatten a list of optimisation runs into a table."""
    rows = []
    for r in runs:
        row = {f"p_{k}": v for k, v in r.params.items()}
        for k, v in r.result.metrics.items():
            row[f"m_{k}"] = v
        rows.append(row)
    return pd.DataFrame(rows)


def best(runs: list[Run]) -> Run:
    return runs[0]
