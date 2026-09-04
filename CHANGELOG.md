# Changelog

All notable changes to mql5bot are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-09-04

### Added

**MQL5 Expert Advisor** (`mql5/`)
- `Mql5Bot.mq5` main EA with 5 strategies: EMA crossover, RSI reversal,
  Donchian breakout, Bollinger reversal, MACD momentum
- `RiskManager.mqh` — risk-based position sizing, daily loss limit,
  drawdown kill-switch, spread guard
- `TradeManager.mqh` — market & pending stop-order execution with retry
  logic, fill verification via deal history, hedging/netting safe
- `PositionGuard.mqh` — ATR trailing stop, breakeven, partial scale-out
- `SignalEngine.mqh` — completed-bar-only strategy evaluation (no repaint)
- `Session.mqh` — days-of-week bitmask + intraday trading window
- `Logger.mqh` — leveled file + terminal logging
- `Telemetry.mqh` — HTTP heartbeat/trade/alert reporting (WebRequest)
- `Mql5BotDownloadData.mq5` script — export bar history to CSV for the
  Python toolkit
- Presets for all 5 strategies (`mql5/Presets/Mql5Bot/`)

**Python quant toolkit** (`python/mql5bot/`)
- Vectorized strategy twins with an identical evaluation contract
- Event-driven backtest engine: lookahead-proof entries, intrabar stop
  simulation, spread/slippage/commission cost model, risk-based sizing,
  trailing/breakeven/partial exits, daily-loss & drawdown kill switches
- Performance metrics: CAGR, Sharpe, Sortino, max drawdown & duration,
  Calmar, win rate, profit factor, payoff, expectancy
- Grid-search optimiser (multiprocessed) and walk-forward validation
- Self-contained interactive HTML reports
- Live web dashboard with simulated or MT5-bridged bar feed
- Telemetry bridge — HTTP collector for EA events (JSONL + SSE stream)
- CLI (`mql5bot`) with data / backtest / compare / optimize / walkforward /
  dashboard subcommands
- Reproducible synthetic OHLC generator, CSV loader, live MT5 bridge

**Tooling & QA**
- 36-test pytest suite, including a hard no-lookahead oracle test and an
  exact commission-accounting test
- GitHub Actions CI: test matrix (Python 3.10–3.12) + CLI smoke test
- `scripts/install_mql5.py` — one-command deployment into the MT5 data
  folder (auto-detection on Windows/macOS/Linux-Wine)

[1.0.0]: https://github.com/raminhdev/mql5bot/releases/tag/v1.0.0
