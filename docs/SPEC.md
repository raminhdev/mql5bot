# 18. OUTPUT STYLE
Code, not essays. Comment intent and failure modes. Trade-offs go to `docs/DECISIONS.md`. If something is impossible in MQL5/Python, say so and provide the safest alternative — never silently degrade. When uncertain about a financial rule, choose the more conservative option and document it.

# 19. EXTERNAL REFERENCES (read-only inspiration; never copy code without review)
- MT5-in-Docker projects (e.g., vmlellis/mt5-docker, im-mahdi-74/Dockerized-MetaTrader5-with-Python-DataBridge): may be consulted ONLY in Release C for `backtest_runner` on Linux hosts. Windows portable MT5 remains the reference environment; any Wine-based results must be cross-checked against Windows before being used in gates. Document findings in docs/DECISIONS.md.
- Charting: no Highcharts (commercial license, JS framework). Visual verification uses matplotlib PNGs (spec 13). If interactive charts are ever needed, the only allowed library is TradingView `lightweight-charts` (Apache-2.0), loaded as a single static file, decided in DECISIONS.md first.
- Any third-party trading/signal code (e.g., AutoTradeSignal/core, paper_trading_view) must NOT be imported. Ideas only. Every external snippet, if any, requires: license check, line-by-line review note in docs/CODEGEN_REVIEW_CHECKLIST.md, and unit tests.
- ML datasets/targets (e.g., BTC target builders) are out of scope until v1.1 meta-labeling (spec 11, last bullet).
