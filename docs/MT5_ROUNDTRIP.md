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
| 4 | **fixture / data preparation** | import `artifacts/gold/gold_fixture.csv` (Gold #1) — and `artifacts/gold_2/gold2_fixture.csv` (Gold #2, `GOLD_2_RECONSTRUCTED_NEW_PROVENANCE`, frozen — never regenerate) — as bars of custom offline symbols, preferred, so bars are byte-identical to each manifest `dataset_hash`; alternative: broker EURUSD data for the SAME window via `Mql5BotDownloadData.mq5` | the controlling dataset(s) in the terminal; dataset hash recorded and compared to the corresponding `manifest.json` before any tester run | hash mismatch → STOP, do not run; the fixture CSV is the controlling dataset; any Gold #2 divergence is classified BEFORE any Python edit |
| 5 | **baseline leg (M1-OHLC)** | `python tools/run_mt5_backtest.py run --config <job>.json` at model grade **M1-OHLC** (documented baseline params: strategy, inputs, sizing, deposit, leverage as exported, fixed spread); per leg of the regime × model ladder (`matrix` generates the jobs) | RAW HTML report archived verbatim + `.json` sidecar (command line, config, hashes); parsed by `run_mt5_backtest.py parse` — extractor only, never hand-typed numbers | non-zero exit → record the raw error; never retry silently into a "pass"; missing raw report or parse failure ⇒ the leg did NOT run |
| 6 | **Every Tick leg** | `run` with tester model grade **Every tick** (same window/params as step 5) | raw Every-tick report + sidecar, archived and parsed like step 5 | missing/skipped grade ⇒ ladder incomplete ⇒ NOT VERIFIED |
| 7 | **Every-Tick-real-ticks leg** | `run` with model grade **Every tick based on real ticks** (broker tick data required; same window/params) | raw real-tick report + sidecar, archived and parsed like step 5 | no broker tick data for the window ⇒ leg UNAVAILABLE ⇒ NOT VERIFIED with the recorded reason (not FAILED) |
| 8 | **Python↔MT5 comparison** | `certify.run_certification(..., python_data=...)` + the reconciliation harness | (a) Python TRUTH M1-OHLC cross-check leg + slippage-surcharge tiers + OBSERVED MT5-vs-Python degradation per regime; (b) field-by-field comparison of the parsed deal list against `artifacts/gold/expected_execution.json` + `reconciliation.json` (Gold #1) and against `artifacts/gold_2/expected_execution.json` + `artifacts/gold_2/reconciliation.json` (Gold #2 — every `PENDING_OWNER` field must be filled from the owner's run with real `MT5_` evidence, never copied from the Python values) — every field MATCH / DIVERGENT + magnitude + classification; the classification vocabulary is at minimum SIGNAL_MISMATCH / INDICATOR_MISMATCH / WARMUP / SESSION_MISMATCH / SIZING_MISMATCH / ROUNDING / META_VETO_MISMATCH / RISK_VETO_MISMATCH / EXECUTION_MISMATCH / DATA_MISMATCH / TIMESTAMP_MISMATCH / STATE_MISMATCH / UNRESOLVED (each DIVERGENCE maps onto the existing ROUNDING / WARMUP / SOURCE_SEMANTICS / TIMEFRAME_SEMANTICS / IMPLEMENTATION_BUG / UNRESOLVED classes), explicit NOT_APPLICABLE where a field does not apply — never silent omission, never "close enough"; (c) **sub-check 8a Kill-Switch seam proof**: latch the kill switch (StateStore file or drawdown trip), feed the fixture — journal shows ZERO new orders while `AllowsNewTrades()==false`, ENTRY line absent; (d) **sub-check 8b restart proof**: restart the EA mid-fixture — no duplicate exposure, state reload line, unchanged magic; (e) **sub-check 8c execution-path proofs** (owner, on demo): stateful retry after a retryable retcode (attempt cap + backoff visible in journal), lost-response adoption after restart (position adopted, not duplicated), SL verify→modify→re-verify (SlGuard), and kill-switch latch before entry (Kill-Switch proof is required BEFORE the first live order — no trade may precede it); (f) **sub-check 8d account-type legs**: run the gold leg(s) once on a NETTING account and once on a HEDGING account and record both journals (netting flips vs hedging independent positions) | divergence is a FINDING, reported AS OBSERVED (never normalized away); the 30–50% degradation band is INFORMATIONAL ONLY and never gates; 8a/8b/8c/8d not run ⇒ runtime safety proofs stay PENDING_OWNER |
| 9 | **immutable archive / manifest** | bind the certification to the pipeline manifest: `CertifyConfig.manifest_id` = the S5-certified manifest id; commit `mt5_report.json`, `mt5_journal.txt`, ALL raw reports (steps 5–7), logs, the compile log and the registry entry (identity + status model), each with its SHA-256 and timestamp | one immutable certification record (input → output → verdict → status model); append-only, never overwritten by a rerun | an unbound report is diagnostics, not certification; a rerun is a NEW record |
| 10 | **certification-state assignment** | `report["status_model"]` (Blocker 7): exactly one of the five states below | the ONLY place a strategy may be called verified; `VERIFIED` only when every required leg RAN and passed, set by the terminal owner | "the tool executed successfully" is steps 1–2 software truth and NEVER upgrades a state by itself |

Any step that cannot run ⇒ that gate stays
`BLOCKED_OWNER_ENVIRONMENT`. Do not simulate, do not sample, do not
extrapolate.

## Certification states (exactly five)

| state | meaning | who may set it |
|---|---|---|
| `SOFTWARE_PASS` | software-level gates only: compile 0/0, sandbox suite green, pipeline certification path complete — no terminal claim implied | sandbox / CI |
| `EMPIRICAL_VALIDATION_PENDING` | S1–S5 passed on the research stack; the MT5 ladder (steps 3–8) has not run | pipeline |
| `VERIFIED` | steps 1–9 executed on a real terminal, every required leg ran ok, 100-trade minimum, spread floor (when configured), zero reasons in `verdict_for` | terminal owner only |
| `FAILED` | a required leg RAN and failed its gate (or a material divergence was confirmed) | terminal owner only |
| `NOT_ELIGIBLE` | the strategy never reached S5 certification (zero survivors / blocked pipeline) | pipeline |

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
