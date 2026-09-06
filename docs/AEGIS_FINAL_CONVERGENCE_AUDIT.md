# AEGIS Final Convergence Audit

**Mission:** final convergence (§1–§86). **Branch:** `arena/01a070b0-mql5bot`.
This document records the pre-coding audit, the legacy-path classification,
and the exact state in which the convergence work started.

## §1 State reconciliation record

```text
HEAD      87ae8ee (restored; sandbox had rolled back to base 984a406)
REMOTE    origin/arena/01a070b0-mql5bot = 87ae8ee (verified via ls-remote)
PYTEST COLLECTED   1103
PYTEST PASSED     1102
PYTEST FAILED        0   (one transient: optional `optuna`/`pyyaml` missing
                          after venv loss — installed and re-verified green)
SKIPPED              1   (live-MT5-only guard, by design)
RUFF        All checks passed
WORKTREE    clean; an uncommitted PARALLEL workstream (pipeline/fast_engine/
            leakage-features, ~2.5k lines, not this branch's history) was
            found on the rolled-back worktree.  PRESERVED, not discarded:
            git stash "pre-convergence" + /home/user/
            preserved_uncommitted_984a406.patch.  It belongs to sibling
            agent branches (arena/01a06c21 / 01a06cb0) and is NOT merged
            into this branch's history without its author.
```

Never force-pushed; the restore was a fast-forward from origin.

## §2 Subsystem audit

Legend — state: IMPLEMENTED / PARTIAL / NOT_IMPLEMENTED / BLOCKED_OWNER_ENVIRONMENT.
"TESTED" is stated separately from "IMPLEMENTED" everywhere (§69: not synonyms).

| Area | State | Tests | Integration | Known limitations / safety risk | Remaining work |
|---|---|---|---|---|---|
| Strategy (5 SPEC strategies + examples) | IMPLEMENTED, RESEARCH-VALIDATED | engine/scenarios/reproducibility suites | canonical engine consumes them | synthetic data only; PF≈1.03–1.05 honest fixture | real-data research is owner-provided |
| DSL | IMPLEMENTED | dsl_core/runtime/security/parity | intake→factory→runtime | single-symbol expressions; sessions present (london_breakout_filtered) | none material |
| Indicator universe | IMPLEMENTED | indicator_universe (25) | DSL schema/normalize/parse/runtime read contracts | 68 kinds; no fake "all indicators" claim | MQL5 parity for 59 new kinds BLOCKED_OWNER_ENVIRONMENT |
| Factory | IMPLEMENTED | 118+ factory tests | intake→store→lifecycle→evidence | — | campaign engine glue enrichment (§13/§14/§16) |
| Research | IMPLEMENTED | research_proof, optuna_hardening, cv_state_leakage | Campaign trial accounting feeds DSR/PBO context | deterministic engines only; fast engine labeled screening | — |
| Campaigns | PARTIAL | discovery suite | orchestrator + `discovery_campaigns` table | candidate parentage/seed/search-position not yet persisted on docs; manifest fields incomplete | §13/§14/§15/§16 enrichment |
| OOS | IMPLEMENTED | oos_registry, cv_state_leakage, research_proof | structural firewall; oos touched once | — | acceptance proof in E2E (§75/§76) |
| WFA | IMPLEMENTED | robustness/WFA suites | canonical | — | — |
| CPCV / PBO / DSR / PSR | IMPLEMENTED | WFA_CPCV_REVIEW-pinned tests | score component `cpcv_pbo_evidence` consumes PBO | — | — |
| Monte Carlo | IMPLEMENTED | robustness suite | score component `monte_carlo_stability` | — | — |
| Meta (single-asset gate) | IMPLEMENTED | meta_gate/layer_unit/matrix/failure_matrix | consumed by canonical pipeline; Meta≤Risk proven | — | — |
| Meta portfolio (multi-asset canonical) | IMPLEMENTED | meta_portfolio/multi_asset/metamorphic_multi_asset/portfolio_guarantees | shared account/cash/DD/margin/heat; regime/drift/correlation feeds | synthetic data; real basket = UNAVAILABLE (owner data) | concentration reporting surfaced for governor (§25) |
| Risk | IMPLEMENTED | risk invariants, sizer tests | Meta→Risk→sizer; EA RiskManager | — | §39 boundary proof test |
| Allocation | IMPLEMENTED | discovery governor; allocation digest (EA-side crypto verify) | governor→Meta weights; NEVER score→lots | — | — |
| Lifecycle | IMPLEMENTED | factory_lifecycle/store | store.transition is the only boundary | — | approval-record enrichment (§32) |
| Shadow / Demo | IMPLEMENTED | oversight suite | record_shadow/live_observation + alerts | — | — |
| Live Small | IMPLEMENTED | discovery ramp + fixtures | eligibility only; EA allocation honors factor | — | §79/§80 acceptance wiring |
| Kill switch | IMPLEMENTED | discovery + mql5_sources S2 + EA halt path | governor refuses; EA TripKillSwitch | reset explicit+audited | §36 authority-proof chain test |
| Circuit breaker | IMPLEMENTED | discovery + fixtures | governor freeze/keep-last-safe | — | — |
| Watchdog | IMPLEMENTED (component); harness PARTIAL | discovery rate-limit/fail-safe | channel-injected | external-process deployment NOT_IMPLEMENTED by design | §37/§38 failure-matrix test |
| MQL5 | IMPLEMENTED (source, 4933 lines) | test_mql5_sources (S1–S5 + retry/restart) | EA: RiskManager kill switch, SlGuard escalation, MagicMap FNV1a, StateStore restart, Allocation digest | compile/tester BLOCKED_OWNER_ENVIRONMENT | §46–§48 owner actions |
| MT5 bridge | IMPLEMENTED (Python collector) | telemetry bridge tests | EA Telemetry.mqh → Collector | live MT5 never faked | — |
| Telemetry | IMPLEMENTED | bridge + EA sources | — | — | — |
| UI | IMPLEMENTED (board/strategy/safety) | api_ui (12) | explicit approvals; §73 source proofs | research/campaigns page missing | §51/§52 pages |
| API | IMPLEMENTED | api_ui | FastAPI+Jinja2+HTMX (no React) | — | POST /campaigns (§52) |
| CLI | IMPLEMENTED | factory_cli | — | — | — |
| Persistence | IMPLEMENTED | store/migrations suites | Alembic-only; FK integrity pinned | — | §71/§72/§73 additions |
| Security | IMPLEMENTED | 19 security + 11 redteam + 14 discovery redteam | — | — | §65 final round gaps (below) |
| Documentation | PARTIAL | doc-consistency tests | 40+ docs | README factory-era wording; convergence audit (this file) | §69/§70 refresh |

## §3 Duplicate / legacy path classification

| Path | Classification | Rationale / action |
|---|---|---|
| `engine.py` (+ backtest/costs/sizer/symbolspec) | **CANONICAL** | the only accounting/execution-truth engine |
| `fast_engine.py` | **DIAGNOSTIC** | docstring-declared screening re-orchestration; reuses canonical math; never a validation path (test-pinned wording) |
| `meta_layer.py` | **CANONICAL** | single-asset allocation gate (Meta≤Risk) |
| `meta_portfolio.py` | **CANONICAL** | multi-asset shared-account engine |
| `meta_oos.py` | **CANONICAL** | the ONE OOS look for Meta policy, hash-frozen pre-OOS |
| `meta_replay.py` | **DIAGNOSTIC** | replay tooling; never authoritative |
| `portfolio.py` | **CANONICAL (research)** | research correlation/vol tools on results |
| `discovery/portfolio.py` | **CANONICAL (governance)** | candidate assembly for allocation; feeds governor, not execution |
| `indicator_universe/` + `indicators.py` | **CANONICAL** | universe = contracts+extends; baseline 9 parity-pinned in `indicators.py` |
| `optimizer.py` | **CANONICAL (research)** | deterministic grid/WFA + optuna harness (never sees OOS) |
| `stress.py`, `tools/*` | **DIAGNOSTIC** | labeled measurement/diagnostic tools |
| `certify.py` | **CANONICAL** | real-tick certification; no fabricated tick claims |
| old per-strategy execution paths | **NONE FOUND** | single EA entry (`Mql5Bot.mq5`) + include modules; `test_mql5_sources` pins wiring |

No DANGEROUS duplicates found: one OrderSend path, one lifecycle boundary,
one kill switch per side (Python governance + EA RiskManager), no second
accounting engine. Where a diagnostic exists it is already labeled; the
convergence work must keep it that way (§3: never silently promote a
diagnostic to validation).

## §65 gap scan (security) — items needing NEW coverage

Covered today: injection-as-data, fake/cross-version/stale evidence, oversized/
recursive/malformed specs, SQL/shell metacharacters, template/URL abuse,
interpreter sanitization, policy_override/state_forgery, NaN-poisoned
observations, breaker reset abuse, history flooding, progress replay,
campaign-policy replay, UI LIVE bypass, ramp arguing, score tampering,
candidate explosion, redundancy abuse.

Gaps to add in this mission: duplicate campaign id (DB uniqueness under
concurrency), concurrent promotion races, forged human-approval actor
(non-human actor pressing approval), SSRF-by-design proof (providers must
never fetch), restart-during-transaction safety, stale shadow result reuse.

## §66 gap scan (properties) — items needing NEW coverage

Covered today: canonicalization idempotency, future-mutation invariance
(indicators + registry-wide), determinism, campaign reproduction, restart
state, invalid-promotion-stays-invalid, decay-never-increases, kill-switch
blocks, breaker retains.

Gaps to add: display-name change ≠ identity change; OOS cannot alter prior
research records; adding an unrelated strategy does not alter prior
evidence; dataset-identity change invalidates incompatible evidence;
recovery-requires-qualification (exists) + risk-only-decreases-through-Meta
(exists in risk invariants) — pin both in one property suite.

## §84 production boundary (pre-declared)

`MT5_COMPILE`, `MT5_TESTER`, `PYTHON↔MT5 RECONCILIATION` =
**BLOCKED_OWNER_ENVIRONMENT** unless the owner runs MetaEditor/Strategy
Tester and supplies artifacts. They will NOT be converted to PASS.
