# Changelog

All notable changes to mql5bot are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — Aegis Release A foundation (audit + canonical risk models)

### Added
- `docs/IMPLEMENTATION_AUDIT.md` — full evidence-based audit of the repository
  against `docs/SPEC.md` (v4): architecture, implemented features, release
  readiness (A ≈ 25–30 %, B–E 0 %), missing/broken requirements, safety-critical
  gaps (ranked S1–S11), and the exact recommended implementation order.
- `docs/DECISIONS.md` — decisions log (SPEC §24): layout-preservation decision,
  Python-first canonical model decision, SPEC §19 reconciliation, version
  naming; carries the earlier decisions from HANDOFF §4.
- `python/mql5bot/symbolspec.py` — canonical broker `SymbolSpec` + pure
  normalisers (tick rounding, stops-level enforcement, volume min/max/step/
  limit, profit-currency loss-per-lot) + FNV-1a 32-bit magic derivation with a
  persistent, collision-safe `MagicRegistry` (SPEC §3.3/§3.9/§3.10 seed).
- `python/mql5bot/sizer.py` — canonical risk sizer on injected specs: fixed
  lot, risk % equity/balance, fixed money, Kelly capped at 0.25 (off by
  default); floor-to-step volume (never over-risk), below-min rejection,
  max/limit clamping, injected margin-calc reduce/reject (SPEC §8.C).
- `tests/test_symbolspec.py`, `tests/test_sizer.py` — 41 new tests incl. the
  five synthetic broker specs (EURUSD 5-digit, USDJPY, XAUUSD, US30-like,
  BTCUSD-like), FNV-1a vectors, registry stability across removal/reload,
  margin rejection, risk-budget invariant sweep.
- Suite now 80 tests (`pytest tests/` green in this environment).

### MQL5 hardening — Phase-1 DoD (S4 SymbolSpec)
- `mql5/Include/Mql5Bot/SymbolSpec.mqh` — MQL5 port of the canonical broker
  `SymbolSpec`: runtime `BuildSymbolSpec` querying every broker fact
  (SPEC §3.3), tick-grid/volume/stop normalisers and loss-per-lot math
  (SPEC §3.10) byte-parallel to `python/mql5bot/symbolspec.py`; the pure
  helpers are verified by the existing synthetic-spec test vectors
  (`tests/test_symbolspec.py`) on the Python side, which the port mirrors.

### Notes
- MQL5 `CRiskManager`/`CTradeManager` intentionally untouched this session —
  the Python models above are the compile-verified-port target for the next
  (Windows/MetaEditor) session; see `docs/IMPLEMENTATION_AUDIT.md` §17.
- "COMPILE NOT VERIFIED — MetaEditor unavailable in this environment."

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
