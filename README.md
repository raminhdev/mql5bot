# mql5bot

**A full-stack algorithmic trading system for MetaTrader 5.**

[![CI](https://github.com/raminhdev/mql5bot/actions/workflows/ci.yml/badge.svg)](https://github.com/raminhdev/mql5bot/actions/workflows/ci.yml)

One codebase, two layers that stay in lockstep:

| Layer | Language | Location | Purpose |
|-------|----------|----------|---------|
| **Expert Advisor** | MQL5 | `mql5/` | Trades live in MetaTrader 5 |
| **Quant toolkit** | Python | `python/mql5bot/` | Mirrors the same strategies for rigorous backtesting, optimisation and monitoring |

## Features

### MQL5 Expert Advisor (`mql5/Experts/Mql5Bot/Mql5Bot.mq5`)
- **5 strategies** — EMA crossover, RSI reversal, Donchian breakout, Bollinger reversal, MACD momentum
- **Risk management** — risk-based position sizing, daily loss limit, drawdown kill-switch, spread guard
- **Exit management** — ATR trailing stop, breakeven, partial scale-out, max-bars timeout
- **Execution** — market or pending-stop entries, retry logic with fill verification, hedging/netting safe, magic-number isolation
- **Session filter** — days-of-week bitmask + intraday trading window
- **Observability** — file logger with levels, HTTP telemetry (heartbeat / trade / alert events) to any webhook or the included Python collector

### Python quant toolkit (`python/mql5bot/`)
- **Strategies** — vectorized twins of the MQL5 strategies (`strategies.py`)
- **Backtest engine** — event-driven, lookahead-proof (entries at next open), intrabar stop simulation, spread/slippage/commission model, risk-based sizing, trailing/breakeven/partial exits, daily-loss and drawdown kill switches
- **Metrics** — CAGR, Sharpe, Sortino, max drawdown & duration, Calmar, win rate, profit factor, expectancy
- **Optimiser** — grid search (multiprocessed) and walk-forward validation
- **Reports** — self-contained interactive HTML reports with equity/drawdown charts
- **Dashboard** — live web dashboard with a growing bar feed (`mql5bot dashboard`)
- **Telemetry bridge** — HTTP collector for the EA's events
- **Data** — CSV loading (MT5 export compatible), reproducible synthetic OHLC generator, live MT5 bridge (`MetaTrader5` package, optional)

## Quick start

```bash
# 1. Install the Python toolkit
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# 2. Generate data (or export from MT5: File -> Save As... CSV)
mql5bot data --symbol EURUSD --timeframe H1 --days 730 --out data/EURUSD_H1.csv

# 3. Backtest a strategy with realistic costs
mql5bot backtest --data data/EURUSD_H1.csv --strategy ema_crossover \
    --spread 1.0 --slippage 0.5 --commission 7 --risk 1 \
    --trail 2.5 --daily-loss 5 --report results/report.html

# 4. Compare all strategies
mql5bot compare --data data/EURUSD_H1.csv --report results/compare.html

# 5. Optimise parameters
mql5bot optimize --data data/EURUSD_H1.csv --strategy ema_crossover \
    --grid '{"fast":[8,10,12,16],"slow":[25,30,40]}' --jobs 4

# 6. Live dashboard
mql5bot dashboard --port 8000
```

Or from Python:

```python
from mql5bot import generate_ohlc, run_backtest, save_report_html

df = generate_ohlc(days=730, timeframe="H1", seed=42)
res = run_backtest(df, "ema_crossover", risk_percent=1.0,
                   spread_points=1.0, commission_per_lot=7.0,
                   trail_atr=2.5, max_daily_loss_pct=5.0)
print(res.metrics)
save_report_html(res, "results/report.html")
```

### Installing the Expert Advisor

One command (auto-detects the MT5 data folder on Windows / macOS / Linux-Wine):

```bash
python scripts/install_mql5.py                 # or --folder <path> if not detected
```

This copies the EA, include modules, the data-export script and the 5
strategy presets into your terminal's data folder. Or do it manually:

1. Copy `mql5/Include/Mql5Bot/` → `<MT5 Data Folder>/MQL5/Include/Mql5Bot/`
2. Copy `mql5/Experts/Mql5Bot/Mql5Bot.mq5` → `<MT5 Data Folder>/MQL5/Experts/Mql5Bot/`
3. Compile in MetaEditor (F7), then drag the EA onto a chart and pick a
   preset from the **Inputs** tab (`ema_crossover`, `rsi_reversal`,
   `donchian_breakout`, `bollinger_reversal`, `macd_momentum`).
4. If using telemetry, add your collector URL to
   **Tools → Options → Expert Advisors → Allow WebRequest for listed URL**.
   *(The compile step requires MetaEditor on Windows — it can't run in this repository's environment.)*

### Feeding the Python toolkit with real MT5 data

1. Attach `Scripts/Mql5Bot/Mql5BotDownloadData.mq5` to a chart and run it —
   it exports bar history to `MQL5/Files/` as a CSV the Python loader accepts.
2. Point the CLI at that file:

```bash
mql5bot backtest --data "<MT5 data>/MQL5/Files/mql5bot_export.csv" --strategy ema_crossover
```

Or pull bars live with the optional MT5 bridge (`pip install MetaTrader5`,
Windows only): `from mql5bot import load_mt5`.

## Strategy ↔ backtest parity

The Python strategies and the MQL5 `CSignalEngine` are deliberate twins:

- Indicators are evaluated only on **completed bars** (shift ≥ 1 in MQL5, desired-position lag in Python).
- Stop/target distances are the same ATR multiples (`sl_atr`, `tp_atr`).
- Position sizing risks the same fraction of equity over the stop distance.
- The Python backtest adds a conservative cost model (full spread round trip, slippage, commission) so its results are a *pessimistic* estimate of what the EA will do on a demo account.

## Repository layout

```
mql5/
  Experts/Mql5Bot/Mql5Bot.mq5      the Expert Advisor
  Scripts/Mql5Bot/Mql5BotDownloadData.mq5  CSV bar-history exporter
  Presets/Mql5Bot/*.set            5 ready-to-load strategy presets
  Include/Mql5Bot/
    Config.mqh          types, enums, constants, lot helpers
    Logger.mqh          file + terminal logger
    Session.mqh         trading session filter
    RiskManager.mqh     sizing, daily loss, drawdown kill-switch, spread guard
    TradeManager.mqh    market/pending execution, retries, fill verification
    PositionGuard.mqh   ATR trailing, breakeven, partial scale-out
    SignalEngine.mqh    5 strategy engines
    Telemetry.mqh       HTTP event reporting (WebRequest)
scripts/
  install_mql5.py       one-command deployment into the MT5 data folder
python/
  mql5bot/
    strategies.py       vectorized strategy twins + registry
    indicators.py       EMA/SMA/RSI/Bollinger/ATR/Donchian/MACD
    backtest.py         event-driven backtest engine
    metrics.py          performance statistics
    optimizer.py        grid search + walk-forward
    report.py           standalone HTML reports
    dashboard.py        live dashboard server
    telemetry_bridge.py HTTP collector for EA events
    data.py             CSV/synthetic/MT5 data layer
    cli.py              command line interface
tests/                  pytest suite (39 tests)
.github/workflows/      CI: test matrix + CLI smoke test
```

## Testing

```bash
.venv/bin/python -m pytest
```

The suite includes a hard **no-lookahead test**: a "perfect oracle" strategy
that signals on a bar's close can only enter at the next bar's open, which
the test verifies trade-by-trade.

## Safety

- Validate every parameter set in the Python backtest (with costs!) before running the EA live.
- Always start the EA on a **demo account**; the framework has no guarantee of profitability.
- Use the magic number to isolate the EA from manual positions, and the daily/drawdown limits as a last line of defence.

## License

MIT — see `LICENSE`.
