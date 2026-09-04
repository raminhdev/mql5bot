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
  baseline per regime — relative net-profit fall in percent with an
  explicit `inside_band` flag against the expected **30–50%** band.
  Degradation is reported as a finding on every leg that ran; it is
  never hidden and never silently waived.  Undefined baselines
  (non-positive base net profit) are reported as `None`, not guessed.
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
