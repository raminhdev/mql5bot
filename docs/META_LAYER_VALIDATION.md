# META LAYER — VALIDATION, RED TEAM, ACTIVATION GATE
(Mandate Phases 27-32.  Measured output below was produced by
`tools/meta_validation.py` on this sandbox; everything is reproducible
with that command.  **No profitable / production-ready / verified
claim is made or may be inferred.**)

---

## 1. Measured comparison — META vs EQUAL_WEIGHT

Method: identical strategies, symbols, time periods, cost model, risk
limits and constraints; ONLY the weighting policy differs (contract
v1.1.0).  Development folds use train-side statistics only; the OOS
window is touched once with the frozen config.

(frozen comparison wall time: 1.1s)

## OOS portfolio metrics (45-day OOS window, 4 strategies)

| metric | META | EQUAL_WEIGHT |
|---|---:|---:|
| cagr | -0.0205 | -0.0227 |
| sharpe | -0.6795 | -0.7310 |
| sortino | -0.8794 | -0.9512 |
| calmar | -0.2140 | -0.2167 |
| max_dd | -0.0957 | -0.1046 |
| recovery | -0.8860 | -0.8939 |
| cvar_5 | -0.0048 | -0.0050 |
| expectancy_per_bar | -0.0001 | -0.0001 |
| turnover | 0.0000 | 0.0000 |
| gross_exposure | 1.0000 | 1.0000 |
| concentration_hhi | 0.2602 | 0.2500 |
| n_trades | 121.0000 | 121.0000 |

## Time-period breakdown (development folds, train-side stats only)

| fold | test bars | meta sharpe | equal sharpe | meta max_dd | equal max_dd |
|---:|---:|---:|---:|---:|---:|
| 1 | 1200 | -0.033 | -0.084 | -0.095 | -0.106 |
| 2 | 1200 | -0.216 | -0.219 | -0.105 | -0.110 |

## Per-strategy OOS evidence (the factors see exactly this)

| strategy | OOS trades | expectancy/trade | OOS net |
|---|---:|---:|---:|
| donchian_20 | 35 | -0.42483 | -1486.91 |
| donchian_55 | 35 | -0.42483 | -1486.91 |
| ema_fast | 24 | -0.09954 | -238.90 |
| ema_slow | 27 | -0.17816 | -481.03 |

## Weights (frozen from development-side statistics)

| strategy | META weight | EQUAL weight |
|---|---:|---:|
| donchian_20 | 0.2077 | 0.2500 |
| donchian_55 | 0.2077 | 0.2500 |
| ema_fast | 0.2533 | 0.2500 |
| ema_slow | 0.3314 | 0.2500 |

## Dimensions NOT measurable in this research stack

- **Regime breakdown**: the Python research stack has no regime
  classifier (regime metadata is static per strategy); a regime
  table would be fabricated.  Regime behavior is pinned by the
  regime matrix tests instead.
- **Symbol breakdown**: synthetic single-symbol data; the
  weighting math is symbol-agnostic (book groups by symbol).
- **Profit factor / expectancy at portfolio level**: portfolio
  trades do not exist under fixed weights; per-strategy OOS
  expectancy and trade counts are reported above.

## Performance profile (10 strategies, 500-bar window, shared sandbox)

| step | ms (mean of 20) |
|---|---:|
| correlation matrix (10x10, 500 bars) | 44.96 |
| full decision | 60.66 |
| journal serialization | 0.37 |
| journal canonical json | 0.27 |

## Activation decision input (SYNTHETIC data — not activation-grade)

- meta OOS sharpe > equal-weight OOS sharpe on this synthetic run: True
- decision per the empirical gate: SYNTHETIC comparison CANNOT
  activate anything.  The Meta Layer ships DISABLED by default;
  the maximum honest state today is SHADOW_ONLY, pending real
  data validation, MT5 truth validation, shadow results and
  demo evidence.


## 2. Reading of the measured result (honest)

- On this SYNTHETIC run the four contributing strategies all LOSE out
  of sample; META tilts weight toward the least-bad strategy and lands
  marginally better than equal weight on every risk-adjusted metric —
  a difference far inside run-to-run noise on 45 days of random-walk
  data.
- **This is NOT evidence that Meta Layer improves anything.**  The
  bounded factors (shrunk + winsorized performance, correlation
  penalty, hard-zero eligibility) deliberately keep META close to
  EQUAL_WEIGHT unless development-side evidence is strong.  That is
  the anti-overfit design goal (Phase 16), not a weakness.
- Per Phase 28: no robust OOS outperformance after costs is claimed;
  the comparison harness and discipline now exist for a REAL-data
  decision.

## 3. RED TEAM (Phase 31) — "how can Meta lose while appearing correct?"

| # | attack | outcome |
|---|---|---|
| 1 | order dependence | FIXED (ML-1): simultaneous snapshot; permutation invariance pinned over shuffles in all modes and fallbacks |
| 2 | correlation inversion over time | WAIVED with mitigation: penalty uses only positive correlation, floored at 0.1, change-limit damps swings; inversion is a data property, monitored via drift/eligibility, not silently absorbed |
| 3 | regime misclassification | FIXED fail-safe: any unknown regime (incl. TRANSITION) zeroes the strategy (REGIME_UNKNOWN); over-conservatism accepted and documented |
| 4 | stale OOS data | FIXED: source staleness = STALE_DATA ineligibility; allocation file staleness = decay after 7 days; insufficient correlation coverage = flagged, global fallback |
| 5 | sample-size bias | FIXED: k=20 shrinkage + ±2% winsorized expectancy pinned ("five lucky trades" test) |
| 6 | winner chasing | FIXED: performance factor bounded [0.1,1.0]; identical stats ⇒ identical weights (convergence-to-equal pinned) |
| 7 | weight oscillation | FIXED: max_weight_change clamp between persisted decisions (tested); hard zeros bypass it (immediate) |
| 8 | normalization artifacts | FIXED: ratio preservation + cap hard bounds + bounded redistribution into uncapped eligible only (metamorphic C/D/F) |
| 9 | zero resurrection | FIXED: mask-before-normalize; no epsilon path; all-zero ⇒ SAFE HOLD (B/K tests) |
| 10 | fallback abuse | FIXED: fallback ONLY on global source failure, named source journaled, hard zeros still zero (test_k); never last-known-good (Phase 30 SAFE HOLD) |
| 11 | stale allocation file | FIXED: digest-verified file; reader flags stale; EA decays to base gate after 7 days; malformed refused both sides |
| 12 | version mismatch | FIXED: state carries decision_version + config_hash; a layer refuses state from a different config; journal carries the full version block |
| 13 | restart reset | FIXED: restart-equivalence byte-identical test; persisted state = weights/zero-reasons only |
| 14 | hidden lookahead | FIXED: correlation window cut at as_of (tested); fold stats are train-side only; OOS touched once |
| 15 | allocation/risk mismatch | FIXED structurally: the EA seam scales lots AFTER RiskManager.GetLots and can only reduce (structural pin) |
| 16 | netting attribution errors | FIXED: book contributions sum to the net score exactly (1e-12 test); attribution lives in the journal, never in position comments |
| 17 | live/shadow divergence | COVERED: shadow divergence metrics implemented; SHADOW may_influence_sizing is structurally False |

**No CRITICAL/HIGH finding remains open.**  The single waiver (#2) is
recorded above with its mitigations.

## 4. Activation decision (Phase 28)

`DISABLED` (default) — maximum honest state today: **SHADOW_ONLY**.
The synthetic comparison cannot satisfy the empirical gate; real-data
validation, MT5 truth validation, shadow results and demo evidence
are all still pending.  Transitions remain explicit and audited.

## 5. Phase 32 EXIT GATE — Meta Layer SOFTWARE_PASS (30/30)

| # | criterion | evidence |
|---|---|---|
| 1 | contract audited + versioned | META_LAYER_CONTRACT.md v1.1.0; DECISIONS ML-1..ML-8 |
| 2 | correlation permutation-invariant | metamorphic A (+ corr monotonicity E) |
| 3 | eligibility deterministic | reason table test; fixed check order |
| 4 | hard-zero semantics | unit + metamorphic B/K (never resurrected) |
| 5 | missing-data explicit | classified table + tests (J, adv 06-08) |
| 6 | five factors implemented | gate/regime/performance/correlation/drift with sources+versions+status |
| 7 | product formula pinned | raw == Πfactors exact test |
| 8 | normalization deterministic | share→cap→redistribute→budget; ratio + bounds tests |
| 9 | equal-weight baseline | MetaPolicy.EQUAL_WEIGHT; same machinery, only weights differ (pinned) |
| 10 | four modes work | independent/weighted_netting/vote/best_of_regime tests incl. ties/abstention |
| 11 | attribution works | signed book sums to net exactly; per-strategy contributions |
| 12 | portfolio constraints work | budget/cap/max_positions reduce-only tests |
| 13 | Risk Engine final authority | no order API; EA seam after GetLots reduce-only (structural) |
| 14 | risk-invariant tests pass | tests/test_meta_risk_invariants.py (12 mapped items) |
| 15 | metamorphic tests pass | tests/test_meta_metamorphic.py A-K |
| 16 | regime tests pass | 7-regime matrix |
| 17 | drift tests pass | NO/MILD/SEVERE/MISSING matrix + clamp |
| 18 | adversarial tests pass | 22 scenarios (test_meta_matrix.py) |
| 19 | journal deterministic | byte-identical journals; strategy_id ordering |
| 20 | restart tested | restart equivalence + state-content whitelist |
| 21 | shadow mode works | divergence metrics; no sizing influence |
| 22 | OOS validation exists | meta_oos fold diagnostics + ONE-LOOK registry |
| 23 | meta-vs-equal comparison exists | this document §1 (measured) |
| 24 | no OOS tuning after exposure | second look refused EVEN with changed config (test) |
| 25 | file contract respected | SPEC allocation.json: schema/digest/atomic/stale/missing; EA consumer |
| 26 | python tests pass | full suite green (see final report PYTEST) |
| 27 | ruff passes | ruff clean at gate commit |
| 28 | no uncontrolled live activation | explicit ladder; DISABLED default; illegal transitions raise |
| 29 | failure fails safe | safe_decision → SAFE HOLD; malformed file → refused |
| 30 | no live ML | no learning anywhere; no optuna import (scanned); pure deterministic math |

SOFTWARE_PASS ≠ profitability, production-readiness, or MT5
verification.  The Meta Layer inherits the WEAKEST certification state
of its contributing strategies and can never upgrade one.
