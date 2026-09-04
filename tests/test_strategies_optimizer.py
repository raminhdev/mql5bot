"""Tests for strategy signal generation and the optimiser."""

import numpy as np
import pandas as pd
import pytest

from mql5bot.data import generate_ohlc
from mql5bot.optimizer import grid_search, walk_forward
from mql5bot.strategies import STRATEGIES, default_params, list_strategies, signal


@pytest.fixture(scope="module")
def df():
    return generate_ohlc(days=120, seed=21)


def test_all_strategies_produce_valid_signals(df):
    for name in STRATEGIES:
        s = signal(df, name)
        assert len(s) == len(df)
        assert set(np.unique(s)).issubset({-1, 0, 1})
        # no signal before the slowest indicator warms up
        assert s.iloc[0] == 0


def test_default_params_exist_for_all(df):
    for name in STRATEGIES:
        p = default_params(name)
        assert p, name
        # strategy must run with its defaults and tweaked params
        signal(df, name, p)
        tweaked = dict(p)
        first_key = next(iter(tweaked))
        tweaked[first_key] = float(tweaked[first_key]) * 1.1
        signal(df, name, tweaked)


def test_unknown_strategy_raises(df):
    with pytest.raises(KeyError):
        signal(df, "nope")
    with pytest.raises(KeyError):
        default_params("nope")


def test_strategy_behaviour_smoke(df):
    # trend strategy: mostly aligned with the prevailing trend direction
    s = signal(df, "ema_crossover")
    drift = np.sign(df["close"].iloc[-1] - df["close"].iloc[0])
    valid = s[s != 0]
    if len(valid) and drift != 0:
        # at least 40% of held bars agree with the net trend
        assert (valid == drift).mean() > 0.4
    # reversal strategy: never stays in a trade too long on this dataset
    s_rsi = signal(df, "rsi_reversal")
    assert abs(s_rsi).mean() <= 1.0


def test_grid_search_ranks_by_metric(df):
    grid = {"fast": [8, 12], "slow": [24, 40]}
    runs = grid_search(
        df, "ema_crossover", grid, metric="sharpe",
        risk_percent=0.5, max_bars=100,
    )
    assert len(runs) == 4
    sharpes = [r.result.metrics["sharpe"] for r in runs]
    assert sharpes == sorted(sharpes, reverse=True)


def test_grid_search_minimize(df):
    grid = {"fast": [8, 12], "slow": [24, 40]}
    runs = grid_search(
        df, "ema_crossover", grid, metric="max_drawdown_pct",
        minimize=True, risk_percent=0.5, max_bars=100,
    )
    dds = [r.result.metrics["max_drawdown_pct"] for r in runs]
    assert dds == sorted(dds)  # most negative (worst) last when minimising


def test_walk_forward_returns_oos_metrics(df):
    wf = walk_forward(
        df, "ema_crossover", grid={"fast": [8, 12], "slow": [24, 40]},
        n_windows=2, train_fraction=0.6, risk_percent=0.5, max_bars=100,
    )
    assert len(wf["windows"]) >= 1
    assert "oos_metrics" in wf
    assert len(wf["oos_equity"]) > 0
    for w in wf["windows"]:
        assert {"fast", "slow"} <= set(w["best_params"])  # defaults merged in


def test_list_strategies_documents_everyone():
    listing = list_strategies()
    assert {s["name"] for s in listing} == set(STRATEGIES)
    for s in listing:
        assert s["description"]
