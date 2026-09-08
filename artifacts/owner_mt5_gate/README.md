# OWNER MT5 EXECUTION PACKAGE (OWNER MT5 EXECUTION GATE)

One directory, one attempt, raw artifacts only. This package defines
EXACTLY what the owner executes and returns. The canonical procedure is
the TEN-step protocol in `docs/MT5_ROUNDTRIP.md` (single source of
truth); this directory is its artifact scaffold.

**Certification status while this package is unexecuted:**
`REALITY_GATE_BLOCKED` · `PRODUCTION = NOT_READY`. No screenshot is
evidence; no text summary substitutes a raw artifact.

## Machine

Windows · MetaTrader 5 (broker build) · MetaEditor 5 · PowerShell.

## Frozen inputs (verify BEFORE any run — §2)

`frozen_inputs.json` (generated mechanically from the frozen manifests)
lists every hash the owner must reproduce locally:

* Gold #1 fixture / manifest / expected-execution SHA-256 + dataset hash
* Gold #2 fixture / manifest / expected-execution SHA-256 + dataset hash
  + the full six-artifact provenance chain
  (`GOLD_2_RECONSTRUCTED_NEW_PROVENANCE` — never regenerated, never
  enlarged; 56 trades IS the semantic contract)
* the exact source commit to compile

Any hash mismatch ⇒ STOP. Do not regenerate, do not re-download,
re-clone the pinned commit and re-verify. The owner executes the exact
frozen artifacts — nothing else.

## The 16 returned artifacts (§30) — slot by slot

| # | artifact | filename convention | requirement |
|---|---|---|---|
| 1 | compile log | `logs/compile-<stamp>.log` | verbatim; 0 errors / 0 warnings counted FROM the log |
| 2 | compiler metadata | `compile_metadata.json` | the six provenance fields below |
| 3 | EX5 hash | inside `compile_metadata.json` | SHA-256 of every fresh `.ex5` |
| 4 | SymbolSpec | `data/broker_exports/<symbol>-<stamp>.json` | actual terminal/broker export; never the synthetic parity spec |
| 5–7 | Gold #1 reports | `gold1_m1ohlc.htm`, `gold1_everytick.htm`, `gold1_realticks.htm` | RAW tester reports (one per model) |
| 8–10 | Gold #2 reports | `gold2_m1ohlc.htm`, `gold2_everytick.htm`, `gold2_realticks.htm` | RAW tester reports (one per model) |
| 11 | parsed reports | `<leg>.parsed.json` | via `run_mt5_backtest.py parse` — never hand-typed metrics |
| 12 | reconciliation | `reconciliation_owner.json` | field-by-field vs both expected_execution artifacts; closed taxonomy |
| 13 | real-tick coverage | `real_tick_coverage.json` | template in this directory; FULL is never assumed |
| 14 | terminal/broker metadata | `environment.json` | OS, terminal build, tester build, broker/server, account mode |
| 15 | final manifest | `certification_manifest.json` | template in this directory — the complete identity chain |
| 16 | certification verdict | `certify_strategy.py` stdout | run with `--reconciliation` pointing at artifact 12 |

## Compiler provenance (§6) — the six mandatory fields

`compile_metadata.json` must contain (raw evidence, not prose):

| field | source |
|---|---|
| `SOURCE_COMMIT` | `git rev-parse HEAD` in the owner's clone (must equal `frozen_inputs.json`) |
| `COMPILER_VERSION` | MetaEditor Help → About (exact build) |
| `TERMINAL_BUILD` | terminal Help → About (exact build) |
| `EX5_SHA256` | `Get-FileHash <each fresh .ex5> -Algorithm SHA256` |
| `COMPILE_TIMESTAMP` | UTC ISO-8601 of the compile run |
| `COMPILER_LOG_SHA256` | `Get-FileHash <compile log> -Algorithm SHA256` |

Reject and re-compile: a stale or cached `.ex5`, a missing log, a
warning-bearing build (`-Strict` exit ≠ 0), an unknown source revision.
"Compiled successfully" text without raw evidence is worthless.

## SymbolSpec comparison classes (§8)

Compare the actual export against the frozen gold assumptions
(`broker_symbol_parity.py` FIELD_MAP). Every field gets EXACTLY one
class:

* `EXACT_MATCH` — identical value;
* `SEMANTICALLY_COMPATIBLE` — differs without changing any decision
  (e.g. display rounding only) — justification recorded;
* `DECISION_CHANGING_MISMATCH` — sizing / stop constraint / volume grid
  / margin / execution differs ⇒ **STOP**; do NOT silently rewrite
  Gold #1/#2; report the mismatch as the evidence;
* `UNSUPPORTED_BROKER_DIFFERENCE` — broker cannot express the field —
  recorded, leg constrained accordingly.

## Tester model identity (§9) — the triad, per leg

Every leg records: `requested_model` (command line), `actual_model`
(report's Model line — parsed, never copied), and the terminal's model
identifier from the tester journal. Command line alone is never proof
of the model actually used.

## Real-tick coverage (§12/§13)

Official MetaTrader semantics: missing tick history makes the tester
GENERATE ticks in Every-tick mode. Therefore:

* `REAL_TICK_COVERAGE_FULL` — only with positive evidence that real
  ticks covered the WHOLE requested interval (journal/data evidence);
* `REAL_TICK_COVERAGE_PARTIAL` — any fallback interval (list them);
* `REAL_TICK_COVERAGE_UNKNOWN` — coverage cannot be proven. **This is
  the default.** Selecting the mode is NOT evidence of FULL.

## First-divergence procedure (§16/§17)

If reconciliation fails: locate the FIRST divergent bar/tick — not the
final PnL. Record Python state, MQL5 state, inputs, indicator values,
strategy/session/Meta/Risk/execution state at that event; classify with
the closed 14-class taxonomy; determine the causal source (data
modeling / indicator init / warmup / numeric representation / session
time / broker spec / normalization / Bid-Ask / spread / tick ordering /
latency / tester model) BEFORE any patch. Neither side is patched
blindly; a gold artifact is NEVER rewritten because MT5 disagrees —
the discrepancy IS the evidence (§18/§19).

## Stale-artifact defense (§29)

Every attack fails closed: old EX5 + new source, new EX5 + old config,
old report + new fixture, wrong broker SymbolSpec / symbol / timeframe /
model / source commit. Enforcement: compile.ps1 freshness + `-Strict`
(§5), `frozen_inputs.json` pre-flight hash check (§2), report model
line vs requested model (§9), manifest bindings in
`certification_manifest.json`, `report_gate` (empty/edited reports
refused), NOT_EXECUTABLE seam, and the red-team battery
(`tests/test_certify_redteam.py`). Any mismatch invalidates the
corresponding certification leg.

## Safety runtime tests (§20–§22) — after the gold runs

Kill Switch (zero new orders), Risk veto (order rejected), Meta reduce
(size ≤ Risk-approved), SL verify→modify→re-verify, lost-response
adoption-before-retry, restart matrix (pending/retry/open/allocation),
netting proof, hedging proof — exact procedures in
`docs/MT5_ROUNDTRIP.md` §Owner runtime safety procedures. If the
account type cannot exercise hedging: record
`BLOCKED_OWNER_ENVIRONMENT`, never a fabricated pass.

## Evidence directory contract (§6) — exactly one layout

The owner returns ONE directory with exactly these deterministic file
names. Missing mandatory files, duplicates, ambiguous names, stale
files, wrong-source-commit files and edited reports are all rejected by
the verifier — never silently repaired.

```
<evidence-dir>/
  compile/compile.log                      # verbatim MetaEditor output
  compile/compile_metadata.json            # the six provenance fields
  compile/Mql5Bot.ex5                      # fresh binary, hashed
  symbolspec/symbolspec.json               # full broker SymbolSpec dump
  gold1/m1_ohlc.htm  gold1/every_tick.htm  gold1/real_ticks.htm
  gold2/m1_ohlc.htm  gold2/every_tick.htm  gold2/real_ticks.htm
  parsed/gold1_<model>.json  parsed/gold2_<model>.json
  reconciliation/gold1.json                # bindings + per-event states
  reconciliation/gold2.json
  real_tick_coverage.json                  # requested/actual model+range
  safety/<kill_switch|risk_veto|meta_reduce|sl_verify|lost_response
         |restart|netting|hedging>.json    # raw evidence each
  environment.json
  archive_manifest.json                    # full identity chain
```

Every artifact is classified by the verifier into exactly one of:
`MISSING / PRESENT_UNVERIFIED / VALID / INVALID / STALE / MISMATCHED /
PENDING_OWNER` — never a single boolean.

## Consuming the evidence — one command (§32)

```
python tools/verify_owner_mt5_gate.py <evidence-dir> --repo . [--out report.json]
```

The command mechanically answers completeness, freshness, identity
binding (source commit by hash, never branch name), tester-model
identity, real-tick coverage, Gold #1/#2 reconciliation, the FIRST
divergence and its deterministic mismatch class, safety/netting/hedging
evidence, and assigns one explainable verdict:
`MT5_VALIDATED` or one of `NOT_VERIFIED_MISSING_MT5_EVIDENCE /
NOT_VERIFIED_RECONCILIATION_MISSING / NOT_VERIFIED_ARTIFACT_MISMATCH /
NOT_VERIFIED_REAL_TICK_COVERAGE_UNKNOWN`. Exit code is nonzero on every
negative verdict; missing, stale, wrong, partial or simulated evidence
can never become a positive verdict.

## Hard rules

* **No live capital** — Strategy Tester + controlled demo + owner
  environment only; no automated capital activation (§23).
* **Gold ≠ empirical** — the gold runs are semantic parity tests; the
  100-trade empirical regime ladder is a SEPARATE lane and is never
  satisfied by gold fixtures (§24).
* **Demo never auto-starts** — demo requires runtime validation + clean
  reconciliation + safety tests + confirmed SymbolSpec + operator
  review (§26).
* **Forbidden claims** unless directly evidenced: "works on MT5",
  "broker validated", "production ready", "safe for live", "real ticks
  passed", "profitable", "live validated" (§33). Use exact evidence
  terminology.
