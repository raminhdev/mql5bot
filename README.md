# mql5bot

**A full-stack algorithmic trading system for MetaTrader 5.**

[![CI](https://github.com/raminhdev/mql5bot/actions/workflows/ci.yml/badge.svg)](https://github.com/raminhdev/mql5bot/actions/workflows/ci.yml)

One codebase, two layers that stay in lockstep:

| Layer | Language | Location | Purpose |
|-------|----------|----------|---------|
| **Expert Advisor** | MQL5 | `mql5/` | Trades live in MetaTrader 5 |
| **Quant toolkit** | Python | `python/mql5bot/` | Mirrors the same strategies for rigorous backtesting, optimisation and monitoring |

## Status vocabulary (NOT synonyms)

Labels used across this repo and its docs:

- **IMPLEMENTED** — the code exists and is unit-tested.
- **RESEARCH-VALIDATED** — validated by the deterministic Python research pipeline on synthetic/owner-provided data.
- **MT5-VALIDATED** — proven in the MetaTrader 5 Strategy Tester (owner environment).
- **LIVE-VALIDATED** — proven with real money (demo counts separately).

Anything marked `BLOCKED_OWNER_ENVIRONMENT` requires the owner's Windows/MetaEditor/terminal; it is never converted to PASS by assumption.

## AEGIS autonomous strategy layer (Python)

On top of the quant toolkit, the repository now carries the AEGIS
autonomous strategy operating system (see `docs/AUTONOMOUS_STRATEGY_DISCOVERY.md`):

- **AEGIS Factory** — natural-language/community intake (EN/FA), deterministic DSL interpretation, statistical gates, evidence-bound lifecycle (`mql5bot/factory/`). IMPLEMENTED, RESEARCH-VALIDATED.
- **Indicator universe** — 71 contract-declared kinds (trend/momentum/volatility/volume/structure/candle/statistical/MTF) with causality property tests (`mql5bot/indicator_universe/`). IMPLEMENTED; MQL5 parity for new kinds BLOCKED_OWNER_ENVIRONMENT.
- **Discovery governance** — transparent 16-component Discovery Score, staged resumable campaigns, allocation governor, decay/recovery, kill switch + allocation circuit breaker + watchdog (`mql5bot/discovery/`). IMPLEMENTED.
- **Operator console** — FastAPI + Jinja2 + HTMX (no React): kanban lifecycle board, research intake, explicit human approvals, safety page (`mql5bot/api/`). IMPLEMENTED; UI can never mark a strategy LIVE (source-scan tested).

The EA's five built-in strategy engines remain the MQL5 execution truth; generated/DSL strategies reach MT5 through the same EA pipeline (compile/tester: BLOCKED_OWNER_ENVIRONMENT).

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
- **Broker spec + risk sizer** (`symbolspec.py`, `sizer.py`) — canonical, injected-broker-spec risk math (SPEC §3.3/§3.10 seed): tick-value sizing with profit-currency conversion, volume min/max/step/limit handling, stops-level enforcement, margin reduce/reject, Kelly capped at 0.25 and off by default, plus FNV-1a strategy-id → magic-number identity (SPEC §3.9). Unit-tested on five synthetic broker specs.
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
    symbolspec.py       canonical broker-symbol specs, normalisers, FNV-1a magic identity
    sizer.py            canonical risk sizer (injected specs, margin checks, capped Kelly)
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
tests/                  pytest suite
docs/                   SPEC (canonical), HANDOFF, implementation audit, decisions
.github/workflows/      CI: test matrix + CLI smoke test
```

## Testing

```bash
.venv/bin/python -m pytest
```

The suite includes a hard **no-lookahead test**: a "perfect oracle" strategy
that signals on a bar's close can only enter at the next bar's open, which
the test verifies trade-by-trade.

## Research evidence, not promises

- **Backtests are not a promise of live profit.** Every historical
  result in this repository — Python engine, walk-forward, staged
  pipeline, MT5 Strategy Tester — is research evidence produced under
  explicit modelling assumptions (fills, spreads, slippage, tick
  reconstruction), not a forecast and not a guarantee of live results.
- Certification follows the Phase-F real-tick protocol
  (`docs/CERTIFICATION.md`, `tools/certify_strategy.py`): M1 OHLC →
  Every Tick → Every Tick based on real ticks → Real ticks on the same
  EA, regime by regime (incl. the 2022 bear and crash windows), with a
  100-trade minimum, a spread floor, 0.5-3.0 pip slippage surcharge
  tiers and the OHLC-vs-tick degradation reported explicitly against
  the expected 30-50% band.  A result is VERIFIED only when every
  required leg actually ran and passed; otherwise the verdict is
  NOT VERIFIED with the reasons printed — never guessed, never
  fabricated.
- FAST/screening results are selection signals only — never final,
  never a profit claim.

## Safety

- Validate every parameter set in the Python backtest (with costs!) before running the EA live.
- Always start the EA on a **demo account**; the framework has no guarantee of profitability.
- Use the magic number to isolate the EA from manual positions, and the daily/drawdown limits as a last line of defence.

## License

MIT — see `LICENSE`.
