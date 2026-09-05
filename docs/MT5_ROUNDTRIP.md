# AEGIS — MT5 TRUTH ROUND-TRIP (owner workflow, Phase 3 hardening)

Blocker 8 deliverable. The exact TEN-step sequence a TERMINAL OWNER
(a Windows machine with a real MetaTrader 5 installation) runs to move
a strategy from `EMPIRICAL_VALIDATION_PENDING` toward `VERIFIED`.
**Nothing in this loop may be fabricated**: every step consumes the
previous step's real artifact, and the sandbox (no terminal) can never
produce any of steps 2–8.  Until this loop has actually been executed,
the MT5 status is exactly `NOT VERIFIED` — which is not a failure and
not a pass.

Companions: `docs/CERTIFICATION.md` (ladder + gates),
`python/mql5bot/certify.py` (verdict machine),
`tools/compile.ps1` (compile gate), `tools/run_mt5_backtest.ps1`
(Windows wrapper) + `tools/run_mt5_backtest.py` (tester driver),
`tools/certify_strategy.py` (ladder CLI), `tools/benchmark_research.py`
(research-engine throughput ladder), `python/mql5bot/mt5tester.py` (report parsing),
`python/mql5bot/status.py` (status model).

---

## The required Windows sequence (exactly ten steps)

| # | Step | Tool / command | Artifact produced | Failure mode |
|---|------|----------------|-------------------|--------------|
| 1 | **compile** | `tools/compile.ps1 -Strict` | fresh `.ex5` per target (an `.ex5` older than the compile start is NOT proof) | exit 1/2/3/4 → stop; record `SOFTWARE_FAIL`, MT5 stays NOT VERIFIED |
| 2 | **compile log** | read `logs/compile-<stamp>.log` (produced by step 1) | verbatim compiler output; 0 errors / 0 warnings counted from the LOG, plus SHA-256 of each fresh `.ex5` | any error/warning token → `SOFTWARE_FAIL`; never infer success from "the script ran" |
| 3 | **baseline tester** | `python tools/run_mt5_backtest.py run --config <job>.json` at the documented baseline model grade (M1-OHLC), per leg of the regime × model ladder (`matrix` subcommand generates the jobs) | tester artifacts for the baseline grade | non-zero exit → record the raw error; never retry silently into a "pass" |
| 4 | **raw report** | `run` already preserves the raw report; archive it verbatim (do not regenerate) | `<report>.html` + `.json` sidecar with the command line, config, hashes | a missing raw report invalidates the leg |
| 5 | **parse** | `python tools/run_mt5_backtest.py parse <report.html>` | metrics JSON extracted by `mt5tester.py`'s table extractor | parse failure = leg not ran; never hand-type numbers |
| 6 | **Every Tick run** | `run` with the tester model grade set to **Every tick** (same window/params) | raw Every-tick report + sidecar, archived like step 4 | missing/skipped grade ⇒ the ladder is incomplete ⇒ NOT VERIFIED |
| 7 | **Every Tick based on real ticks run** | `run` with the model grade **Every tick based on real ticks** (broker tick data required; same window/params) | raw real-tick report + sidecar, archived | no broker tick data for the window ⇒ leg unavailable ⇒ NOT VERIFIED with the reason |
| 8 | **compare Python vs MT5** | `certify.run_certification(..., python_data=...)` | Python TRUTH M1-OHLC cross-check leg + slippage-surcharge tiers + the OBSERVED MT5-vs-Python degradation per regime | divergence is a FINDING, reported AS OBSERVED (never normalized away); the 30–50% band is INFORMATIONAL ONLY and never gates (see below) |
| 9 | **archive manifest** | bind the certification to the pipeline manifest: `CertifyConfig.manifest_id` = the S5-certified manifest id; archive the report, ALL raw reports (steps 3–7), logs and the registry entry (identity + status model) | one immutable certification record (input → output → verdict → status model) | an unbound report is diagnostics, not certification |
| 10 | **assign certification state** | `report["status_model"]` (Blocker 7): exactly one of the five states below | the ONLY place a strategy may be called verified | "the tool executed successfully" is step 1–5 software truth and NEVER upgrades a state by itself |

## Certification states (exactly five)

| state | meaning | who may set it |
|---|---|---|
| `SOFTWARE_PASS` | software-level gates only: compile 0/0, sandbox suite green, pipeline certification path complete — no terminal claim implied | sandbox / CI |
| `EMPIRICAL_VALIDATION_PENDING` | S1–S5 passed on the research stack; the MT5 ladder (steps 2–8) has not run | pipeline |
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

## Checklist (per certification attempt)

- [ ] Windows terminal host with the broker data folder identified
- [ ] `tools/compile.ps1 -Strict` exit 0, log archived, `.ex5` SHA-256 recorded
- [ ] repo state (commit hash) recorded next to the log
- [ ] regime × model ladder jobs generated (`matrix`), one job per leg, one per model grade (M1-OHLC / Every tick / real ticks)
- [ ] every leg's RAW HTML report archived (never overwritten by a rerun)
- [ ] every leg parsed by `run_mt5_backtest.py parse` (no manual numbers)
- [ ] Python TRUTH cross-check leg ran on the same window/params
- [ ] 100-trade minimum met per required leg
- [ ] spread floor met (or explicitly not configured — then it cannot gate)
- [ ] degradation REPORTED AS OBSERVED per regime (band informational only — never a gate; findings recorded)
- [ ] `certify.run_certification` verdict == `VERIFIED` with zero reasons
- [ ] `manifest_id` binding recorded (S5 certification identity)
- [ ] `status_model` section of the report == expected statuses
- [ ] artifacts committed/archived: logs, reports, JSON, registry file

## Anti-fabrication rules (enforced by the code, restated here)

1. The sandbox cannot run steps 2–6; `mt5_stage` returns `status:
   "skipped"` with the reason — never a synthetic result.
2. A compile success (step 1) is a SOFTWARE fact: it never appears as a
   strategy status.
3. Parse outputs come only from `mt5tester.py`'s extractor over the raw
   report; no metric is ever hand-entered.
4. `verdict_for` lists EVERY failing reason; partial passes are
   `NOT VERIFIED`, never "verified with caveats".
5. `status.py` makes `VERIFIED` unreachable without a real terminal
   ladder pass (tested: `tests/test_status_model.py`,
   `tests/test_certify.py`).

---

## Owner SHADOW test for the Meta Layer (empirical-gate Phase 24)

Run AFTER the normal compile gate (steps 1–2 above) with the NEW
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
