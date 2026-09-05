//+------------------------------------------------------------------+
//|                               Mql5Bot/Mql5BotExportSymbolSpec.mq5|
//| Owner-run broker reality export (AEGIS Phase 3).                 |
//|                                                                  |
//| Dumps every broker fact the parity harness needs for the chart   |
//| symbol into MQL5\Files\Mql5Bot\broker_exports\<SYMBOL>.json:     |
//| tick size/value(P/L), contract size, volume min/max/step/limit,  |
//| stops/freeze levels, digits, point, currencies, trade/filling/   |
//| order/expiration modes, margin mode, static margin rates and an  |
//| OrderCalcMargin probe (1.0 lot at mid).                          |
//|                                                                  |
//| Run on the LIVE account of record, then commit the JSON under    |
//| data/broker_exports/ and re-run tools/broker_symbol_parity.py.   |
//+------------------------------------------------------------------+
#property script_show_inputs
#property strict

input string InpExportDir = "Mql5Bot\\broker_exports\\"; // relative to MQL5\Files

string JsonQuote(string s)
  {
   return "\"" + s + "\"";
  }

void Main()
  {
   string sym = _Symbol;

   double bid = SymbolInfoDouble(sym, SYMBOL_BID);
   double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
   double mid = (bid > 0.0 && ask > 0.0) ? 0.5 * (bid + ask) : 0.0;

   double marginInitial = 0.0, marginMaintenance = 0.0;
   double probeMarginBuy = 0.0, probeMarginSell = 0.0;
   bool probeOk = false;
   if(mid > 0.0)
     {
      probeOk = OrderCalcMargin(ORDER_TYPE_BUY, sym, 1.0, mid, probeMarginBuy)
                && OrderCalcMargin(ORDER_TYPE_SELL, sym, 1.0, mid,
                                   probeMarginSell);
     }

   long filling = SymbolInfoInteger(sym, SYMBOL_FILLING_MODE);
   long orderMode = SymbolInfoInteger(sym, SYMBOL_ORDER_MODE);

   string j = "{\n";
   j += "  " + JsonQuote("schema") + ": " + JsonQuote("mql5bot.broker_export/1") + ",\n";
   j += "  " + JsonQuote("exported_at") + ": " + JsonQuote(TimeToString(TimeGMT(), TIME_DATE|TIME_SECONDS) + " GMT") + ",\n";
   j += "  " + JsonQuote("account_login") + ": " + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ",\n";
   j += "  " + JsonQuote("account_currency") + ": " + JsonQuote(AccountInfoString(ACCOUNT_CURRENCY)) + ",\n";
   j += "  " + JsonQuote("account_margin_mode") + ": " + IntegerToString(AccountInfoInteger(ACCOUNT_MARGIN_MODE)) + ",\n";
   j += "  " + JsonQuote("server") + ": " + JsonQuote(AccountInfoString(ACCOUNT_SERVER)) + ",\n";
   j += "  " + JsonQuote("symbol") + ":\n  {\n";
   j += "    " + JsonQuote("name") + ": " + JsonQuote(sym) + ",\n";
   j += "    " + JsonQuote("path") + ": " + JsonQuote(SymbolInfoString(sym, SYMBOL_PATH)) + ",\n";
   j += "    " + JsonQuote("digits") + ": " + IntegerToString(SymbolInfoInteger(sym, SYMBOL_DIGITS)) + ",\n";
   j += "    " + JsonQuote("point") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_POINT), 12) + ",\n";
   j += "    " + JsonQuote("tick_size") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE), 12) + ",\n";
   j += "    " + JsonQuote("tick_value_profit") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE_PROFIT), 12) + ",\n";
   j += "    " + JsonQuote("tick_value_loss") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE_LOSS), 12) + ",\n";
   j += "    " + JsonQuote("contract_size") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE), 12) + ",\n";
   j += "    " + JsonQuote("volume_min") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN), 12) + ",\n";
   j += "    " + JsonQuote("volume_max") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX), 12) + ",\n";
   j += "    " + JsonQuote("volume_step") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP), 12) + ",\n";
   j += "    " + JsonQuote("volume_limit") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_VOLUME_LIMIT), 12) + ",\n";
   j += "    " + JsonQuote("stops_level_points") + ": " + DoubleToString(SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL), 0) + ",\n";
   j += "    " + JsonQuote("freeze_level_points") + ": " + DoubleToString(SymbolInfoInteger(sym, SYMBOL_TRADE_FREEZE_LEVEL), 0) + ",\n";
   j += "    " + JsonQuote("spread_points") + ": " + DoubleToString(SymbolInfoInteger(sym, SYMBOL_SPREAD), 0) + ",\n";
   j += "    " + JsonQuote("trade_mode") + ": " + IntegerToString(SymbolInfoInteger(sym, SYMBOL_TRADE_MODE)) + ",\n";
   j += "    " + JsonQuote("filling_mode_mask") + ": " + IntegerToString(filling) + ",\n";
   j += "    " + JsonQuote("order_mode") + ": " + IntegerToString(orderMode) + ",\n";
   j += "    " + JsonQuote("expiration_mode_mask") + ": " + IntegerToString(SymbolInfoInteger(sym, SYMBOL_EXPIRATION_MODE)) + ",\n";
   j += "    " + JsonQuote("currency_profit") + ": " + JsonQuote(SymbolInfoString(sym, SYMBOL_CURRENCY_PROFIT)) + ",\n";
   j += "    " + JsonQuote("currency_base") + ": " + JsonQuote(SymbolInfoString(sym, SYMBOL_CURRENCY_BASE)) + ",\n";
   j += "    " + JsonQuote("currency_margin") + ": " + JsonQuote(SymbolInfoString(sym, SYMBOL_CURRENCY_MARGIN)) + ",\n";
   j += "    " + JsonQuote("margin_initial") + ": " + DoubleToString(marginInitial, 12) + ",\n";
   j += "    " + JsonQuote("margin_maintenance") + ": " + DoubleToString(marginMaintenance, 12) + ",\n";
   j += "    " + JsonQuote("swap_long") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_SWAP_LONG), 12) + ",\n";
   j += "    " + JsonQuote("swap_short") + ": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_SWAP_SHORT), 12) + ",\n";
   j += "    " + JsonQuote("swap_mode") + ": " + IntegerToString(SymbolInfoInteger(sym, SYMBOL_SWAP_MODE)) + ",\n";
   j += "    " + JsonQuote("margin_probe") + ":\n    {\n";
   j += "      " + JsonQuote("ok") + ": " + (probeOk ? "true" : "false") + ",\n";
   j += "      " + JsonQuote("price") + ": " + DoubleToString(mid, 12) + ",\n";
   j += "      " + JsonQuote("buy_1lot") + ": " + DoubleToString(probeMarginBuy, 12) + ",\n";
   j += "      " + JsonQuote("sell_1lot") + ": " + DoubleToString(probeMarginSell, 12) + "\n";
   j += "    }\n";
   j += "  }\n}\n";

   string fname = InpExportDir + sym + ".json";
   int fh = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
     {
      Print("[mql5bot] export FAILED: cannot open ", fname, " err=", GetLastError());
      return;
     }
   FileWriteString(fh, j);
   FileClose(fh);
   Print("[mql5bot] exported ", sym, " -> MQL5\\Files\\", fname);
  }
//+------------------------------------------------------------------+
//| Script entry                                                     |
//+------------------------------------------------------------------+
void OnStart()
  {
   Main();
  }
