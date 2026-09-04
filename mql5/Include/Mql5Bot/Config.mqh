//+------------------------------------------------------------------+
//|                                            Mql5Bot/Config.mqh    |
//|        Shared types, enums and constants for the mql5bot EA      |
//+------------------------------------------------------------------+
#property copyright "mql5bot contributors"
#property version   "1.0.0"
#property strict

#ifndef MQL5BOT_CONFIG_MQH
#define MQL5BOT_CONFIG_MQH

//--- Bot version ---------------------------------------------------+
#define MQL5BOT_VERSION      "1.0.0"
#define MQL5BOT_NAME         "mql5bot"
#define MQL5BOT_WEBENDPOINT  "https://httpbin.org/post"

//--- Strategy selection --------------------------------------------+
enum ENUM_MQL5BOT_STRATEGY
  {
   STRAT_EMA_CROSSOVER       = 0, // EMA crossover
   STRAT_RSI_REVERSAL        = 1, // RSI reversal
   STRAT_DONCHIAN_BREAKOUT   = 2, // Donchian breakout
   STRAT_BOLLINGER_REVERSAL  = 3, // Bollinger reversal
   STRAT_MACD_MOMENTUM       = 4  // MACD momentum
  };

//--- Entry execution style ------------------------------------------+
enum ENUM_MQL5BOT_ENTRY_MODE
  {
   ENTRY_MARKET  = 0, // market orders
   ENTRY_PENDING = 1  // pending stop orders
  };

//--- Session day-of-week bitmask (MQL5: 0=Sunday .. 6=Saturday) ------+
#define SESSION_SUNDAY     0x01
#define SESSION_MONDAY     0x02
#define SESSION_TUESDAY    0x04
#define SESSION_WEDNESDAY  0x08
#define SESSION_THURSDAY   0x10
#define SESSION_FRIDAY     0x20
#define SESSION_SATURDAY   0x40
#define SESSION_WEEKDAYS   0x3E

//--- Strategy parameters shared by SignalEngine and strategies ------+
struct SBotParams
  {
   int      fastEma;
   int      slowEma;
   int      rsiPeriod;
   double   rsiOversold;
   double   rsiOverbought;
   int      donchianPeriod;
   int      bollingerPeriod;
   double   bollingerDev;
   int      macdFast;
   int      macdSlow;
   int      macdSignal;
   double   slAtr;              // stop-loss distance in ATR multiples
   double   tpAtr;              // take-profit distance in ATR multiples
  };

//--- One evaluation of the active strategy --------------------------+
struct SBotSignal
  {
   int      direction;          // -1 sell, 0 flat, +1 buy
   double   slPrice;            // absolute stop-loss (0 = unset)
   double   tpPrice;            // absolute take-profit (0 = unset)
   bool     valid;
  };

//--- Normalised volume helper ----------------------------------------+
double NormalizeLots(double lots, double step, double minLots, double maxLots)
  {
   if(step <= 0.0)
      step = 0.01;
   double steps = MathRound(lots / step);
   double norm  = steps * step;
   if(norm < minLots)
      norm = minLots;
   if(norm > maxLots)
      norm = maxLots;
   return norm;
  }

//--- Retryable trade server return codes -----------------------------+
bool IsRetryableRetcode(uint retcode)
  {
   switch(retcode)
     {
      case TRADE_RETCODE_REQUOTE:       // 10004
      case TRADE_RETCODE_RETRY:         // 10006
      case TRADE_RETCODE_NO_QUOTES:     // 10018
      case TRADE_RETCODE_PRICE_CHANGED: // 10020
      case TRADE_RETCODE_PRICE_OFF:     // 10021
      case TRADE_RETCODE_TIMEOUT:       // 10028
         return true;
     }
   return false;
  }

//--- Human readable retcode (subset) ----------------------------------+
string RetcodeToString(uint retcode)
  {
   switch(retcode)
     {
      case TRADE_RETCODE_DONE:            return "DONE";
      case TRADE_RETCODE_DONE_PARTIAL:    return "DONE_PARTIAL";
      case TRADE_RETCODE_PLACED:          return "PLACED";
      case TRADE_RETCODE_INVALID_VOLUME:  return "INVALID_VOLUME";
      case TRADE_RETCODE_INVALID_PRICE:   return "INVALID_PRICE";
      case TRADE_RETCODE_INVALID_STOPS:   return "INVALID_STOPS";
      case TRADE_RETCODE_MARKET_CLOSED:   return "MARKET_CLOSED";
      case TRADE_RETCODE_NO_MONEY:        return "NO_MONEY";
      case TRADE_RETCODE_PRICE_CHANGED:   return "PRICE_CHANGED";
      case TRADE_RETCODE_PRICE_OFF:       return "PRICE_OFF";
      case TRADE_RETCODE_REQUOTE:         return "REQUOTE";
      case TRADE_RETCODE_RETRY:           return "RETRY";
      case TRADE_RETCODE_NO_QUOTES:       return "NO_QUOTES";
      case TRADE_RETCODE_TIMEOUT:         return "TIMEOUT";
      case TRADE_RETCODE_INVALID_FILL:    return "INVALID_FILL";
      case TRADE_RETCODE_TOO_MANY_REQUESTS: return "TOO_MANY_REQUESTS";
      default:                            return "UNKNOWN";
     }
  }

#endif // MQL5BOT_CONFIG_MQH
//+------------------------------------------------------------------+
