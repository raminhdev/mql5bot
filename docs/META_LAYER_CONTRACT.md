# META LAYER — CONTRACT ONLY (Phase 3 post-gate deliverable)

**This document is a contract, not an implementation.**  Phase 3's gate
passed (`docs/PHASE3_GATE.md`); the mandate for this session is to
specify the Meta Layer's interface and safeguards and NOTHING more: no
code, no strategy, no ML component is created.  Any future
implementation MUST satisfy every clause below; a clause cannot be
dropped without a documented protocol revision.

---

## 1. Purpose and non-purpose

The Meta Layer combines the outputs of independently certified
strategies into portfolio-level allocation decisions.  It is an
ALLOCATION layer only.  It is NOT:

- a strategy (it generates no entries/exits of its own);
- a risk authority (it sits strictly UNDER the Risk Engine);
- a certified entity (it inherits, never upgrades, the weakest
  certification state among its inputs).

## 2. Inputs (per strategy, per decision timestamp)

| input | meaning | source of truth |
|---|---|---|
| `gate_weight` | 0..1 base weight from the strategy's certification state and gates | certification record (`OosRegistry` entry + status model) |
| `regime_fit` | 0..1 how well the current regime matches the strategy's declared {allowed, preferred, forbidden} regimes | strategy metadata + regime classifier |
| `performance_factor` | realized, out-of-sample attribution-derived factor (0..cap) | OOS-side attribution only — NEVER in-sample or training-window performance |
| `correlation_penalty` | 0..1 multiplier penalizing overlapping exposure with already-weighted strategies | live portfolio exposure |
| `drift_factor` | 0..1 multiplier decaying weight as live behavior drifts from its certified behavior | drift monitor (documented separately when built) |

All inputs are non-negative scalars in [0, cap] with documented
sources.  An input whose source is unavailable is treated as
NEUTRAL (1.0) for multiplicative terms and reported — never guessed.

## 3. Weight computation

    weight(strategy, t) = gate_weight
                        × regime_fit
                        × performance_factor
                        × correlation_penalty
                        × drift_factor

The weight is the PRODUCT of the five factors — no learned or tuned
mixing, no hidden normalization inside the product.  Any
post-product normalization (e.g. rescaling to a gross-exposure
budget) must be a separate, documented, deterministic step and may
only REDUCE weights.

## 4. Combination modes (exactly four)

| mode | behavior |
|---|---|
| `independent` | each strategy trades its own allocation; no cross-interaction (current behavior) |
| `weighted_netting` | positions of the same symbol are combined netting-style, sized by the product weights (DEFAULT) |
| `vote` | a trade fires only when the weighted vote of eligible strategies agreeing on direction meets the configured threshold |
| `best_of_regime` | per regime, only the highest-weight eligible strategy trades |

Default mode: **`weighted_netting`**.  Mode selection is
configuration, pinned in the run manifest; it can never be chosen
per-decision by the layer itself.

## 5. Safeguards (all mandatory, non-negotiable)

1. **Hard zero.**  Any factor equal to zero produces weight zero —
   a strategy that is uncertified, regime-forbidden, drift-expired,
   or correlation-capped cannot trade through any mode.  No
   epsilon-resurrection of zero weights.
2. **Daily clamp.**  The layer's total risk contribution is clamped
   to the portfolio daily-loss budget enforced by the Risk Engine;
   the clamp applies BEFORE orders reach the Risk Engine and can
   only reduce exposure.
3. **Equal-weight fallback.**  If any factor source is unavailable
   for ALL strategies (e.g. drift monitor down), the layer falls
   back to EQUAL weights across eligible strategies and marks the
   decision record `fallback=equal_weight`.  It never falls back to
   "last known good weights".
4. **Explainability.**  Every allocation decision records all five
   factor values, the product, the mode, and any clamp/fallback
   that fired, in the decision journal (human-readable, replayable).
5. **OOS validation.**  The Meta Layer's combination policy is
   itself validated out-of-sample (purged CPCV + one-look OOS
   through the same pipeline discipline as strategies) before it
   may influence certified allocations.  Tuning combination
   hyperparameters on the certification slice is forbidden.
6. **Certification inheritance.**  The portfolio inherits the WEAKEST
   certification state among its contributing strategies.  The layer
   can never upgrade a strategy's state, resurrect a
   `NOT_ELIGIBLE`/`FAILED` strategy, or route around a blocked
   pipeline stage.

## 6. Hard boundaries (the layer can NEVER)

- bypass the Risk Engine (every order still passes the full risk
  path);
- remove, widen, or skip a stop-loss (SL manipulation is reserved
  to the audited SlGuard remediation ladder);
- increase any hard risk limit (per-trade risk %, daily loss,
  drawdown kill-switch thresholds, exposure caps) — the layer may
  only consume headroom, never expand it;
- trade while the kill-switch is latched, for any mode or vote
  outcome;
- emit orders outside the canonical engine seam.

## 7. Acceptance criteria for any future implementation

- the five factors and four modes exist as specified, with the
  product formula and `weighted_netting` default pinned by tests;
- safeguards 1–6 are each pinned by a dedicated test (including
  "zero factor ⇒ zero weight in every mode" and "fallback is
  equal-weight and journaled");
- the layer's decisions are reproducible: same manifests, factors
  and mode ⇒ byte-identical decision journal;
- out-of-sample validation of the combination policy exists BEFORE
  any allocation influence (state-isolation matrix like Phase 5's);
- the hard boundaries are enforced structurally (order flow cannot
  reach the engine except through the risk path) — tested, not
  asserted.

---

*Status: CONTRACT ONLY.  No Meta Layer code exists in this
repository after Phase 3, by mandate.*
