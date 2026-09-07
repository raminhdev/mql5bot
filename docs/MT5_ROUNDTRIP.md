# AEGIS — MT5 TRUTH ROUND-TRIP (owner workflow, Phase 3 hardening)

Blocker 8 deliverable. The exact TEN-step sequence a TERMINAL OWNER
(a Windows machine with a real MetaTrader 5 installation) runs to move
a strategy from `EMPIRICAL_VALIDATION_PENDING` toward `VERIFIED`.
**Nothing in this loop may be fabricated**: every step consumes the
previous step's real artifact, and the sandbox (no terminal) can never
produce any of steps 3–8.  Until this loop has actually been executed,
the MT5 status is exactly `NOT VERIFIED` — which is not a failure and
not a pass.

## CANONICAL PROTOCOL — single source of truth

This document is the ONE canonical owner protocol. Every other document
or tool that lists owner steps MUST either reproduce these exact ten
steps with these exact numbers, or label itself explicitly as a
**SHORTCUT** and map its items onto the step numbers below. Where older
documents used a different numbering (e.g. the nine-step list in
`docs/AEGIS_REALITY_GATE_AUDIT.md` §owner-protocol), those lists are
SUPERSEDED shortcuts; the mapping is annotated there. If a shortened
checklist anywhere does not say which canonical step each item is, it
is non-conforming and must not be used as evidence.

Companions: `docs/CERTIFICATION.md` (ladder + gates),
`python/mql5bot/certify.py` (verdict machine),
`tools/compile.ps1` (compile gate), `tools/run_mt5_backtest.ps1`
(Windows wrapper) + `tools/run_mt5_backtest.py` (tester driver),
`tools/certify_strategy.py` (ladder CLI), `tools/benchmark_research.py`
(research-engine throughput ladder),
`tools/broker_symbol_parity.py` (SymbolSpec parity),
`python/mql5bot/mt5tester.py` (report parsing),
`python/mql5bot/status.py` (status model).

---

## The canonical owner sequence (exactly ten steps)

| # | Step | Tool / command | Artifact produced | Failure mode |
|---|------|----------------|-------------------|--------------|
| 1 | **strict compile** | `powershell -File tools/compile.ps1 -Strict` | fresh `.ex5` per target; compiler version + exit code recorded (an `.ex5` older than the compile start is NOT proof) | exit 1/2/3/4 → stop; record `SOFTWARE_FAIL`, MT5 stays NOT VERIFIED |
| 2 | **compiler-log verification** | read `logs/compile-<stamp>.log` (produced by step 1) | verbatim compiler output; 0 errors / 0 warnings counted from the LOG itself, plus SHA-256 of each fresh `.ex5` and the repo commit hash next to the log | any error/warning token → `SOFTWARE_FAIL`; never infer success from "the script ran" |
| 3 | **SymbolSpec export** | compile + run `mql5/Scripts/Mql5Bot/Mql5BotExportSymbolSpec.mq5` on the demo broker for the certification symbol/timeframe; then `python tools/broker_symbol_parity.py` | timestamped, SHA-256-hashed broker export under `data/broker_exports/` (source-bound to the export script commit); FIELD_MAP comparison with every field PENDING→RESOLVED with the exported values | any field unresolved or export older than the compile → leg BLOCKED until re-exported; never substitute "typical" broker values |
| 4 | **fixture / data preparation** | prepare EXACTLY, for each gold standard: the fixture (`artifacts/gold/gold_fixture.csv` Gold #1; `artifacts/gold_2/gold2_fixture.csv` Gold #2, `GOLD_2_RECONSTRUCTED_NEW_PROVENANCE`, frozen — never regenerate), its manifest, its config hash, the source commit hash, the dataset hash, the SymbolSpec binding from step 3, the timeframe and the testing window; import the fixtures as bars of custom offline symbols (preferred — byte-identical to each manifest `dataset_hash`); alternative: broker EURUSD data for the SAME window via `Mql5BotDownloadData.mq5` | the controlling dataset(s) in the terminal; dataset hash recorded and compared to the corresponding `manifest.json` before any tester run | hash mismatch → STOP, do not run; the fixture CSV is the controlling dataset; any Gold #2 divergence is classified BEFORE any Python edit; the dataset hash is re-checked AFTER the legs to prove no fixture mutation occurred during testing |
| 5 | **baseline leg (M1-OHLC)** | `python tools/run_mt5_backtest.py run --config <job>.json` at model grade **M1-OHLC** (documented baseline params: strategy, inputs, sizing, deposit, leverage as exported, fixed spread); per leg of the regime × model ladder (`matrix` generates the jobs) | RAW HTML report archived verbatim + `.json` sidecar (command line, config, hashes); parsed by `run_mt5_backtest.py parse` — extractor only, never hand-typed numbers | non-zero exit → record the raw error; never retry silently into a "pass"; missing raw report or parse failure ⇒ the leg did NOT run |
| 6 | **Every Tick leg** | `run` with tester model grade **Every tick** (same window/params as step 5) | raw Every-tick report + sidecar, archived and parsed like step 5 | missing/skipped grade ⇒ ladder incomplete ⇒ NOT VERIFIED |
| 7 | **Every-Tick-real-ticks leg** | `run` with model grade **Every tick based on real ticks** (broker tick data required; same window/params) | raw real-tick report + sidecar, archived and parsed like step 5, PLUS the real-tick coverage record (below) | no broker tick data for the window ⇒ leg UNAVAILABLE ⇒ NOT VERIFIED with the recorded reason (not FAILED); coverage PARTIAL/UNKNOWN ⇒ certification constrained (see the real-tick coverage rule) |
| 8 | **Python↔MT5 comparison** | `certify.run_certification(..., python_data=...)` + the reconciliation harness | (a) Python TRUTH M1-OHLC cross-check leg + slippage-surcharge tiers + OBSERVED MT5-vs-Python degradation per regime; (b) field-by-field comparison of the parsed deal list against `artifacts/gold/expected_execution.json` + `reconciliation.json` (Gold #1) and against `artifacts/gold_2/expected_execution.json` + `artifacts/gold_2/reconciliation.json` (Gold #2 — every `PENDING_OWNER` field must be filled from the owner's run with real `MT5_` evidence, never copied from the Python values) — every field MATCH / DIVERGENT + magnitude + classification; the classification vocabulary is EXACTLY this closed set (one class per divergence): SIGNAL_MISMATCH / INDICATOR_MISMATCH / WARMUP_MISMATCH / SESSION_MISMATCH / SIZING_MISMATCH / ROUNDING_MISMATCH / META_MISMATCH / RISK_MISMATCH / EXECUTION_MISMATCH / DATA_MISMATCH / TIMESTAMP_MISMATCH / STATE_MISMATCH / BROKER_SPEC_MISMATCH / UNKNOWN (these refine the older ROUNDING / WARMUP / SOURCE_SEMANTICS / TIMEFRAME_SEMANTICS / IMPLEMENTATION_BUG / UNRESOLVED classes, which remain as the coarse grouping), explicit NOT_APPLICABLE where a field does not apply — never silent omission, never "close enough"; (c) **sub-check 8a Kill-Switch seam proof**: latch the kill switch (StateStore file or drawdown trip), feed the fixture — journal shows ZERO new orders while `AllowsNewTrades()==false`, ENTRY line absent; (d) **sub-check 8b restart proof**: restart the EA mid-fixture — no duplicate exposure, state reload line, unchanged magic; (e) **sub-check 8c execution-path proofs** (owner, on demo): stateful retry after a retryable retcode (attempt cap + backoff visible in journal), lost-response adoption after restart (position adopted, not duplicated), SL verify→modify→re-verify (SlGuard), and kill-switch latch before entry (Kill-Switch proof is required BEFORE the first live order — no trade may precede it); (f) **sub-check 8d account-type legs**: run the gold leg(s) once on a NETTING account and once on a HEDGING account and record both journals (netting flips vs hedging independent positions) | divergence is a FINDING, reported AS OBSERVED (never normalized away); the 30–50% degradation band is INFORMATIONAL ONLY and never gates; 8a/8b/8c/8d not run ⇒ runtime safety proofs stay PENDING_OWNER |
| 9 | **immutable archive / manifest** | bind the certification to the pipeline manifest: `CertifyConfig.manifest_id` = the S5-certified manifest id; archive ALL of: the compile log, the `.ex5` SHA-256 hashes, the broker SymbolSpec export, every raw report and parsed report (steps 5–7), both gold manifests + expected executions + the reconciliation record(s), the step-7 real-tick coverage record, owner environment metadata (terminal build, broker name/account type), the tester model used, and the source/config/data hashes — each with its SHA-256 and timestamp — into ONE immutable certification manifest | one immutable certification record (input → output → verdict → status model); append-only, never overwritten by a rerun | an unbound report is diagnostics, not certification; a rerun is a NEW record; any missing or mismatched artifact ⇒ the attempt is NOT_VERIFIED, never repaired after the fact |
| 10 | **certification-state assignment** | `report["status_model"]` (Blocker 7): exactly one of the five states below | the ONLY place a strategy may be called verified; `VERIFIED` only when every required leg RAN and passed, set by the terminal owner | "the tool executed successfully" is steps 1–2 software truth and NEVER upgrades a state by itself |

Any step that cannot run ⇒ that gate stays
`BLOCKED_OWNER_ENVIRONMENT`. Do not simulate, do not sample, do not
extrapolate.

### Real-tick coverage rule (step 7, binding — official MT5 semantics)

Official MetaTrader 5 semantics ("Real and Generated Ticks",
`metatrader5.com/en/terminal/help/algotrading/tick_generation`):
"If a symbol history has a minute bar with no tick data for it, the
tester generates ticks in the Every tick mode. This allows testing the
EA on a certain period in case a broker's tick data is insufficient."
Minute bars are considered more reliable than ticks. **Selecting the
real-tick modelling mode therefore NEVER implies every tick was real**
— the terminal silently falls back to generated ticks for gaps.

Every step-7 artifact must record, with the closed vocabulary of
`mql5bot.mt5tester.REAL_TICK_COVERAGES`:

| record | content |
|---|---|
| `requested_model` | the model grade the leg was started with |
| `actual_model` | the Model line parsed from the report (`settings.model`) + tester journal evidence |
| `real_tick_coverage` | `REAL_TICK_COVERAGE_FULL` / `REAL_TICK_COVERAGE_PARTIAL` / `REAL_TICK_COVERAGE_UNKNOWN` |
| `fallback_coverage` | which sub-intervals (if any) fell back to generated ticks, from the tester journal |
| `broker_data_availability` | what tick history the broker actually held for the window |
| `test_interval` | the exact leg window |

Coverage classification: FULL only when the journal/report shows real
ticks for the entire window; **PARTIAL whenever any fallback occurred**
(record `REAL_TICK_COVERAGE_PARTIAL`); UNKNOWN when the evidence cannot
settle it. A PARTIAL/UNKNOWN step 7 keeps the certification
appropriately constrained: the leg's numbers are recorded AS OBSERVED,
but `VERIFIED` must cite the coverage class, and a `VERIFIED` claim on
PARTIAL/UNKNOWN coverage is non-conforming until the gap is closed
(longer broker history or a narrower certified window).

### Every Tick ≠ real ticks (step 6 vs step 7, binding)

The two tick grades are intentionally DIFFERENT modelling paths:
Every Tick generates synthetic ticks from M1 bars (fixed per-bar
spread); the real-tick grade replays broker ticks (spread may vary
inside a bar). Their results are compared to determine whether the
strategy is execution-model sensitive, whether any divergence comes
from data modelling, and whether it crosses a safety or strategy
boundary — **never to force identical trade counts**. Differences are
reported explicitly as findings.

### Mismatch triage procedure (step 8, binding)

If a real MT5 mismatch appears: STOP normal progress.  Then:

1. **Reproducer** — freeze the exact data + configuration that shows
   the divergence (fixture hash, config hash, leg id, report hash).
2. **Classification** — exactly one class from the closed set above
   (`UNKNOWN` is allowed and honest; two classes are not).
3. **Locate** — the first divergent bar/tick, the first divergent
   state, and whether any financial DECISION changed (a cosmetic
   difference that cannot change an order is recorded, not patched).
4. **Attribute** — whether the fix belongs in Python, MQL5, the
   contract, the data adapter, or the broker mapping.  Never patch
   both sides simultaneously before the causal source is identified;
   the side whose contract is canonical (EA semantics for execution,
   broker spec for symbol fields) decides the direction.

### SymbolSpec divergence rule (step 3, binding)

The synthetic parity spec is only a deterministic contract fixture.
The owner-side SymbolSpec comes from the actual terminal/broker
(`Mql5BotExportSymbolSpec.mq5`).  If actual differs from expected:
DO NOT silently rewrite the contract — classify the impact first:
`SIZING` (tick value / contract size / currencies), `STOP_CONSTRAINT`
(stops level / freeze level), `VOLUME_GRID` (volume min/max/step/
limit), `MARGIN`, or `EXECUTION` (trade mode / filling / expiration).
Each class names what must be re-verified before the leg counts.

## Certification states (exactly five)

| state | meaning | who may set it |
|---|---|---|
| `SOFTWARE_PASS` | software-level gates only: compile 0/0, sandbox suite green, pipeline certification path complete — no terminal claim implied | sandbox / CI |
| `EMPIRICAL_VALIDATION_PENDING` | S1–S5 passed on the research stack; the MT5 ladder (steps 3–8) has not run | pipeline |
| `VERIFIED` | steps 1–9 executed on a real terminal, every required leg ran ok, 100-trade minimum, spread floor (when configured), zero reasons in `verdict_for` | terminal owner only |
| `FAILED` | a required leg RAN and failed its gate (or a material divergence was confirmed) | terminal owner only |
| `NOT_ELIGIBLE` | the strategy never reached S5 certification (zero survivors / blocked pipeline) | pipeline |

### Mission-vocabulary mapping (binding)

Different documents use two vocabularies for the same machine.  The
five-state table above is canonical; the mapping is:

| mission vocabulary | canonical machine |
|---|---|
| `SOFTWARE_PASS` | `SOFTWARE_PASS` (software facts only, never a strategy claim) |
| `RESEARCH_VALIDATED` | `EMPIRICAL_VALIDATION_PENDING` (S1–S5 research gates passed; MT5 not run) |
| `MT5_VALIDATED` | the MT5 dimension = `VERIFIED` (every required leg RAN and ok) — reachable only from steps 3–9 on a real terminal |
| `VERIFIED` | `VERIFIED` (the full ladder passed; terminal owner only) |
| `NOT_VERIFIED` | the MT5 dimension = `NOT VERIFIED` |
| `BLOCKED_OWNER_ENVIRONMENT` | legs that cannot run in the current environment |

Hard rule: **Python-only evidence — green tests, green source audits,
green parsers, existing artifacts — can NEVER produce `MT5_VALIDATED`
or `VERIFIED`.** Each leg needs its own actual terminal evidence
(`python/mql5bot/status.py` enforces this; pinned by
`tests/test_status_model.py` and `tests/test_certify.py`).

## Degradation reporting rule (binding, Phase 3 gate)

Real-tick degradation is **reported AS OBSERVED** per regime (the
`degradation_report` in `certify.py`: observed percentage + an
`inside_band` flag for the 30–50% reference band).  The band is
**informational only** and NEVER a pass/fail gate: a strategy is not
certified or rejected because its degradation falls inside or outside
an arbitrary range.  What gates is a *required leg failing to run*, the
100-trade minimum, and the spread floor when configured.  An anomalous
observed degradation is a FINDING to investigate and record, not an
auto-fail.

## Owner execution package (single self-contained bundle, mission §16)

### MACHINE

Windows PC · MetaTrader 5 (broker build) · MetaEditor 5.

### REQUIRED INPUTS (what the owner must have before step 1)

* the exact repository commit being certified (this branch, pinned hash);
* Gold #1 fixture `artifacts/gold/gold_fixture.csv` + `artifacts/gold/manifest.json`;
* Gold #2 fixture `artifacts/gold_2/gold2_fixture.csv` + `artifacts/gold_2/manifest.json`
  (frozen — `GOLD_2_RECONSTRUCTED_NEW_PROVENANCE`);
* the gold configs + config hashes (inside each manifest);
* the tools named by the ten steps (compile.ps1, run_mt5_backtest.py,
  broker_symbol_parity.py, certify_strategy.py).

### REQUIRED OUTPUTS (one certification attempt produces ALL of these)

1. compile log (verbatim) — `logs/compile-<stamp>.log`
2. fresh `.ex5` SHA-256 hashes (per target)
3. broker SymbolSpec export — `data/broker_exports/<symbol>-<stamp>.json`
4. M1-OHLC reports (Gold #1 + Gold #2) — raw `.htm` + `.json` sidecar
5. Every-Tick reports (Gold #1 + Gold #2) — raw `.htm` + `.json` sidecar
6. real-tick reports (Gold #1 + Gold #2) — raw `.htm` + `.json` sidecar +
   the real-tick coverage record
7. parsed reports (via `run_mt5_backtest.py parse` — never hand-typed)
8. reconciliation record(s) — every field MATCH / DIVERGENT /
   NOT_APPLICABLE / PENDING_OWNER
9. final archive manifest (step 9) with every SHA-256 + timestamp

### FAILURE RULE

Any missing artifact, any hash mismatch, any unparsed report, any
skipped leg ⇒ the attempt is `NOT_VERIFIED`. There is no partial
VERIFIED and no post-hoc repair; a rerun is a NEW record.

## Checklist (per certification attempt — SHORTCUT view of the ten steps)

Each item names the canonical step(s) it evidences.

- [ ] Windows terminal host with the broker data folder identified
- [ ] **step 1**: `tools/compile.ps1 -Strict` exit 0
- [ ] **step 2**: compile log archived; 0/0 counted from the log; `.ex5`
      SHA-256 recorded; repo commit hash recorded next to the log
- [ ] **step 3**: SymbolSpec export timestamped + hashed; every FIELD_MAP
      entry PENDING→RESOLVED
- [ ] **step 4**: fixture imported; dataset hash matches `manifest.json`
- [ ] **steps 5–7**: regime × model ladder jobs generated (`matrix`), one
      job per leg, one per model grade (M1-OHLC / Every tick / real ticks)
- [ ] every leg's RAW HTML report archived (never overwritten by a rerun)
- [ ] every leg parsed by `run_mt5_backtest.py parse` (no manual numbers)
- [ ] **step 8**: Python TRUTH cross-check leg ran on the same
      window/params; reconciliation fields all MATCH/DIVERGENT/
      NOT_APPLICABLE (no silent omission)
- [ ] **step 8a**: kill-switch seam proof ran — zero new orders while
      latched
- [ ] **step 8b**: restart proof ran — no duplicate exposure, magic
      unchanged
- [ ] **step 8c**: retry / lost-response adoption / SL verify-modify-reverify
      / kill-switch-before-entry proofs recorded (demo)
- [ ] **step 8d**: netting-account AND hedging-account legs recorded
- [ ] step 7 real-tick coverage recorded with the closed vocabulary
      (FULL / PARTIAL / UNKNOWN) + requested-vs-actual model + fallback
      intervals from the journal
- [ ] step 4 dataset hash re-checked AFTER the legs (no fixture mutation
      during testing)
- [ ] any SymbolSpec difference classified (SIZING / STOP_CONSTRAINT /
      VOLUME_GRID / MARGIN / EXECUTION) — never silently rewritten
- [ ] Gold #2 owner leg (when certifying that strategy): all
      `PENDING_OWNER` fields filled with real MT5 evidence, or the
      field stays `PENDING_OWNER`
- [ ] 100-trade minimum met per required leg
- [ ] spread floor met (or explicitly not configured — then it cannot gate)
- [ ] degradation REPORTED AS OBSERVED per regime (band informational only
      — never a gate; findings recorded)
- [ ] **step 9**: `certify.run_certification` verdict recorded;
      `manifest_id` binding recorded (S5 certification identity); all
      artifacts hashed + timestamped, append-only
- [ ] **step 10**: `status_model` section of the report == expected
      statuses
- [ ] artifacts committed/archived: logs, reports, JSON, registry file

## Owner runtime safety procedures (step 8a–8d detail — ALL OWNER EVIDENCE)

These are runtime proofs on a demo terminal. They can NEVER be produced
or simulated in the sandbox; without them the corresponding safety
claims stay PENDING_OWNER. Each row: procedure → expected evidence.

| # | proof | procedure (demo) | expected evidence |
|---|---|---|---|
| 1 | **Kill Switch** (8a) | latch the kill switch (StateStore file or drawdown trip) BEFORE a known entry bar in the fixture, then feed the fixture | ZERO new orders while latched; ENTRY line absent from the journal; `AllowsNewTrades()==false` visible |
| 2 | **Risk veto** | trigger a documented risk veto (e.g. daily-loss halt on a prepared fixture/account state) | the entry is REJECTED by the Risk Engine; journal shows the veto reason; no position opened |
| 3 | **Meta reduce-only** | run with a reduced allocation weight (0 < w < 1) under Meta activation | every position size ≤ the Risk-approved size; allocation journal shows the applied weight; size never exceeds Risk |
| 4 | **Lost execution response** | create an ambiguous state (e.g. cut the connection around an order send, or simulate a retryable retcode) | state recovery happens BEFORE the retry; no duplicated exposure; journal shows adoption/retry with attempt cap + backoff |
| 5 | **Missing SL** | remove/lose the SL on an open position (demo manipulation) | SlGuard verify → modify → re-verify sequence in the journal; position never left without a protective stop after recovery |
| 6 | **Restart matrix** | restart the EA four times: during (a) pending execution, (b) active retry, (c) open position, (d) allocation polling | safe reconstruction each time: state reload line, no duplicate exposure, unchanged magic, orphan pendings cancelled or adopted |
| 7 | **Netting** | run the gold leg on a NETTING account with opposite signals | weighted aggregation into one net position per symbol; journal shows net flips, not independent positions |
| 8 | **Hedging** | run the same leg on a HEDGING account | isolated attribution: independent positions with their own magic/tickets; no cross-contamination |

## Anti-fabrication rules (enforced by the code, restated here)

1. The sandbox cannot run steps 3–8; `mt5_stage` returns `status:
   "skipped"` with the reason — never a synthetic result.
2. A compile success (steps 1–2) is a SOFTWARE fact: it never appears as
   a strategy status.
3. Parse outputs come only from `mt5tester.py`'s extractor over the raw
   report; no metric is ever hand-entered.
4. `verdict_for` lists EVERY failing reason; partial passes are
   `NOT VERIFIED`, never "verified with caveats".
5. `status.py` makes `VERIFIED` unreachable without a real terminal
   ladder pass (tested: `tests/test_status_model.py`,
   `tests/test_certify.py`).
6. Stale artifacts are rejected, not reused: an `.ex5` older than the
   compile start, a report whose config/symbol/commit/fixture hash does
   not match the current attempt, or a missing sidecar/hash invalidates
   the leg (steps 1, 3, 4, 5–7, 9).
7. Empty, truncated or non-report files fail closed: the report gate
   (`mt5tester.report_gate`) refuses a parsed report without tables or
   label/value rows, so an empty or edited report can never become an
   `ok` leg (pinned by `tests/test_certify_redteam.py`).
8. A strategy outside the five built-in engines is `NOT_EXECUTABLE`:
   certification refuses its tester legs before any runner is invoked —
   no approximation onto a built-in (`certify.mql5_execution_status`,
   pinned by `tests/test_certify_redteam.py`).

---

## Owner SHADOW test for the Meta Layer (empirical-gate Phase 24)

Run AFTER the canonical steps 1–2 (compile gate) with the NEW
`Allocation.mqh` + the sizing seam in `Mql5Bot.mq5`.  Record every
step's evidence (log/journal file); a step without evidence did not
happen.

| # | step | pass evidence |
|---|------|---------------|
| 1 | `tools/compile.ps1 -Strict` with the Meta Layer sources | 0 errors / 0 warnings log + fresh `.ex5` SHA-256 |
| 2 | deploy EA to the demo/test terminal | install log |
| 3 | set Meta inputs: `InpAllocationFile=in/allocation.json`, `InpBaseGateWeight=1.0`; activation stays DISABLED in Python | config screenshot/log line |
| 4 | provide a valid `allocation.json` (from `mql5bot.meta_layer.write_allocation_file`) | file digest recorded |
| 5 | attach EA to a demo symbol | EA log initialised |
| 6 | confirm the Risk Engine stays active: daily-loss %, drawdown %, spread floor still configured (`g_risk.Init` inputs unchanged) | inputs journal |
| 7 | confirm Meta does NOT alter live sizing in DISABLED/SHADOW: allocation weights are computed + journaled; trades size exactly as the Risk Engine approved (compare `lots` before/after `ScaleLots` in the log) | trade log equality |
| 8 | inspect the decision journal (Python, canonical) — one entry per decision, strategy_id ascending | journal file hash |
| 9 | restart the EA (and the Python layer) | state file reload log; weights continuous; activation preserved |
| 10 | corrupt / stale the allocation file (mutate a weight; backdate computed_at > 7 days) | EA logs "allocation refused" / decays to base gate; NO order-size change beyond the documented fallback |
| 11 | kill-switch test on demo: latch the kill switch | zero new trades in every mode; allocation journal shows KILL_SWITCH eligibility |

A SHADOW run passes when 1–11 all hold.  Any failure = the Meta Layer
stays DISABLED until fixed and re-tested.  These steps can NEVER be
executed or evidenced in this sandbox.
