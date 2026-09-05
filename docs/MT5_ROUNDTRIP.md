# AEGIS — MT5 TRUTH ROUND-TRIP (owner workflow, Phase 3 hardening)

Blocker 8 deliverable. The exact sequence a TERMINAL OWNER (a Windows
machine with a real MetaTrader 5 installation) runs to move a strategy
from `EMPIRICAL_VALIDATION_PENDING` toward `VERIFIED`.  **Nothing in
this loop may be fabricated**: every step consumes the previous step's
real artifact, and the sandbox (no terminal) can never produce any of
steps 2–7.  Until this loop has actually been executed, the MT5 status
is exactly `NOT VERIFIED` — which is not a failure and not a pass.

Companions: `docs/CERTIFICATION.md` (ladder + gates),
`python/mql5bot/certify.py` (verdict machine),
`tools/compile.ps1` (compile gate), `tools/run_mt5_backtest.py`
(tester driver), `python/mql5bot/mt5tester.py` (report parsing),
`python/mql5bot/status.py` (status model).

---

## The required Windows sequence

| # | Step | Tool / command | Artifact produced | Failure mode |
|---|------|----------------|-------------------|--------------|
| 1 | **compile** | `tools/compile.ps1 -Strict` | combined log `logs/compile-<stamp>.log` with verbatim compiler output + SHA-256 of each fresh `.ex5` (an `.ex5` older than the compile start is NOT proof) | exit 1/2/3/4 → stop; record `SOFTWARE_FAIL`, MT5 stays NOT VERIFIED |
| 2 | **run tester** | `python tools/run_mt5_backtest.py run --config <job>.json` (per leg of the regime × model ladder) | tester artifacts + RAW HTML report preserved verbatim before any parsing | non-zero exit → record the raw error; never retry silently into a "pass" |
| 3 | **capture raw report** | `run` already preserves the raw report; archive it (do not regenerate) | `<report>.html` + `.json` sidecar with the command line, config, hashes | a missing raw report invalidates the leg |
| 4 | **parse report** | `python tools/run_mt5_backtest.py parse <report.html>` | metrics JSON extracted by `mt5tester.py`'s table extractor | parse failure = leg not ran; never hand-type numbers |
| 5 | **compare against Python** | `certify.run_certification(..., python_data=...)` | Python TRUTH M1-OHLC cross-check leg + slippage-surcharge tiers + OHLC-vs-tick degradation table (30–50% expected band, explicit flags) | divergence outside the documented band is a FINDING, reported, never normalized away |
| 6 | **real-tick certification** | full ladder via `certify.run_certification(cfg, run_tester=...)` — every tick grade (M1-OHLC → every-tick → real ticks) per regime | `report` dict + rendered markdown; verdict `VERIFIED` only when EVERY required leg ran ok AND the 100-trade minimum AND the spread floor AND the degradation band held | any unavailable/failed leg ⇒ NOT VERIFIED with every reason listed |
| 7 | **record manifest** | bind the certification to the pipeline manifest: `CertifyConfig.manifest_id` = the S5-certified manifest id; archive report + raw artifacts + registry entry (identity + status model) | one immutable certification record (input → output → verdict → status model) | an unbound report is diagnostics, not certification |
| 8 | **assign status** | `report["status_model"]` (Blocker 7): `VERIFIED` only from step 6 passing; `FAILED` when a required leg ran and failed; `EMPIRICAL_VALIDATION_PENDING` + MT5 `NOT VERIFIED` otherwise | the ONLY places a strategy may be called verified | "the tool executed successfully" is step 1–4 software truth and NEVER upgrades a status by itself |

## Checklist (per certification attempt)

- [ ] Windows terminal host with the broker data folder identified
- [ ] `tools/compile.ps1 -Strict` exit 0, log archived, `.ex5` SHA-256 recorded
- [ ] repo state (commit hash) recorded next to the log
- [ ] regime × model ladder jobs generated (`matrix`), one job per leg
- [ ] every leg's RAW HTML report archived (never overwritten by a rerun)
- [ ] every leg parsed by `run_mt5_backtest.py parse` (no manual numbers)
- [ ] Python TRUTH cross-check leg ran on the same window/params
- [ ] 100-trade minimum met per required leg
- [ ] spread floor met (or explicitly not configured — then it cannot gate)
- [ ] degradation inside the 30–50% band per regime (or finding recorded)
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
