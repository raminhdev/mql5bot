"""mql5bot.backtest — bar-based event-driven backtest engine.

Model contract (documented so results are reproducible):

* Signals are the strategy's *desired position* computed from closed bars.
  Trades are executed at the **next** bar's open — lookahead is impossible.
* Entry fills at the open adjusted for half the spread (buy at ask, sell at
  bid) plus slippage. Exits adjust the same way, so a round trip always pays
  the full spread plus slippage on both legs plus commission.
* Stop loss / take profit are simulated intrabar using the bar's high/low.
  When a bar touches both levels, the stop is assumed hit first
  (conservative). Exits happen at the stop price exactly (worst case).
* Position sizing risks ``risk_percent`` of current equity over the stop
  distance, matching ``CRiskManager`` in the MQL5 EA.
* The equity curve is marked to market at every bar close.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import strategies
from .indicators import atr as atr_indicator

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class BacktestResult:
    strategy: str
    params: dict
    config: dict
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    equity: pd.Series = field(default_factory=pd.Series)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """JSON-serialisable summary (equity downsampled to <= 1500 points)."""
        eq = self.equity
        step = max(1, math.ceil(len(eq) / 1500))
        eq_ds = eq.iloc[::step]
        return {
            "strategy": self.strategy,
            "params": self.params,
            "config": self.config,
            "metrics": {k: _jsonable(v) for k, v in self.metrics.items()},
            "equity": {
                "time": [str(t) for t in eq_ds.index],
                "value": [float(v) for v in eq_ds.values],
            },
            "trades": self.trades.to_dict(orient="records"),
        }


@dataclass
class _Position:
    side: int  # +1 long, -1 short
    entry_time: pd.Timestamp
    entry_price: float
    lots: float
    sl: float
    tp: float
    atr_entry: float
    commission_paid: float = 0.0
    partial_done: bool = False
    be_done: bool = False
    bars_held: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def run_backtest(
    df: pd.DataFrame,
    strategy_name: str,
    params: dict | None = None,
    *,
    initial_capital: float = 10_000.0,
    risk_percent: float = 1.0,
    max_lots: float = 100.0,
    allow_short: bool = True,
    spread_points: float = 1.0,
    slippage_points: float = 0.0,
    commission_per_lot: float = 7.0,
    point: float = 1e-5,
    contract_size: float = 100_000.0,
    trail_atr: float = 0.0,
    breakeven_atr: float = 0.0,
    breakeven_offset_points: float = 0.0,
    partial_atr: float = 0.0,
    partial_fraction: float = 0.5,
    max_bars: int = 0,
    max_daily_loss_pct: float = 0.0,
    max_drawdown_pct: float = 0.0,
) -> BacktestResult:
    """Run the backtest. Returns a :class:`BacktestResult`."""
    # ---------------- validation ----------------
    if risk_percent <= 0:
        raise ValueError("risk_percent must be > 0")
    if not 0.0 < partial_fraction < 1.0:
        raise ValueError("partial_fraction must be in (0, 1)")
    if spread_points < 0 or slippage_points < 0 or commission_per_lot < 0:
        raise ValueError("costs must be >= 0")

    merged = strategies.default_params(strategy_name)
    if params:
        merged.update(params)
    desired = strategies.signal(df, strategy_name, merged).to_numpy()

    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    n = len(df)
    atr_series = atr_indicator(h, l, c, 14)

    half_spread = spread_points * point / 2.0
    slip = slippage_points * point
    sl_mult = float(merged.get("sl_atr", 2.0))
    tp_mult = float(merged.get("tp_atr", 4.0))

    equity = np.empty(n)
    equity[0] = float(initial_capital)
    peak_equity = float(initial_capital)
    cash = float(initial_capital)
    pos: _Position | None = None
    trades: list[dict] = []
    day_open_equity = float(initial_capital)
    current_day = df.index[0].normalize()
    day_halted = False
    dd_halted = False

    # ---------------- closures ----------------
    def manage_position(i: int) -> None:
        """Update exits and resolve intrabar SL/TP for the open position."""
        nonlocal pos, cash
        assert pos is not None
        pos.bars_held += 1
        a = atr_series[i - 1] if i >= 1 else np.nan

        # --- exits that update on bar close ---------------------------
        if i >= 1 and not np.isnan(a) and a > 0:
            # trailing stop: never loosened
            if trail_atr > 0:
                if pos.side > 0:
                    pos.sl = max(pos.sl, c[i] - trail_atr * a)
                else:
                    pos.sl = min(pos.sl, c[i] + trail_atr * a)
            # breakeven
            if breakeven_atr > 0 and not pos.be_done:
                profit_dist = pos.side * (c[i] - pos.entry_price)
                if profit_dist >= breakeven_atr * a:
                    pos.sl = pos.entry_price + pos.side * breakeven_offset_points * point
                    pos.be_done = True
            # partial scale-out at target, SL to breakeven
            if partial_atr > 0 and not pos.partial_done:
                profit_dist = pos.side * (c[i] - pos.entry_price)
                if profit_dist >= partial_atr * a:
                    fill = c[i] - pos.side * half_spread - pos.side * slip
                    gross = (
                        pos.side
                        * (fill - pos.entry_price)
                        * pos.lots
                        * partial_fraction
                        * contract_size
                    )
                    cash += gross
                    pos.lots *= 1.0 - partial_fraction
                    pos.sl = pos.entry_price
                    pos.partial_done = True

        # --- intrabar SL/TP (conservative: stop first) ----------------
        hit_sl = (pos.side > 0 and l[i] <= pos.sl) or (pos.side < 0 and h[i] >= pos.sl)
        hit_tp = (pos.side > 0 and h[i] >= pos.tp) or (pos.side < 0 and l[i] <= pos.tp)
        if hit_sl:
            close_trade(i, pos.sl, "stop_loss")
        elif hit_tp:
            close_trade(i, pos.tp, "take_profit")
        elif max_bars > 0 and pos is not None and pos.bars_held >= max_bars:
            close_trade(i, c[i], "max_bars")

    def close_trade(i: int, price: float, reason: str) -> None:
        nonlocal pos, cash
        assert pos is not None
        fill = price - pos.side * half_spread - pos.side * slip
        gross = pos.side * (fill - pos.entry_price) * pos.lots * contract_size
        cash += gross  # commission was already deducted at entry
        pnl_net = gross - pos.commission_paid
        trades.append(
            {
                "entry_time": str(pos.entry_time),
                "exit_time": str(df.index[i]),
                "side": "long" if pos.side > 0 else "short",
                "entry_price": round(pos.entry_price, 6),
                "exit_price": round(fill, 6),
                "lots": pos.lots,
                "bars_held": pos.bars_held,
                "pnl": round(pnl_net, 2),
                "pnl_pct": round(pnl_net / initial_capital * 100.0, 4),
                "exit_reason": reason,
            }
        )
        pos = None

    def open_trade(i: int, side: int, ref_atr: float) -> None:
        nonlocal pos, cash
        fill = o[i] + side * half_spread + side * slip
        stop_dist = sl_mult * ref_atr
        if stop_dist <= spread_points * point:
            return
        risk_amount = equity[i - 1] * risk_percent / 100.0
        lots = risk_amount / (stop_dist * contract_size)
        lots = min(max(lots, 0.01), max_lots)
        lots = math.floor(lots * 100.0) / 100.0
        if lots < 0.01:
            return
        commission = commission_per_lot * lots * 2.0  # round-trip, up front
        cash -= commission
        pos = _Position(
            side=side,
            entry_time=df.index[i],
            entry_price=fill,
            lots=lots,
            sl=fill - side * stop_dist,
            tp=fill + side * tp_mult * ref_atr,
            atr_entry=ref_atr,
            commission_paid=commission,
        )

    # ---------------- main loop ----------------
    for i in range(n):
        if pos is not None:
            equity[i] = cash + pos.side * (c[i] - pos.entry_price) * pos.lots * contract_size
        else:
            equity[i] = cash
        peak_equity = max(peak_equity, equity[i])

        # ---- day rollover + daily loss limit ----
        day = df.index[i].normalize()
        if day != current_day:
            current_day = day
            day_open_equity = equity[i]
            day_halted = False
        if (
            max_daily_loss_pct > 0
            and not day_halted
            and equity[i] <= day_open_equity * (1 - max_daily_loss_pct / 100.0)
        ):
            if pos is not None:
                close_trade(i, c[i], "daily_loss_limit")
            day_halted = True

        # ---- drawdown kill switch (permanent) ----
        if (
            max_drawdown_pct > 0
            and equity[i] <= peak_equity * (1 - max_drawdown_pct / 100.0)
        ):
            if pos is not None:
                close_trade(i, c[i], "max_drawdown")
            dd_halted = True

        # ---- manage open position ----
        if pos is not None:
            manage_position(i)
            if pos is None:  # closed during this bar
                equity[i] = cash

        # ---- entries ----
        if pos is None and not dd_halted and not day_halted and i >= 1:
            side = int(desired[i - 1])
            if side < 0 and not allow_short:
                side = 0
            if side != 0:
                ref_atr = atr_series[i - 1]
                if not np.isnan(ref_atr) and ref_atr > 0:
                    open_trade(i, side, ref_atr)
                    if pos is not None:
                        # resolve intrabar SL/TP on the entry bar itself
                        manage_position(i)
                        if pos is None:
                            equity[i] = cash

    # ---- finalise: close any open position at the last close ----
    if pos is not None:
        close_trade(n - 1, c[n - 1], "end_of_data")
    equity[n - 1] = cash

    equity_series = pd.Series(equity, index=df.index, name="equity")
    trades_df = pd.DataFrame(trades)

    from .metrics import compute_metrics

    metrics = compute_metrics(
        equity_series,
        trades_df,
        periods_per_year=_periods_per_year(df.index),
    )
    config = {
        "initial_capital": initial_capital,
        "risk_percent": risk_percent,
        "max_lots": max_lots,
        "allow_short": allow_short,
        "spread_points": spread_points,
        "slippage_points": slippage_points,
        "commission_per_lot": commission_per_lot,
        "trail_atr": trail_atr,
        "breakeven_atr": breakeven_atr,
        "partial_atr": partial_atr,
        "max_bars": max_bars,
        "max_daily_loss_pct": max_daily_loss_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "bars": int(n),
    }
    return BacktestResult(
        strategy=strategy_name,
        params=merged,
        config=config,
        trades=trades_df,
        equity=equity_series,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _periods_per_year(index: pd.DatetimeIndex) -> float:
    """Approximate bars per year from the median bar spacing."""
    if len(index) < 2:
        return 252.0
    delta = index.to_series().diff().dt.total_seconds().median()
    if pd.isna(delta) or delta <= 0:
        return 252.0
    return 365.25 * 24 * 3600 / delta


def _jsonable(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value
