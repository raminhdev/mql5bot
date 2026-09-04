"""Adversarial leakage tests: future data must not move the past (plan Phase 8).

The mechanical rule under test: *inject an extreme value into a future
candle — no feature or signal computed before that timestamp may change.*

Covered here:

* indicator features — EMA, SMA, rolling std (volatility), RSI, ATR,
  Bollinger (mid/upper/lower), Donchian, MACD (line/signal/hist),
  highest/lowest, crossovers;
* every registered strategy signal (EMA crossover, RSI, Donchian,
  Bollinger, MACD families);
* per-span regime features (mutating bars outside the span must not
  change the span's regime report).

Rolling percentile / regression-slope features do not exist in the
research feature set yet — when they are added, they get the same pin
here.
"""

import numpy as np
import pandas as pd
import pytest
from mql5bot import optimizer as optimizer_mod
from mql5bot.indicators import (
    atr,
    bollinger,
    crossover,
    donchian,
    ema,
    highest,
    lowest,
    macd,
    rolling_std,
    rsi,
    sma,
)
from mql5bot.strategies import STRATEGIES, signal

N = 300
PROBE = 220  # bars [PROBE, N) get mutated; outputs must not move before it
CUT = 200  # prefix length asserted unchanged (margin below the mutation)


def _random_frame(seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=N, freq="h")
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.5, N))
    spread = np.abs(rng.normal(0.0, 0.2, N))
    high = np.maximum(close[:-1], close[1:]) + spread[1:]
    low = np.minimum(close[:-1], close[1:]) - spread[1:]
    high = np.concatenate([[high[0]], high])
    low = np.concatenate([[low[0]], low])
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": 1000.0}, index=idx)


def _mutate(df: pd.DataFrame) -> pd.DataFrame:
    """Copy with an extreme-value injection into every bar >= PROBE."""
    out = df.copy()
    blast = np.linspace(3.0, 8.0, N - PROBE)
    for col in ("open", "high", "low", "close"):
        out.loc[out.index[PROBE]:, col] = (
            out.loc[out.index[PROBE]:, col] * blast
            + np.arange(N - PROBE, dtype=float)
        )
    return out


def _assert_prefix_stable(before: np.ndarray, after: np.ndarray) -> None:
    a, b = np.asarray(before)[:CUT], np.asarray(after)[:CUT]
    assert a.shape == b.shape
    assert np.array_equal(a, b, equal_nan=True), \
        "a future-bar mutation moved an earlier feature output"


INDICATOR_CASES = [
    ("ema", lambda h, l, c: ema(c, 10)),
    ("sma", lambda h, l, c: sma(c, 20)),
    ("rolling_std", lambda h, l, c: rolling_std(c, 20)),
    ("rsi", lambda h, l, c: rsi(c, 14)),
    ("atr", lambda h, l, c: atr(h, l, c, 14)),
    ("bollinger", lambda h, l, c: bollinger(c, 20, 2.0)),
    ("donchian", lambda h, l, c: donchian(h, l, 20)),
    ("macd", lambda h, l, c: macd(c, 12, 26, 9)),
    ("highest", lambda h, l, c: highest(c, 20)),
    ("lowest", lambda h, l, c: lowest(c, 20)),
    ("crossover", lambda h, l, c: crossover(ema(c, 10), ema(c, 30))),
]


@pytest.mark.parametrize(
    "name,fn",
    INDICATOR_CASES,
    ids=[name for name, _ in INDICATOR_CASES],
)
def test_indicator_prefix_immune_to_future_mutation(name, fn):
    df = _random_frame()
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    before = fn(h, l, c)
    df2 = _mutate(df)
    after = fn(df2["high"].to_numpy(), df2["low"].to_numpy(),
               df2["close"].to_numpy())
    outs_b = before if isinstance(before, tuple) else (before,)
    outs_a = after if isinstance(after, tuple) else (after,)
    assert len(outs_b) == len(outs_a)
    for o_b, o_a in zip(outs_b, outs_a):
        _assert_prefix_stable(o_b, o_a)
    # sanity: the feature inputs really did change after the probe
    assert not df2["close"].equals(df["close"])


@pytest.mark.parametrize("strategy", sorted(STRATEGIES))
def test_strategy_signal_prefix_immune_to_future_mutation(strategy):
    df = _random_frame(seed=11)
    df2 = _mutate(df)
    assert not df["close"].equals(df2["close"])
    s1 = signal(df, strategy).to_numpy()
    s2 = signal(df2, strategy).to_numpy()
    # nothing before the first mutated bar (PROBE) may move
    assert np.array_equal(s1[:PROBE], s2[:PROBE]), strategy


def test_regime_features_depend_only_on_their_span():
    df = _random_frame(seed=3)
    df2 = _mutate(df)
    ppy = 24 * 365.25
    regime = optimizer_mod._regime
    before = regime(df, 100, 200, ppy)
    after = regime(df2, 100, 200, ppy)
    assert before == after
    # but a mutation INSIDE the span does move the report (guard sanity:
    # a test that can never fail would be vacuous)
    df3 = df.copy()
    df3.loc[df3.index[150], "close"] *= 1.5
    moved = regime(df3, 100, 200, ppy)
    assert moved != before
