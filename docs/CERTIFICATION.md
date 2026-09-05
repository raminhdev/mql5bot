# Real-tick certification protocol (plan Phase F)

`mql5bot.certify` + `tools/certify_strategy.py`. One idea: a result is
VERIFIED only through the graded data ladder on the same EA and the
same terminal, per regime — never through a single OHLC print.

## Data-grade ladder (tester models, per regime)

| Grade | MT5 model | Meaning |
|---|---|---|
| M1 OHLC | 1 | baseline built from 1-minute bars |
| Every tick | 0 | synthetic ticks interpolated from M1 |
| Every tick on real ticks | 3 | real-tick tick structure |
| Real ticks | 4 | broker tick history |

Every required leg of the ladder must run and pass its gates for a
VERIFIED verdict. Without an MT5 terminal host the legs cannot run and
the verdict is NOT VERIFIED with the reason — nothing is guessed.

## Regime sample (multi-regime, incl. bear and crash)

| regime | window | character |
|---|---|---|
| bear_2022 | 2022.01.01–2022.06.30 | Fed-hike bear trend |
| crash_2020 | 2020.02.20–2020.04.30 | COVID crash + whipsaw recovery |
| trend_2021 | 2021.01.01–2021.06.30 | sustained trend |
| range_2023 | 2023.01.01–2023.06.30 | choppy range |

## Gates and explicit reports

- **100-trade minimum** per required leg (and asserted in the verdict).
- **Spread floor**: the modelled average spread vs the configured floor,
  in pips; a missing average fails loudly (floors are never assumed).
- **Slippage surcharge tiers 0.5–3.0 pips**: applied analytically to the
  canonical Python TRUTH M1-OHLC leg (per side, tick-valued) and
  reported per tier.
- **OHLC-vs-tick degradation**: every tick grade vs its own M1-OHLC
  baseline per regime — the OBSERVED relative net-profit change in
  percent, reported as measured (10%, 20%, 60%, 80%: whatever the run
  actually shows).  The historical **30–50%** band is INFORMATIVE ONLY:
  it is stated alongside the observation (`inside_band` flag) and is
  NEVER a pass/fail requirement — a valid strategy must not be rejected
  for landing outside an arbitrary range.  Degradation never gates the
  verdict; it is a finding on every leg that ran, never hidden, never
  silently waived.  Undefined baselines (non-positive base net profit)
  are reported as `None`, not guessed.  Treating the band as a hard
  gate would require new empirical evidence, documented as a protocol
  revision.
- **Python cross-check leg**: an independent canonical TRUTH-engine M1
  run bound to the same (strategy, params) manifest; recorded, never
  gates the verdict.

## Usage

```bash
# config.json mirrors mql5bot.certify.CertifyConfig
python tools/certify_strategy.py --config config.json --out report.md \
    [--data ohlc.parquet]     # optional python cross-check leg
```

Exit code 0 = VERIFIED; 1 = anything else (including every NOT VERIFIED
case). The MT5 runner binds only on Windows terminal hosts
(`mt5tester.RunSettings`); everywhere else every tester leg is reported
as not run.

## Honesty rules

- `VERIFIED` / `NOT VERIFIED` are derived only from leg outcomes above
  them in the report; never typed by hand, never carried over.
- Backtests — Python or tester — are research evidence, not a promise
  of live profit (README "Research evidence, not promises").

## Certification identity (Phase 3 hardening — one-look registry)

The OOS one-look registry (`mql5bot.pipeline.OosRegistry`, schema 2) keys
every certification on the EXACT identity
(`mql5bot.pipeline.OosIdentity`):

| Field | Source |
|---|---|
| `dataset_content_digest` | content digest of the OOS frame (always; an explicit `dataset_tag` is carried but never the anchor) |
| `strategy` / `strategy_version` | registry declaration |
| `engine` / `engine_version` | `truth` + `mql5bot.versions.ENGINE_VERSION` |
| `cost_model_version` / `cost_config_digest` | `mql5bot.versions.COST_MODEL_VERSION` + content digest of the cost kwargs |
| `feature_version` | `mql5bot.versions.FEATURE_VERSION` (signal/indicator semantics) |
| `certification_protocol_version` | `mql5bot.versions.CERTIFICATION_PROTOCOL_VERSION` |

Enforcement is intentionally STRONGER than "one look per
(dataset_version, strategy)":

1. the exact identity is refused on a second look (one look, recorded,
   forever);
2. the same (dataset content, strategy) pair is refused under ANY
   identity — bumping a strategy version, cost model, feature version or
   protocol version cannot mint a fresh look on the same data; the
   violation names exactly which identity fields changed;
3. a tag change on the same content is refused (tags never weaken the
   identity).

Every recorded entry carries its full identity, the honest status model
(`EMPIRICAL_VALIDATION_PENDING`, MT5 `NOT VERIFIED`) and the complete
cost configuration, so a certification is reproducible and auditable
from the registry alone.

### Failure/recovery policy (explicit)

* A REFUSED look (second attempt on a used slice) raises before any
  run and records nothing.
* An attempt whose RUN FAILS (engine/terminal exception) records
  nothing and consumes NO look: no result was observed, so no knowledge
  leaked; a retry after fixing the cause is permitted
  (`tests/test_oos_registry.py::test_failed_attempt_consumes_nothing_
  retry_permitted_once_locked`).  This grants no parameter-shopping
  latitude: the FIRST successful look locks the (dataset content,
  strategy) pair forever, whatever attempts preceded it.
* No other recovery path exists.  There is no "re-certify", "reset" or
  "force" operation on the registry, and none may be added without a
  documented protocol revision.
