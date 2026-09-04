"""mql5bot.metrics — performance statistics for equity curves and trades."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(
    equity: pd.Series,
    trades: pd.DataFrame | None = None,
    *,
    periods_per_year: float = 252.0,
    risk_free_annual: float = 0.0,
) -> dict:
    """Compute a full performance report from an equity curve and trade log.

    All NaN-producing statistics (e.g. Sharpe with zero variance) are
    reported as ``None``.
    """
    equity = pd.Series(equity, dtype=float).dropna()
    if len(equity) < 2:
        return _empty_metrics()

    returns = equity.pct_change().dropna()
    n_bars = len(equity)
    years = max(n_bars / periods_per_year, 1e-9)

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0

    std = returns.std(ddof=0)
    ann_vol = std * np.sqrt(periods_per_year) if std > 0 else None
    sharpe = (
        (returns.mean() * periods_per_year - risk_free_annual) / (std * np.sqrt(periods_per_year))
        if std > 0
        else None
    )
    downside = returns[returns < 0]
    dstd = downside.std(ddof=0) if len(downside) else 0.0
    sortino = (
        (returns.mean() * periods_per_year - risk_free_annual) / (dstd * np.sqrt(periods_per_year))
        if dstd > 0
        else None
    )

    # drawdown
    running_peak = equity.cummax()
    dd = equity / running_peak - 1.0
    max_dd = dd.min()
    max_dd_duration = _longest_dd_run(dd) if max_dd < 0 else 0
    calmar = cagr / abs(max_dd) if max_dd < 0 else None

    # trade statistics
    trade_stats = _trade_stats(trades) if trades is not None and len(trades) else {}

    out = {
        "start": str(equity.index[0]),
        "end": str(equity.index[-1]),
        "bars": int(n_bars),
        "years": round(float(years), 4),
        "start_equity": float(equity.iloc[0]),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": _r(total_return * 100.0),
        "cagr_pct": _r(cagr * 100.0),
        "annual_vol_pct": _r(ann_vol * 100.0) if ann_vol is not None else None,
        "sharpe": _r(sharpe),
        "sortino": _r(sortino),
        "max_drawdown_pct": _r(max_dd * 100.0) if max_dd is not None else None,
        "max_dd_duration_bars": int(max_dd_duration),
        "calmar": _r(calmar),
        "best_bar_pct": _r(returns.max() * 100.0),
        "worst_bar_pct": _r(returns.min() * 100.0),
        "avg_bar_pct": _r(returns.mean() * 100.0),
    }
    out.update(trade_stats)
    return out


def _trade_stats(trades: pd.DataFrame) -> dict:
    t = trades.copy()
    pnl = pd.to_numeric(t["pnl"], errors="coerce")
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    n = len(pnl)
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (np.inf if gross_profit > 0 else None)
    win_rate = len(wins) / n * 100.0 if n else None
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = losses.mean() if len(losses) else 0.0
    payoff = avg_win / abs(avg_loss) if avg_loss else (np.inf if avg_win > 0 else None)
    expectancy = pnl.mean() if n else None
    return {
        "trades": int(n),
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate_pct": _r(win_rate),
        "profit_factor": _r(profit_factor),
        "avg_win": _r(avg_win),
        "avg_loss": _r(avg_loss),
        "payoff_ratio": _r(payoff),
        "expectancy": _r(expectancy),
        "net_profit": _r(pnl.sum()),
    }


def monthly_returns(equity: pd.Series) -> pd.DataFrame:
    """Resample an equity curve into monthly % returns (pivot, month x year)."""
    eq = equity.resample("ME").last().ffill()
    rets = eq.pct_change().dropna() * 100.0
    out = pd.DataFrame(
        {
            "year": rets.index.year,
            "month": rets.index.month,
            "return_pct": rets.values.round(4),
        }
    )
    return out


def _longest_dd_run(dd: pd.Series) -> int:
    longest = run = 0
    for v in dd:
        if v < 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest


def _empty_metrics() -> dict:
    return {
        "start": None,
        "end": None,
        "bars": 0,
        "years": 0.0,
        "start_equity": None,
        "end_equity": None,
        "total_return_pct": None,
        "cagr_pct": None,
        "annual_vol_pct": None,
        "sharpe": None,
        "sortino": None,
        "max_drawdown_pct": None,
        "max_dd_duration_bars": 0,
        "calmar": None,
        "best_bar_pct": None,
        "worst_bar_pct": None,
        "avg_bar_pct": None,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate_pct": None,
        "profit_factor": None,
        "avg_win": None,
        "avg_loss": None,
        "payoff_ratio": None,
        "expectancy": None,
        "net_profit": None,
    }


def _r(v):
    """Round to a sane precision, keep None/NaN as None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return round(f, 4)
