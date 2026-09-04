# AEGIS — TASKS.md

Derived from `docs/SPEC.md` §6 (canonical repository layout), §16 (workflow), §17 (Definition of Done).
One checkbox per deliverable file, in dependency/build order. Each phase ends with its test file(s) and a "docs updated" line.
Legend: `[ ]` = not started, `[x]` = done & pushed.

---

## Phase 0 — Plan & repo init (planning artifacts)

- [ ] TASKS.md — this checklist (planning session artifact)
- [ ] PROGRESS.md — session pointer (planning session artifact)
- [x] PING.md — bootstrap connectivity probe (created on `arena/01a06c21-mql5bot`; see Open Questions)
- [ ] README.md — project overview / quick start / Mermaid architecture / release table / risk defaults / FAQ / DISCLAIMER
- [ ] CHANGELOG.md — per-release change log
- [ ] DISCLAIMER.md — no-profit-claim disclaimer
- [ ] LICENSE — proprietary placeholder
- [ ] .gitignore
- [ ] .editorconfig

---

# Release A — `ea-core`

## Phase 1 — EA skeleton (compiles)

- [ ] ea/MQL5/Include/Aegis/Core/Constants.mqh
- [ ] ea/MQL5/Include/Aegis/Core/Errors.mqh
- [ ] ea/MQL5/Include/Aegis/Core/Version.mqh
- [ ] ea/MQL5/Include/Aegis/Core/Config.mqh
- [ ] ea/MQL5/Include/Aegis/Core/State.mqh
- [ ] ea/MQL5/Include/Aegis/Core/NewBar.mqh
- [ ] ea/MQL5/Include/Aegis/Core/Scheduler.mqh
- [ ] ea/MQL5/Include/Aegis/Core/Engine.mqh
- [ ] ea/MQL5/Experts/Aegis/Aegis.mq5
- [ ] ea/tools/compile.ps1
- [ ] ea/MQL5/Include/Aegis/Tests/TestFramework.mqh
- [ ] ea/MQL5/Scripts/Aegis/RunUnitTests.mq5
- [ ] docs updated (Phase 1): compile log notes + ARCHITECTURE skeleton

## Phase 2 — Core + Market + Execution + Risk + tests

Market (SSymbolSpec before RiskEngine):
- [ ] ea/MQL5/Include/Aegis/Market/SymbolSpec.mqh
- [ ] ea/MQL5/Include/Aegis/Market/SymbolCtx.mqh
- [ ] ea/MQL5/Include/Aegis/Market/ServerTime.mqh
- [ ] ea/MQL5/Include/Aegis/Market/Sessions.mqh
- [ ] ea/MQL5/Include/Aegis/Market/Data.mqh
- [ ] ea/MQL5/Include/Aegis/Market/IndicatorPool.mqh
- [ ] ea/MQL5/Include/Aegis/Market/News.mqh

Execution:
- [ ] ea/MQL5/Include/Aegis/Execution/RetCodes.mqh
- [ ] ea/MQL5/Include/Aegis/Execution/Normalizer.mqh
- [ ] ea/MQL5/Include/Aegis/Execution/FillingResolver.mqh
- [ ] ea/MQL5/Include/Aegis/Execution/RetryQueue.mqh
- [ ] ea/MQL5/Include/Aegis/Execution/OrderBook.mqh
- [ ] ea/MQL5/Include/Aegis/Execution/Executor.mqh
- [ ] ea/MQL5/Include/Aegis/Execution/ExecStats.mqh

Risk (sizer/stop-models before RiskEngine):
- [ ] ea/MQL5/Include/Aegis/Risk/PositionSizer.mqh
- [ ] ea/MQL5/Include/Aegis/Risk/StopModels.mqh
- [ ] ea/MQL5/Include/Aegis/Risk/Limits.mqh
- [ ] ea/MQL5/Include/Aegis/Risk/PortfolioHeat.mqh
- [ ] ea/MQL5/Include/Aegis/Risk/Exposure.mqh
- [ ] ea/MQL5/Include/Aegis/Risk/DrawdownScaler.mqh
- [ ] ea/MQL5/Include/Aegis/Risk/KillSwitch.mqh
- [ ] ea/MQL5/Include/Aegis/Risk/PropFirmRules.mqh
- [ ] ea/MQL5/Include/Aegis/Risk/RiskEngine.mqh

Tests:
- [ ] ea/MQL5/Include/Aegis/Tests/TestPositionSizer.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestNormalizer.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestStopModels.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestLimits.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestRetCodes.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestSessions.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestFillingResolver.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestHeatExposureDd.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestRiskEngine.mqh

Docs:
- [ ] docs/ARCHITECTURE.md
- [ ] docs/RISK_MODEL.md
- [ ] docs/EXECUTION.md
- [ ] docs/BROKER_COMPAT.md
- [ ] docs/TESTING.md
- [ ] docs updated (Phase 2)

## Phase 3 — Management + Filters + compiled strategies + tests

Strategy:
- [ ] ea/MQL5/Include/Aegis/Strategy/IStrategy.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/Signal.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/StrategyBase.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/MagicMap.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/StrategyRegistry.mqh

Compiled reference strategies:
- [ ] ea/MQL5/Include/Aegis/Strategies/MACrossTrend.mqh
- [ ] ea/MQL5/Include/Aegis/Strategies/RSIMeanReversion.mqh
- [ ] ea/MQL5/Include/Aegis/Strategies/RangeBreakout.mqh
- [ ] ea/MQL5/Include/Aegis/Strategies/DonchianTrend.mqh
- [ ] ea/MQL5/Include/Aegis/Strategies/TemplateStrategy.mqh
- [ ] ea/MQL5/Include/Aegis/Strategies/Generated/.gitkeep

Filters:
- [ ] ea/MQL5/Include/Aegis/Filters/IFilter.mqh
- [ ] ea/MQL5/Include/Aegis/Filters/FilterChain.mqh
- [ ] ea/MQL5/Include/Aegis/Filters/SpreadFilter.mqh
- [ ] ea/MQL5/Include/Aegis/Filters/SessionFilter.mqh
- [ ] ea/MQL5/Include/Aegis/Filters/NewsFilter.mqh
- [ ] ea/MQL5/Include/Aegis/Filters/VolatilityFilter.mqh
- [ ] ea/MQL5/Include/Aegis/Filters/DayOfWeekFilter.mqh
- [ ] ea/MQL5/Include/Aegis/Filters/CorrelationFilter.mqh
- [ ] ea/MQL5/Include/Aegis/Filters/RolloverFilter.mqh

Management:
- [ ] ea/MQL5/Include/Aegis/Management/Breakeven.mqh
- [ ] ea/MQL5/Include/Aegis/Management/Trailing.mqh
- [ ] ea/MQL5/Include/Aegis/Management/PartialClose.mqh
- [ ] ea/MQL5/Include/Aegis/Management/TimeExit.mqh
- [ ] ea/MQL5/Include/Aegis/Management/OCO.mqh
- [ ] ea/MQL5/Include/Aegis/Management/Pyramiding.mqh
- [ ] ea/MQL5/Include/Aegis/Management/Attribution.mqh

Tests:
- [ ] ea/MQL5/Include/Aegis/Tests/TestMagicMap.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestAttribution.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestFilters.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestManagement.mqh

Docs:
- [ ] docs/ADDING_A_STRATEGY.md
- [ ] docs updated (Phase 3)

## Phase 4 — UI + IO + Persistence + Recovery + FileContract

IO:
- [ ] ea/MQL5/Include/Aegis/IO/Logger.mqh
- [ ] ea/MQL5/Include/Aegis/IO/Notifier.mqh
- [ ] ea/MQL5/Include/Aegis/IO/Json.mqh
- [ ] ea/MQL5/Include/Aegis/IO/Persistence.mqh
- [ ] ea/MQL5/Include/Aegis/IO/FileContract.mqh
- [ ] ea/MQL5/Include/Aegis/IO/Heartbeat.mqh
- [ ] ea/MQL5/Include/Aegis/IO/TradeExport.mqh
- [ ] ea/MQL5/Include/Aegis/IO/CommandReader.mqh

UI:
- [ ] ea/MQL5/Include/Aegis/UI/Dpi.mqh
- [ ] ea/MQL5/Include/Aegis/UI/Theme.mqh
- [ ] ea/MQL5/Include/Aegis/UI/Widgets.mqh
- [ ] ea/MQL5/Include/Aegis/UI/Dashboard.mqh
- [ ] ea/MQL5/Include/Aegis/UI/Panels/.mqh

Recovery:
- [ ] ea/MQL5/Include/Aegis/Core/Recovery.mqh

Scripts:
- [ ] ea/MQL5/Scripts/Aegis/ExportTrades.mq5
- [ ] ea/MQL5/Scripts/Aegis/CloseAllByMagic.mq5
- [ ] ea/MQL5/Scripts/Aegis/SymbolAudit.mq5

File Contract schemas (java-side validation):
- [ ] schemas/allocation.schema.json
- [ ] schemas/command.schema.json
- [ ] schemas/heartbeat.schema.json
- [ ] schemas/trades.schema.json
- [ ] schemas/bundle.schema.json

Runtime samples:
- [ ] ea/MQL5/Files/Aegis/ (documented runtime folder + samples)

Tests:
- [ ] ea/MQL5/Include/Aegis/Tests/TestJson.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestFileContract.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestRecovery.mqh

Docs:
- [ ] docs/UI.md
- [ ] docs/FILE_CONTRACT.md
- [ ] docs/OPERATIONS_RUNBOOK.md
- [ ] docs updated (Phase 4)

## Phase 5 — sets, research tools, docs, self-review → tag

Sets:
- [ ] ea/sets/ conservative `.set` files per strategy/symbol/TF

Tools:
- [ ] ea/tools/run_tests.ps1
- [ ] ea/tools/package.ps1
- [ ] ea/tools/tester_ini.template

Research tools:
- [ ] research/walk_forward.py
- [ ] research/monte_carlo.py
- [ ] research/report_parser.py
- [ ] research/sample_data/ (sample data)
- [ ] research/README.md

Docs:
- [ ] docs/FAQ.md
- [ ] docs/DECISIONS.md (seeded with HANDOFF §4)

Self-review / tag:
- [ ] Self-review vs Release A DoD (items 1–31) + fix findings
- [ ] MQL5 compile log (0 errors / 0 warnings) + unit tests run
- [ ] git tag `A-ea-core`
- [ ] docs updated (Phase 5)

---

# Release B — `dsl`

## Phase 6 — DSL engine + tests

- [ ] schemas/strategy.schema.json
- [ ] ea/MQL5/Include/Aegis/Strategy/Dsl/Schema.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/Dsl/Expr.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/Dsl/Nodes.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/Dsl/IndicatorBinding.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/Dsl/Patterns.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/Dsl/Parser.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/Dsl/DslStrategy.mqh
- [ ] ea/MQL5/Include/Aegis/Strategy/Dsl/Loader.mqh

Tests:
- [ ] ea/MQL5/Include/Aegis/Tests/TestDslParser.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestDslOperators.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestDslPatterns.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestDslMtfNoLookahead.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestDslInvalidSpec.mqh

Docs:
- [ ] docs/DSL_REFERENCE.md
- [ ] docs updated (Phase 6)

## Phase 7 — examples + bundle + parity → docs → tag

Examples:
- [ ] examples/strategies/ — 10 DSL specs (incl. 4 reference strategies: MACrossTrend, RSIMeanReversion, RangeBreakout, DonchianTrend + 6 more)
- [ ] examples/strategies/ — 1 deliberately invalid spec (expected error)

Bundle / tester:
- [ ] ea/MQL5/Include/Aegis/Strategy/Dsl/Bundle.mqh

Tests:
- [ ] ea/MQL5/Include/Aegis/Tests/TestDslParity.mqh (compiled-vs-DSL parity for 4 reference strategies)
- [ ] ea/MQL5/Include/Aegis/Tests/TestDslBundleTester.mqh (bundle in Strategy Tester)

Docs:
- [ ] docs/CODEGEN_REVIEW_CHECKLIST.md
- [ ] docs updated (Phase 7)
- [ ] git tag `B-dsl`

---

# Release C — `factory-core`

## Phase 8 — Factory skeleton + DB + Kanban

- [ ] factory/pyproject.toml
- [ ] factory/main.py
- [ ] factory/app/__init__.py
- [ ] factory/app/routes/ (intake, strategy page, Kanban routes)
- [ ] factory/app/templates/ (Jinja2 + HTMX templates)
- [ ] factory/app/static/ (css/js)
- [ ] factory/models/ (SQLAlchemy models)
- [ ] factory/db/ (Alembic env + migrations)
- [ ] factory/gates.yaml
- [ ] .github/workflows/python-ci.yml

Tests:
- [ ] factory/tests/test_factory_app.py (one-command start, DB created, Kanban)

Docs:
- [ ] docs/FACTORY_GUIDE.md
- [ ] docs/LIFECYCLE_AND_GATES.md
- [ ] docs updated (Phase 8)

## Phase 9 — intake + spec builder + lints

- [ ] factory/importers/ (manual paste, URL, file/screenshot, generic_web)
- [ ] factory/spec_builder/ (LLM-assisted spec builder + restatement + ambiguity list)
- [ ] factory/providers/llm/ (OpenAI/Anthropic/local abstractions; keys from env)
- [ ] factory/providers/stt/ (speech-to-text abstraction)
- [ ] factory/lints/ (semantic lints: missing SL, lookahead, unbounded pyramiding, contradictory conditions, unrealistic TP/SL, regime declaration)

Tests:
- [ ] factory/tests/test_intake.py
- [ ] factory/tests/test_spec_builder.py
- [ ] factory/tests/test_lints.py

Docs:
- [ ] docs updated (Phase 9)

## Phase 10 — backtest runner + gates 1–2 + report parser

- [ ] ea/tools/run_backtest.ps1 (portable MT5 tester automation)
- [ ] factory/backtest_runner/ (terminal64 /config: automation)
- [ ] factory/gates/ (Gate1 Backtest, Gate2 Robustness, gate config)
- [ ] factory/export_parser/ (parse MT5 report exports)

Tests:
- [ ] factory/tests/test_backtest_runner.py
- [ ] factory/tests/test_gates.py
- [ ] factory/tests/test_report_parser.py

Docs:
- [ ] docs updated (Phase 10)

## Phase 11 — allocation + portfolio view + audit log → docs → tag

- [ ] factory/allocation/ (per-strategy weight, risk %, max concurrent, explanation fields)
- [ ] factory/portfolio/ (equity per strategy/combined, correlation heatmap, contribution, what-if)
- [ ] factory/audit_log/ (audit log model + audit of every action)
- [ ] factory/regime.yaml (regime config for weights) — see Phase 12 for engine

Tests:
- [ ] factory/tests/test_allocation.py
- [ ] factory/tests/test_allocation_clamps.py (clamps on synthetic degraded series)
- [ ] factory/tests/test_audit_log.py

Docs:
- [ ] docs/WEEKLY_ROUTINE.md
- [ ] docs updated (Phase 11)
- [ ] git tag `C-factory-core`

---

# Release D — `regime-meta`

## Phase 12 — Regime (EA + Py parity)

- [ ] ea/MQL5/Include/Aegis/Regime/Features.mqh
- [ ] ea/MQL5/Include/Aegis/Regime/RegimeConfig.mqh
- [ ] ea/MQL5/Include/Aegis/Regime/RegimeEngine.mqh
- [ ] factory/regime/regime_engine.py (Python mirror, own Wilder-smoothed indicators)
- [ ] factory/regime.yaml (feature lookbacks, thresholds, hysteresis N, dimensions)

Tests:
- [ ] ea/MQL5/Include/Aegis/Tests/TestRegimeFeatures.mqh
- [ ] ea/MQL5/Include/Aegis/Tests/TestRegimeHysteresis.mqh
- [ ] factory/tests/test_regime_parity.py

Docs:
- [ ] docs/REGIME_AND_META.md
- [ ] docs updated (Phase 12)

## Phase 13 — Meta-layer (EA Combiner + Factory weights + portfolio WFA)

Meta (EA):
- [ ] ea/MQL5/Include/Aegis/Meta/Eligibility.mqh
- [ ] ea/MQL5/Include/Aegis/Meta/Weights.mqh
- [ ] ea/MQL5/Include/Aegis/Meta/Combiner.mqh
- [ ] ea/MQL5/Include/Aegis/Meta/CombineModes.mqh
- [ ] ea/MQL5/Include/Aegis/Meta/ConflictMatrix.mqh

Meta (Factory):
- [ ] factory/meta/weights.py (gate_weight × regime_fit × performance × correlation_penalty × drift)
- [ ] research/portfolio_wfa.py (portfolio WFA vs equal-weight baseline)

Tests:
- [ ] ea/MQL5/Include/Aegis/Tests/TestCombiner.mqh (conflict matrix, weighted_netting, vote)
- [ ] ea/MQL5/Include/Aegis/Tests/TestMetaWeights.mqh (explainable, clamped, ≤15%/day, hard zeros)
- [ ] factory/tests/test_meta_weights.py
- [ ] factory/tests/test_portfolio_wfa.py

Docs:
- [ ] docs/REGIME_AND_META.md (combination modes + attribution)
- [ ] docs updated (Phase 13)

## Phase 14 — cost model, heat/exposure/DD, drift, data audit → docs → tag

- [ ] factory/costs/ (cost model per broker: spread, commission, swap incl. triple, slippage)
- [ ] factory/costs.example.yaml
- [ ] factory/drift/ (edge monitoring + SPC, Keep/Watch/Demote)
- [ ] tools/data_audit.py (gaps, spikes, weekend bars, DST anomalies)

Tests:
- [ ] factory/tests/test_costs.py
- [ ] factory/tests/test_drift.py (synthetic degraded series → demote recommendation)
- [ ] factory/tests/test_data_audit.py (flags corrupted sample)

Docs:
- [ ] docs/COST_MODEL.md
- [ ] docs updated (Phase 14)
- [ ] git tag `D-regime-meta`

---

# Release E — `nocode`

## Phase 15 — conversational flow + visual verification

- [ ] factory/chat/ (resumable state machine: intake → restatement → clarification → spec → approve)
- [ ] factory/visual_verification/ (headless quick backtest + matplotlib PNG candlestick charts of last 10–20 hypothetical trades)
- [ ] factory/providers/stt/ (voice → STT, provider abstracted)

Tests:
- [ ] factory/tests/test_conversational_flow.py
- [ ] factory/tests/test_visual_verification.py

Docs:
- [ ] docs updated (Phase 15)

## Phase 16 — Telegram + voice

- [ ] factory/telegram/ (bot, own token, whitelist owner chat_id)
- [ ] factory/telegram/voice.py (voice path via STT)

Tests:
- [ ] factory/tests/test_telegram.py (rejects non-whitelisted users)

Docs:
- [ ] docs updated (Phase 16)

## Phase 17 — i18n / RTL → docs → tag v1.0.0

- [ ] factory/i18n/fa.json
- [ ] factory/i18n/en.json
- [ ] factory/tests/test_i18n.py (completeness, RTL-safe)

Docs:
- [ ] docs updated (Phase 17)
- [ ] git tag `v1.0.0`

---

# Final — full self-review against DoD

- [ ] Full self-review against DoD items 1–55
- [ ] Fix findings, re-test, re-compile
- [ ] Final report (file tree, compile log, test summaries, DoD table, known limitations, next steps)

---

## DoD verification (items 1–55)

**Build & Git**
- [ ] 1. MQL5 compiles 0 errors / 0 warnings (log attached).
- [ ] 2. All MQL5 unit tests pass.
- [ ] 3. pytest + ruff green; CI green.
- [ ] 4. Every file has its own commit; no >1 uncommitted file at any point.
- [ ] 5. Session-resume test performed and described.
- [ ] 6. Tags per release + v1.0.0; pushed or blocked with explicit credential request.
- [ ] 7. No secrets committed; no profit claims.

**EA safety**
- [ ] 8. No position without SL (code path + test).
- [ ] 9. Lot sizing correct on 5 synthetic specs (table).
- [ ] 10. Stops/freeze respected; invalid stops never sent.
- [ ] 11. Filling mode dynamic; no hardcoded `ORDER*FILLING*`.
- [ ] 12. Retry queue without Sleep; fatal codes not retried.
- [ ] 13. Daily/weekly/DD/consecutive limits trigger and persist across restart.
- [ ] 14. Kill switch from UI, GlobalVariable, hotkey, Factory command, auto; explicit reset.
- [ ] 15. Restart recovery adopts positions via Magic + ticket map.
- [ ] 16. No double entry per bar.
- [ ] 17. No indicator handle leaks.
- [ ] 18. Works on hedging and netting.
- [ ] 19. Every input validated → `INIT_PARAMETERS_INCORRECT`.
- [ ] 20. Martingale absent; grid capped, off by default.
- [ ] 21. MagicMap stable across add/remove/reload.

**UI / IO**
- [ ] 22. UI DPI scaling math documented; no flicker; clean removal; hidden in optimization; correct digits; destructive buttons confirm.
- [ ] 23. Logger never throws; no file I/O in optimization.
- [ ] 24. WebRequest/Calendar skipped in tester; Telegram failures never block; separate tokens.
- [ ] 25. Sessions handle DST and midnight windows.
- [ ] 26. File contract implemented with atomic writes and schema validation both sides; heartbeat/trades/commands verified.

**DSL**
- [ ] 27. 10 specs load, validate, trade in tester; invalid spec rejected with precise error.
- [ ] 28. No lookahead (test).
- [ ] 29. Compiled-vs-DSL parity for 4 reference strategies.
- [ ] 30. Bundle works in Strategy Tester.
- [ ] 31. Adding a strategy: compiled = 1 file + 1 line; DSL = 1 JSON, no recompile.

**Factory**
- [ ] 32. One-command start; DB created; Kanban; paste → spec + questions → validate → written to EA folder.
- [ ] 33. Gate thresholds configurable and enforced; status skipping impossible via UI/API.
- [ ] 34. Live EA refuses specs below live_small (logged + alerted).
- [ ] 35. Allocation hot-reload changes position sizing; stale/missing allocation handled.
- [ ] 36. Factory has zero trading code paths (lint/test).
- [ ] 37. Backtest automation documented and run on a sample.
- [ ] 38. OOS budget enforced.
- [ ] 39. Audit log complete.

**Regime / Meta / Profitability**
- [ ] 40. Regime labels stable under ±10% thresholds; EA/Py parity passes.
- [ ] 41. Forbidden regimes block signals (test).
- [ ] 42. Weights explainable, clamped, ≤15%/day; hard zeros work.
- [ ] 43. weighted_netting never holds opposite positions on one symbol; attribution sums to 100%.
- [ ] 44. vote respects K and scales size.
- [ ] 45. Portfolio WFA report vs equal-weight exists; default documented.
- [ ] 46. Cost model in gates; Edge-to-Cost enforced; live cost deviation alert.
- [ ] 47. Heat/exposure/DD scaling enforced with numbers.
- [ ] 48. Data audit flags corrupted sample.
- [ ] 49. Drift triggers demote recommendation on synthetic series.
- [ ] 50. Nothing in regime/meta/factory bypasses Risk Engine or kill switch (test).

**No-code**
- [ ] 51. Persian end-to-end: description → restatement → questions → spec → visual charts → approve, no JSON.
- [ ] 52. Telegram rejects non-whitelisted users; voice path works or provider need documented.
- [ ] 53. Natural-language edit → new version through gates; old version untouched.
- [ ] 54. All owner-facing strings fa/en; RTL-safe.

**Docs**
- [ ] 55. All docs in tree complete; DISCLAIMER present; known limitations honestly listed; self-review issues found and fixed are listed.
