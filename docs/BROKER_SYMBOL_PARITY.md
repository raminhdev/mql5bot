# BROKER SYMBOL PARITY — Mission 3 / AEGIS Phase 3

Parity of broker/symbol reality against the owner's live-account exports.
**Owner-gated**: the sandbox cannot reach a broker, so every owner-side
number is PENDING until the owner commits `data/broker_exports/*.json`
(produced by `mql5/Scripts/Mql5Bot/Mql5BotExportSymbolSpec.mq5`). No broker
parameter is ever invented here.

## Mandated field map (pinned by `tests/test_broker_symbol_parity.py`)

| Owner export field (MT5 source) | Python `SymbolSpec` | MQL5 `SSymbolSpec` | Consumers | Tolerance |
|---|---|---|---|---|
| digits (SYMBOL_DIGITS) | `digits` | `digits` | rounding | exact |
| point (SYMBOL_POINT) | `point` | `point` | stops/freeze conversion | rel 1e-12 |
| tick_size (SYMBOL_TRADE_TICK_SIZE) | `tick_size` | `tickSize` | round_to_tick/ticks_of/min-stop | rel 1e-12 |
| tick_value_profit (SYMBOL_TRADE_TICK_VALUE_PROFIT) | `tick_value_profit` | `tickValueProfit` | gain valuation | rel 1e-9 |
| tick_value_loss (SYMBOL_TRADE_TICK_VALUE_LOSS) | `tick_value_loss` | `tickValueLoss` | **loss_per_lot → SL sizing** | rel 1e-9 |
| contract_size (SYMBOL_TRADE_CONTRACT_SIZE) | `contract_size` | `contractSize` | engine P/L | rel 1e-9 |
| volume_min / volume_max / volume_step / volume_limit | `volume_*` | `volume*` | volume grid & caps | exact |
| stops_level_points (SYMBOL_TRADE_STOPS_LEVEL) | `stops_level_points` | `stopsLevelPoints` | sizer, SlGuard, pending offset | exact |
| freeze_level_points (SYMBOL_TRADE_FREEZE_LEVEL) | `freeze_level_points` | `freezeLevelPoints` | freeze guard | exact |
| currency_profit (SYMBOL_CURRENCY_PROFIT) | `currency_profit` | `currencyProfit` | profit→deposit conversion | exact |
| trade_mode (SYMBOL_TRADE_MODE) | — (runtime) | `tradeMode` | OnNewBar entry gates | exact |
| filling_mode_mask (SYMBOL_FILLING_MODE) | — (runtime) | `fillingMode` | filling ladder FOK→IOC→RETURN | exact |
| order_mode / expiration_mode_mask | — (runtime) | `orderMode`/`expirationMode` | pending policy | exact |
| margin_initial / margin_maintenance (SYMBOL_MARGIN_*) + OrderCalcMargin probe | — (runtime `OrderCalcMargin` is authority) | — (runtime) | margin sanity cross-check | rel 1e-9 |

Asset classes required: **FX, METAL, INDEX CFD, CRYPTO** (one symbol each the
broker actually offers).

## Derived P/L identity (tick value cross-check)

`tick_value ≈ contract_size × tick_size × fx(profit→deposit)` — evaluated
only when the owner supplies the FX conversion; otherwise PENDING. The sizer
primitives (`round_to_tick`, `normalize_volume` floor semantics, `loss_per_lot`)
are replayed against the OWNER's exported grid so parity is behavioural, not
just field-by-field.

## Status

| Item | Status |
|---|---|
| Export script (`Mql5BotExportSymbolSpec.mq5`) | WRITTEN (compile owner-gated) |
| Harness (`tools/broker_symbol_parity.py`) | COMPLETE, tested |
| Schema validation + strict fail-fast | COMPLETE, tested |
| Owner exports (FX/METAL/INDEX/CRYPTO) | **PENDING — owner only** |
| Parity verdict | **NOT VERIFIED** |
