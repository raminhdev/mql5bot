# AEGIS — PROJECT HANDOFF (mental roadmap, decisions, state, todo)
Read this together with `docs/SPEC.md` (v4). SPEC is canonical for WHAT to build; this file is canonical for WHERE we are, WHY decisions were made, and WHAT to do next. If they conflict, SPEC wins for engineering, this file wins for process/state.

---
## 0. One-paragraph summary
Owner (Persian-speaking, non-programmer, trades via MetaTrader 5) wants an automated trading system where he can describe strategies in plain language (sourced weekly from a public strategy-sharing website), have them turned into executable logic, validated statistically, selected/combined intelligently by market regime, and traded with strict risk controls. We designed **Aegis**: (1) **Aegis-EA** — an MQL5 execution/risk framework with a JSON strategy DSL interpreter; (2) **Aegis-Factory** — a Python "strategy CRM" that converts descriptions → DSL specs → statistical gates → allocation → monitoring/retirement. Core philosophy: **strategies are data; the framework makes losing money due to bugs, mis-sizing, missing stops, broker quirks, overfitting or human error as close to impossible as engineering allows. No profit claims, ever.**

---
## 1. Owner profile & goals (do not lose these)
- Not a programmer. Must add/edit strategies by describing them (Persian or English, text or voice, web or Telegram). Never touches code or JSON.
- Wants: multiple strategies checked simultaneously; automatic selection of the one(s) fitting current market conditions, or a combination.
- Wants: SL/TP and "everything needed for profitability" — we translated that into: risk engine, cost model, execution quality, regime engine, meta-layer, drift detection, statistical gates.
- Wants: zero tolerance for bugs incl. UI, because it is real money.
- Environment: agent runs on **Arena AI**, connected to GitHub repo `raminhdev/mql5bot`. Arena has an ephemeral sandbox and pushes to its own branch `arena/<id>-mql5bot`. Arena's chat paste fields DROP long text → long documents must be put in the repo via GitHub web UI by the owner, not pasted in chat.

---
## 2. Honest assumptions we told the owner (keep repeating them)
- No bot/prompt gives guaranteed profit. 90%+ of public strategies have no edge or are curve-fit; weekly rotation without statistical gates = random trading minus costs.
- The value is the **factory + filter**: intake 20–50 strategies/week, validate brutally, discard ~95%, demo the rest, promote only survivors with small risk, retire losers automatically. Expect 1–2 strategies/month reaching live-small.
- Any "intelligent" selector must be validated like a strategy and must beat equal-weight out-of-sample, otherwise default to equal-weight.
- Realistic outcome of a correct system: controlled drawdown and moderate, steady returns — not monthly doubling.
- Check the source website's Terms of Service before scraping; importer defaults to manual paste.

---
## 3. Evolution of the spec (why v4 looks like it does)
- **v1** (EA framework): modular EA, IStrategy interface, Risk Engine veto, Execution with retry, filters, dashboard UI, tests, docs, DoD 1–30.
- **v2** additions: crash-resilient git protocol (one file = one commit = one push; TASKS.md/PROGRESS.md), **Strategy DSL** (strategies as JSON, no recompile), **Factory/CRM** (intake → spec → gates → allocation → Kanban), DoD 31–40.
- **v3** additions: **Regime Engine** (rule-based, EA+Python parity), **Meta-Layer** (eligibility, slow-moving explainable weights, combination modes independent/weighted_netting/vote/best_of_regime), **Profitability Essentials** (cost model, portfolio heat, currency exposure, DD scaler, vol targeting, execution quality, data audit, drift/SPC), **No-code conversational intake** (restatement → clarification → visual verification with charts of last 10–20 hypothetical trades → approve), DoD 41–55.
- **v4 (current, canonical)**: consolidation after two line-by-line review passes. Fixed contradictions and money-losing bugs (see §5). Introduced **5 independently usable releases A–E**, a single repo layout, a **File Contract** between EA and Factory, and unified DoD (55 items).

---
## 4. Key architectural decisions (already made; change only via docs/DECISIONS.md)
1. Signal/Risk separation: strategies emit signals; Meta-layer and Risk Engine veto; Factory never trades (files only).
2. Every position always has SL; failure to set SL → close + CRITICAL.
3. Query broker specs at runtime; all risk math on injected `SSymbolSpec` struct (unit-testable with synthetic specs).
4. Stable identity: Magic = FNV-1a hash of `strategy_id` into reserved range, persisted in MagicMap; never index-based.
5. Attribution/management state persisted by `POSITION_IDENTIFIER` in files, NOT in position comment (brokers overwrite comments; ~31 char limit).
6. No `Sleep()`; retries via `RetryQueue` processed in OnTimer with backoff.
7. Strategy Tester: DSL specs delivered as a single bundle via `#property tester_file`; WebRequest/Calendar skipped in tester.
8. Releases A→E gated by DoD; do not start N+1 before N is tagged.
9. Reference strategies exist both compiled and as DSL; bar-by-bar parity test is the golden test of the DSL engine.
10. Combination default = `weighted_netting` (one book position per symbol; net opposite signals; pro-rata attribution).
11. Weights: gate_weight × regime_fit × performance_factor × correlation_penalty × drift_factor; adaptive part clamped [0.25,1.5], ≤ ±15%/day; hard zeros allowed; daily cadence only; ≤10 meta params.
12. Gates: Gate3 demo = ≥4 weeks AND ≥30 trades (low-frequency exception documented). OOS budget: one look per strategy version.
13. Kelly sizing capped ≤0.25 Kelly, off by default. Martingale forbidden; grid off by default and hard-capped.
14. Two separate Telegram bot tokens (EA vs Factory).
15. Factory: Python 3.11+, FastAPI, SQLite, Jinja2+HTMX (no JS framework), binds 127.0.0.1 with password from env. MQL5 compile is local-only (PowerShell); GitHub CI only for Python.
16. Server GMT offset estimated from `TimeCurrent()−TimeGMT()` when connected, persisted.
17. External repos: read-only inspiration; no third-party trading code imported; no Highcharts (license); if interactive charts ever needed → TradingView lightweight-charts only, decided in DECISIONS.md first (SPEC §19).

---
## 5. Review findings already folded into SPEC v4 (so the next AI doesn't re-introduce them)
Contradictions removed: two repo layouts → one; three workflows → one; three DoD lists → one; "Python only" vs React/PowerShell → explicit language list; impossible MQL5 CI → local script; compiled vs DSL strategies → both + parity; missing final-report requirement → restored.
Money-losing bugs fixed: index-based Magic; attribution in comment; weight clamp vs zero weights; Gate3 "OR"; Sleep vs retry; DSL files unavailable in tester sandbox; duplicate bot token; WebRequest/Calendar in tester; lot tests tied to broker symbol names; Python/TA-Lib indicator init mismatch (own Wilder implementation + tolerance); undefined data source for visual verification (headless tester exports CSV, Python renders); no EA⇄Factory contract (added File Contract with atomic writes + schemas); Factory offline/no LLM key behavior; recovery via comment; uncapped Kelly; missing GMT offset API; Factory web security.

---
## 6. What ACTUALLY happened with the Arena agent (state history)
1. Session 1: agent received the giant prompt, generated a lot, **pushed nothing**; connection dropped; everything lost.
2. Diagnosis: (a) huge single-session prompt → agent deferred first push; (b) possible read-only/insufficient git scope; (c) ephemeral sandbox. Fix: split into tiny sessions, first push within 2 minutes, spec lives in repo.
3. Bootstrap session: **push works**. Agent created `PING.md` on branch `arena/01a06c21-mql5bot`, based on latest `main` (`a82c1cd`).
4. Next session: agent (correctly) refused to invent `TASKS.md`/`docs/SPEC.md` because instructions said "do not re-plan", and reported both are **absent from the repo**. Owner's pastes into Arena arrived empty.
5. Owner found 6 external repos (mt5-docker ×2, highcharts, paper_trading_view, BTC target builder, AutoTradeSignal/core). Evaluated in §4.17 / SPEC §19: reference only, no imports.

### Current repo state (as far as known — VERIFY FIRST)
- `main`: README (+ whatever owner added). Commit `a82c1cd` was latest main at bootstrap time.
- `arena/01a06c21-mql5bot`: `PING.md` only.
- **Missing:** `docs/SPEC.md`, `TASKS.md`, `PROGRESS.md`, any code. Nothing has been merged back to main yet (unless owner did it).

---
## 7. Operating model (process rules — mandatory)
- Long documents (SPEC, HANDOFF) go into the repo via GitHub web UI by the owner; chat carries only short session prompts.
- **Session size:** ≤10–12 files per session. One file → `git add <file> TASKS.md PROGRESS.md` → commit → push → paste hash. Stop after 3 failed pushes.
- Each session starts from latest `main`; Arena will create/use its own `arena/*` branch — acceptable. **After every session the owner opens a PR `arena/* → main` and merges.** main = source of truth.
- Owner's per-session check: number of commits ≈ number of files; PROGRESS.md updated; no files outside the list.
- Release gating: A (ea-core) → B (dsl) → C (factory-core) → D (regime-meta) → E (nocode). Tag each. Put Release A on a demo account before investing in later releases.
- After each release: run a **Red Team review** session with a fresh agent ("how can this system lose money?"), fix findings, then proceed.
- Never paste external repo links into work-session prompts (derails the agent); policy lives in SPEC §19.

---
## 8. Session prompt templates (use verbatim)
### 8.1 Planning session (run once, after SPEC.md is in main)
PLANNING SESSION — the only outputs are TASKS.md and PROGRESS.md. No project code.
1. git fetch; git checkout main; git pull. Paste `git log --oneline -5` (must include "docs: add master spec v4").
2. Read docs/SPEC.md COMPLETELY (all 19 sections). If missing or truncated, STOP and tell me.
3. Create TASKS.md from SPEC §6 (layout), §16 (workflow), §17 (DoD): Release A–E → Phase → one checkbox line per FILE, in dependency/build order; each phase ends with its test file(s) and a "docs updated" line; final "DoD verification" section listing items 1–55; mark PING.md done, nothing else.
4. Create PROGRESS.md: current_release A, current_phase 1, current_file none, next_3_steps (first 3 unchecked files), unpushed false, open_questions [].
5. Commit and push each file SEPARATELY. Paste both hashes.
6. End with `git log origin/<branch> --oneline -10` and the exact branch name. Do not start Phase 1.

### 8.2 Work session (repeat until done)
WORK SESSION.
1. git fetch; git checkout main; git pull. If Arena forces its own branch, branch it FROM latest main. Paste `git log --oneline -5`.
2. Read docs/SPEC.md, TASKS.md, PROGRESS.md. Paste PROGRESS.md. Do not re-plan.
3. Take the FIRST 10 unchecked files from TASKS.md in order. Paste the list before starting.
4. ONE FILE → git add <file> TASKS.md PROGRESS.md → commit → push → paste hash. Only then the next file.
5. If a push fails 3 times, STOP and report.
6. After the 10 files (or when a phase ends): update PROGRESS.md (next 3 steps), push, end with `git log origin/<branch> --oneline -15` and the branch name for me to merge.
7. Touch nothing outside these files except TASKS.md / PROGRESS.md.

### 8.3 Red Team session (after each release tag)
RED TEAM REVIEW — no new features. Read docs/SPEC.md and the code of Release <X>. Produce docs/REDTEAM_<X>.md listing every way this release could lose money or violate SPEC §3 principles (execution, sizing, stops, recovery, netting/hedging, tester vs live, file contract, UI), each with severity, evidence (file:line), and a concrete fix. Then fix CRITICAL/HIGH items one file per commit, re-run tests, update CHANGELOG.

---
## 9. TODO — intended but NOT yet applied (ordered)
**Immediate (owner + agent)**
- [ ] Owner: create `docs/SPEC.md` on `main` via GitHub web UI (full v4 text + §19). Verify not truncated (ends with §19).
- [ ] Owner: create `HANDOFF.md` on `main` (this file).
- [ ] Owner: merge `arena/01a06c21-mql5bot` → `main` (PING.md) so the branch and main converge.
- [ ] Agent: Planning session (§8.1) → TASKS.md + PROGRESS.md. Owner merges. Owner sends TASKS.md text to a reviewing AI to check dependency order/completeness before coding.
- [ ] Agent: Work sessions for Release A (§8.2), ~10 files each. Owner merges after each.

**Golden reference files I intended to write (high leverage: they prevent agent drift) — not yet written**
- [ ] `schemas/strategy.schema.json` — complete DSL v1 JSON schema (meta, indicators, conditions, entry, exit, filters, risk overrides, regimes, vol_targeting, params, requires_codegen).
- [ ] `factory/regime.yaml` — feature lookbacks, thresholds, hysteresis N, dimensions.
- [ ] `factory/gates.yaml` — the numeric thresholds from SPEC §10.4 as config.
- [ ] `examples/strategies/*.json` — the 4 reference strategies in DSL (MACrossTrend, RSIMeanReversion, RangeBreakout, DonchianTrend) + 6 more + 1 invalid.
- [ ] `docs/FILE_CONTRACT.md` with all 6 JSON schemas (allocation, command, heartbeat, trades, bundle, correlation).
- [ ] A sample Persian intake conversation (description → restatement → questions → approval) as a golden example for Release E.
- [ ] `docs/DECISIONS.md` seeded with §4 of this handoff.

**Process**
- [ ] Red Team session after Release A, B, C, D, E.
- [ ] Owner: ≥4 weeks demo on the target broker for Release A before enabling anything from C/D/E on live money; verify restart recovery, kill switch, netting/hedging manually.
- [ ] Consider moving from Arena to a local agent (Claude Code / Codex CLI / Cursor on the owner's PC or Windows VPS) so files persist on disk even if the agent disconnects; the same prompts work.

---
## 10. Risks & warnings for the next AI
- MetaEditor compile cannot run in the agent sandbox; agent must write code carefully and the owner (or a Windows agent) runs `tools/compile.ps1` and feeds back errors. Never claim "compiles" without a log.
- Arena chat loses long pastes; keep everything in the repo.
- Wine/Docker MT5 results may differ from Windows; only Windows portable MT5 is the reference for gates.
- Do not add ML before the rule-based system is stable (meta-labeling is v1.1, flagged, ≥300 live trades).
- Do not "simplify" the risk engine, magic map, attribution persistence or file contract — each fix in §5 corresponds to a real-money failure mode.
- Any deviation from SPEC must be recorded in docs/DECISIONS.md with rationale; conservative option wins when uncertain.
- Never write marketing language or profitability claims in code, docs, UI or Telegram messages.

---
## 11. Definition of "we are on track" (owner's weekly self-check)
- `main` has SPEC.md, HANDOFF.md, TASKS.md, PROGRESS.md and code; `git log` shows one commit per file.
- Current release's phase in PROGRESS.md matches ticked items in TASKS.md.
- Compile log with 0 warnings exists for the latest EA state; MQL5 unit tests and pytest pass.
- No unmerged `arena/*` branch older than one session.
- Release tags exist for finished releases; Red Team doc exists per finished release.
