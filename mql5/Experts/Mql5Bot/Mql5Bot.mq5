//+------------------------------------------------------------------+
//|                                                 Mql5Bot.mq5     |
//|              Full-featured Expert Advisor framework for MT5      |
//|                                                                  |
//|  - 5 strategies (EMA crossover, RSI reversal, Donchian breakout, |
//|    Bollinger reversal, MACD momentum)                            |
//|  - risk-based position sizing, daily loss limit, drawdown        |
//|    kill-switch, spread guard                                    |
//|  - ATR trailing stop, breakeven, partial scale-out               |
//|  - market or pending (stop-order) entries, retry logic           |
//|  - session/time-of-day filter, max-bars timeout, hedging safe    |
//|  - file logging + HTTP telemetry (WebRequest)                    |
//|                                                                  |
//|  The Python twin of every strategy lives in python/mql5bot/ —    |
//|  validate parameter sets there before going live.                |
//+------------------------------------------------------------------+
#property copyright "mql5bot contributors"
#property link      "https://github.com/raminhdev/mql5bot"
#property version   "1.0.0"
#property strict

#include <Mql5Bot/Config.mqh>
#include <Mql5Bot/Logger.mqh>
#include <Mql5Bot/Session.mqh>
#include <Mql5Bot/RiskManager.mqh>
#include <Mql5Bot/TradeManager.mqh>
#include <Mql5Bot/PositionGuard.mqh>
#include <Mql5Bot/SignalEngine.mqh>
#include <Mql5Bot/Telemetry.mqh>

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "=== Strategy ==="
input ENUM_MQL5BOT_STRATEGY InpStrategy      = STRAT_EMA_CROSSOVER;  // Strategy
input int                     InpFastEma     = 10;                   // EMA fast period
input int                     InpSlowEma     = 30;                   // EMA slow period
input int                     InpRsiPeriod   = 14;                   // RSI period
input double                  InpRsiOversold = 30.0;                 // RSI oversold
input double                  InpRsiOverbought = 70.0;               // RSI overbought
input int                     InpDonchianPeriod = 20;                // Donchian period
input int                     InpBollingerPeriod = 20;               // Bollinger period
input double                  InpBollingerDev  = 2.0;                // Bollinger deviations
input int                     InpMacdFast   = 12;                    // MACD fast
input int                     InpMacdSlow   = 26;                    // MACD slow
input int                     InpMacdSignal = 9;                     // MACD signal
input double                  InpSlAtr      = 2.5;                   // Stop-loss (ATR x)
input double                  InpTpAtr      = 4.0;                   // Take-profit (ATR x)

input group "=== Risk & money management ==="
input double                  InpRiskPercent = 1.0;                  // Risk % of equity per trade
input double                  InpMaxLots     = 10.0;                 // Max lots per trade
input double                  InpDailyLossPct = 0.0;                 // Daily loss limit % (0=off)
input double                  InpMaxDrawdownPct = 0.0;               // Max drawdown kill-switch % (0=off)
input double                  InpMaxSpreadPoints = 0.0;              // Max spread in points (0=off)
input int                     InpMaxBars     = 0;                    // Max bars per trade (0=off)

input group "=== Exits ==="
input double                  InpTrailAtr    = 0.0;                   // ATR trailing stop (0=off)
input double                  InpBreakevenAtr = 0.0;                  // Breakeven trigger (ATR, 0=off)
input double                  InpBreakevenOffset = 0.0;               // Breakeven offset (points)
input double                  InpPartialAtr  = 0.0;                   // Partial close trigger (ATR, 0=off)
input double                  InpPartialFraction = 0.5;               // Partial close fraction

input group "=== Execution ==="
input ENUM_MQL5BOT_ENTRY_MODE InpEntryMode  = ENTRY_MARKET;          // Entry mode
input int                     InpPendingOffsetPoints = 10;           // Pending order offset (points)
input int                     InpPendingExpireBars = 6;              // Pending expiry (bars)
input int                     InpDeviation   = 30;                   // Max price deviation (points)
input int                     InpMaxRetries  = 3;                    // Order retries
input int                     InpRetryDelayMs = 150;                 // Retry delay (ms)
input bool                    InpAllowShort  = true;                 // Allow short trades
input long                    InpMagic       = 20240904;             // Magic number

input group "=== Session filter ==="
input bool                    InpUseSession  = false;                // Enable session filter
input int                     InpSessionStartHour = 8;               // Session start hour (server)
input int                     InpSessionStartMin  = 0;               // Session start minute
input int                     InpSessionEndHour   = 17;              // Session end hour
input int                     InpSessionEndMin    = 0;               // Session end minute
input int                     InpSessionDays      = SESSION_WEEKDAYS; // Days bitmask (0=Sun .. 6=Sat)

input group "=== Logging & telemetry ==="
input int                     InpLogLevel    = 2;                    // 0=off 1=error 2=info 3=debug
input bool                    InpTelemetry   = false;                // Enable HTTP telemetry
input string                  InpWebhookUrl  = MQL5BOT_WEBENDPOINT;   // Webhook URL (add to allowed list)

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
CLogger         g_log;
CSessionFilter  g_session;
CRiskManager    g_risk;
CTradeManager   g_trade;
CPositionGuard  g_guard;
CSignalEngine   g_signal;
CTelemetry      g_tele;

datetime        g_lastBarTime   = 0;
datetime        g_lastHeartbeat = 0;
bool            g_dailyHit      = false;
bool            g_drawdownHit   = false;
bool            g_pendingSlotOpen = false;
int             g_todayDayOfYear = -1;
double          g_todayStartEquity = 0.0;
string          g_symbol = _Symbol;
ENUM_TIMEFRAMES g_tf     = _Period;

SBotParams      g_params;
SBotSignal      g_lastSignal;

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
string TfToString(ENUM_TIMEFRAMES tf)
  {
   switch(tf)
     {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_D1:  return "D1";
      default:         return "?";
     }
  }

int CountBotPositions()
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == g_symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
         count++;
     }
   return count;
  }

int CurrentExposure()
  {
   int dir = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == g_symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
        {
         long type = PositionGetInteger(POSITION_TYPE);
         dir += (type == POSITION_TYPE_LONG) ? 1 : -1;
        }
     }
   if(dir > 0) return 1;
   if(dir < 0) return -1;
   return 0;
  }

ulong FirstBotPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == g_symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return t;
     }
   return 0;
  }

void CloseAllPositions(string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == g_symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
        {
         if(g_trade.ClosePosition(g_symbol, t, 0.0))
            g_log.Info("closed position #" + IntegerToString(t) + " (" + reason + ")");
        }
     }
  }

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
  {
   PrintFormat("=== %s v%s starting on %s %s ===",
               MQL5BOT_NAME, MQL5BOT_VERSION, g_symbol, TfToString(g_tf));

   //--- params for the signal engine
   g_params.fastEma        = InpFastEma;
   g_params.slowEma        = InpSlowEma;
   g_params.rsiPeriod      = InpRsiPeriod;
   g_params.rsiOversold    = InpRsiOversold;
   g_params.rsiOverbought  = InpRsiOverbought;
   g_params.donchianPeriod = InpDonchianPeriod;
   g_params.bollingerPeriod= InpBollingerPeriod;
   g_params.bollingerDev   = InpBollingerDev;
   g_params.macdFast       = InpMacdFast;
   g_params.macdSlow       = InpMacdSlow;
   g_params.macdSignal     = InpMacdSignal;
   g_params.slAtr          = InpSlAtr;
   g_params.tpAtr          = InpTpAtr;

   //--- logger
   g_log.Init("Mql5Bot\\Logs\\", "mql5bot_" + g_symbol + "_" + TfToString(g_tf), InpLogLevel);

   //--- session filter
   g_session.Init(InpUseSession, InpSessionStartHour, InpSessionStartMin,
                  InpSessionEndHour, InpSessionEndMin, InpSessionDays);

   //--- risk manager
   g_risk.Init(InpRiskPercent, InpMaxLots, InpDailyLossPct,
               InpMaxDrawdownPct, InpMaxSpreadPoints);

   //--- signal engine
   if(!g_signal.Init(g_symbol, g_tf, g_params))
      return INIT_FAILED;

   //--- trade manager
   g_trade.Init(InpMagic, InpDeviation, InpMaxRetries, InpRetryDelayMs,
                InpEntryMode == ENTRY_PENDING, InpPendingExpireBars);

   //--- position guard
   if(!g_guard.Init(g_symbol, g_tf, InpTrailAtr, InpBreakevenAtr,
                    InpBreakevenOffset, InpPartialAtr, InpPartialFraction))
      return INIT_FAILED;

   //--- telemetry
   g_tele.Init(InpTelemetry, InpWebhookUrl, 2000);

   //--- day tracking
   g_todayDayOfYear   = -1;
   g_todayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);

   g_log.Info(StringFormat("initialised: strategy=%d risk=%.2f%% sl=%.2f ATR tp=%.2f ATR",
                           InpStrategy, InpRiskPercent, InpSlAtr, InpTpAtr));
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   g_log.Info("shutting down (reason " + IntegerToString(reason) + ")");
   g_signal.Deinit();
   g_log.Flush();
  }

//+------------------------------------------------------------------+
//| New-bar entry & exit logic (runs once per completed bar)         |
//+------------------------------------------------------------------+
void OnNewBar()
  {
   //--- pending order housekeeping (fills / expiry)
   if(g_trade.HasPendingOrder())
     {
      g_pendingSlotOpen = g_trade.OnBar(g_symbol) ? false : true;
     }
   else
     {
      g_pendingSlotOpen = false;
     }

   //--- day rollover
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   int doy = now.day_of_year;
   if(doy != g_todayDayOfYear)
     {
      g_todayDayOfYear   = doy;
      g_todayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_dailyHit         = false;
      g_risk.OnNewDay();
      g_log.Info("new trading day — daily limits reset");
     }

   //--- risk limits
   g_risk.CheckLimits(g_dailyHit, g_drawdownHit);
   if(g_drawdownHit)
     {
      g_log.Error("MAX DRAWDOWN LIMIT HIT — kill switch engaged");
      g_tele.Alert("critical", "max drawdown limit hit — trading disabled");
      CloseAllPositions("drawdown_kill");
      return;
     }
   if(g_dailyHit)
     {
      g_log.Error("DAILY LOSS LIMIT HIT — trading paused for today");
      g_tele.Alert("warning", "daily loss limit hit");
      CloseAllPositions("daily_loss_limit");
      return;
     }

   //--- exit management on open positions
   ulong ticket = FirstBotPosition();
   if(ticket != 0 && PositionSelectByTicket(ticket))
     {
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      int action = g_guard.Review(g_symbol, g_tf, ticket, sl, tp);

      if((action & EXIT_MODIFY_SLTP) != 0)
        {
         if(g_trade.ModifySLTP(g_symbol, ticket, sl, tp))
            g_log.Info(StringFormat("#%I64u exits updated: sl=%.5f tp=%.5f", ticket, sl, tp));
        }
      if((action & EXIT_CLOSE_PARTIAL) != 0)
        {
         double vol = PositionGetDouble(POSITION_VOLUME) * g_guard.PartialFraction();
         if(g_trade.ClosePosition(g_symbol, ticket, vol))
           {
            g_log.Info(StringFormat("#%I64u partial close %.2f lots (SL -> breakeven)",
                                    ticket, vol));
            g_tele.Trade(g_symbol, "partial_close", "guard", vol,
                         SymbolInfoDouble(g_symbol, SYMBOL_BID), 0.0, "scale-out");
           }
        }
     }

   //--- max-bars timeout
   if(ticket != 0 && InpMaxBars > 0 && PositionSelectByTicket(ticket))
     {
      datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
      int bars = iBarShift(g_symbol, g_tf, openTime, false);
      if(bars >= InpMaxBars)
        {
         if(g_trade.ClosePosition(g_symbol, ticket, 0.0))
            g_log.Info(StringFormat("#%I64u closed: max bars timeout (%d)", ticket, bars));
        }
     }

   //--- session filter
   if(!g_session.IsTradingTime(TimeCurrent()))
      return;

   //--- entries
   if(g_dailyHit || g_drawdownHit || g_risk.IsKillSwitch())
      return;
   if(!g_risk.IsSpreadOK())
      return;
   if(g_trade.HasPendingOrder())
      return;   // a pending entry is already working

   g_lastSignal = g_signal.Evaluate(InpStrategy);
   if(!g_lastSignal.valid)
      return;

   int desired = g_lastSignal.direction;
   if(desired < 0 && !InpAllowShort)
      desired = 0;
   if(desired == 0)
      return;

   int exposure = CurrentExposure();
   if(exposure == desired)
      return;
   if(exposure != 0)
     {
      // flip: close current, let the next bar open the new direction
      g_log.Info("signal flipped — closing opposite position");
      CloseAllPositions("signal_flip");
      return;
     }

   //--- size by risk over the stop distance
   double riskMoney = 0.0;
   double fill = (desired > 0) ? SymbolInfoDouble(g_symbol, SYMBOL_ASK)
                               : SymbolInfoDouble(g_symbol, SYMBOL_BID);
   double lots = g_risk.GetLots(fill, g_lastSignal.slPrice, riskMoney);

   if(lots <= 0.0)
     {
      g_log.Debug("no size: lots<=0");
      return;
     }

   double slDist = (g_lastSignal.slPrice > 0.0) ? MathAbs(fill - g_lastSignal.slPrice) : 0.0;
   double tpDist = (g_lastSignal.tpPrice > 0.0) ? MathAbs(fill - g_lastSignal.tpPrice) : 0.0;

   bool ok = false;
   if(g_trade.IsPendingMode())
      ok = g_trade.SendPending(g_symbol,
                               (desired > 0) ? POSITION_TYPE_LONG : POSITION_TYPE_SHORT,
                               lots, InpPendingOffsetPoints, slDist, tpDist,
                               IntegerToString(InpStrategy));
   else
      ok = g_trade.SendMarket(g_symbol,
                              (desired > 0) ? POSITION_TYPE_LONG : POSITION_TYPE_SHORT,
                              lots, slDist, tpDist,
                              IntegerToString(InpStrategy));

   if(ok)
     {
      g_guard.OnPositionOpened();
      g_log.Info(StringFormat("ENTRY %s %.2f lots risk=%.2f (%.2f%%) sl=%.5f tp=%.5f",
                              (desired > 0) ? "BUY" : "SELL", lots, riskMoney,
                              g_risk.RiskPercent(), g_lastSignal.slPrice, g_lastSignal.tpPrice));
      g_tele.Trade(g_symbol, (desired > 0) ? "buy" : "sell",
                   IntegerToString(InpStrategy), lots, fill, 0.0, "entry");
     }
  }

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- new bar?
   datetime barTime = iTime(g_symbol, g_tf, 0);
   if(barTime != g_lastBarTime)
     {
      if(g_lastBarTime != 0)      // skip the very first tick of the EA
         OnNewBar();
      g_lastBarTime = barTime;
     }

   //--- telemetry heartbeat (every 60s)
   if(g_tele.IsEnabled() && TimeCurrent() - g_lastHeartbeat >= 60)
     {
      g_lastHeartbeat = TimeCurrent();
      double dailyPnl = AccountInfoDouble(ACCOUNT_EQUITY) - g_todayStartEquity;
      g_tele.Heartbeat(g_symbol, TfToString(g_tf),
                       AccountInfoDouble(ACCOUNT_EQUITY),
                       AccountInfoDouble(ACCOUNT_BALANCE),
                       dailyPnl);
     }
  }

//+------------------------------------------------------------------+
//| OnTradeTransaction — log fills/close PnL via deal history        |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
     {
      ulong deal = trans.deal;
      if(HistoryDealSelect(deal))
        {
         long magic = HistoryDealGetInteger(deal, DEAL_MAGIC);
         if(magic == InpMagic)
           {
            double pnl    = HistoryDealGetDouble(deal, DEAL_PROFIT);
            double vol    = HistoryDealGetDouble(deal, DEAL_VOLUME);
            double price  = HistoryDealGetDouble(deal, DEAL_PRICE);
            string symbol = HistoryDealGetString(deal, DEAL_SYMBOL);
            g_log.Info(StringFormat("DEAL #%I64u %s vol=%.2f price=%.5f pnl=%.2f",
                                    deal, symbol, vol, price, pnl));
            if(pnl != 0.0)
               g_tele.Trade(symbol, "close", IntegerToString(InpStrategy),
                            vol, price, pnl, HistoryDealGetString(deal, DEAL_COMMENT));
           }
        }
     }
  }
//+------------------------------------------------------------------+
