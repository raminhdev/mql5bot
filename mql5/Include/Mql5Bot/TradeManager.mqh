//+------------------------------------------------------------------+
//|                                       Mql5Bot/TradeManager.mqh   |
//|     Order execution with retries, fill verification and pending  |
//|     stop-order support (hedging + netting safe)                  |
//+------------------------------------------------------------------+
#property strict

#ifndef MQL5BOT_TRADEMANAGER_MQH
#define MQL5BOT_TRADEMANAGER_MQH

#include <Mql5Bot/Config.mqh>

// How the manager reacts to ambiguous server answers:
//  - REQUOTE / PRICE_CHANGED / PRICE_OFF : refresh prices and resend
//  - NO_QUOTES                           : wait briefly and resend
//  - RETRY / TIMEOUT                     : verify against history first,
//                                          resend only if nothing was filled
// After the retry loop a final history check decides the outcome, so a
// duplicated fill is far less likely than a silent failure.

class CTradeManager
  {
private:
   ulong             m_magic;
   int               m_deviation;        // points
   int               m_maxRetries;
   int               m_retryDelayMs;
   bool              m_pendingMode;
   int               m_pendingExpireBars;
   ulong             m_pendingTicket;
   int               m_pendingBarsLeft;
   int               m_counter;          // unique comment suffix

   double            Ask(string symbol) { return SymbolInfoDouble(symbol, SYMBOL_ASK); }
   double            Bid(string symbol) { return SymbolInfoDouble(symbol, SYMBOL_BID); }

   string            NextComment(string prefix)
     {
      m_counter++;
      return StringFormat("mql5bot-%s-%d", prefix, m_counter);
     }

   // Minimal SL/TP distance enforced by the broker (0 when unrestricted)
   double            MinStopDist(string symbol)
     {
      long level = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
      if(level <= 0)
         return 0.0;
      return level * SymbolInfoDouble(symbol, SYMBOL_POINT) +
             (Ask(symbol) - Bid(symbol));
     }

   // true when a deal with our magic AND exact comment landed recently
   bool              FindRecentDeal(ulong magic, string comment, int secondsBack)
     {
      datetime now  = TimeCurrent();
      datetime from = now - secondsBack;
      if(!HistorySelect(from, now + 5))
         return false;
      int total = HistoryDealsTotal();
      for(int i = total - 1; i >= 0; i--)
        {
         ulong deal = HistoryDealGetTicket(i);
         if(deal == 0)
            continue;
         if(HistoryDealGetInteger(deal, DEAL_MAGIC) == magic &&
            HistoryDealGetInteger(deal, DEAL_TIME)  >= from &&
            HistoryDealGetString(deal, DEAL_COMMENT) == comment)
            return true;
        }
      return false;
     }

   // Send one market request; fills prices/stops from distances.
   uint              SendMarketRequest(string symbol, ENUM_POSITION_TYPE dir,
                                      double lots, double slDist, double tpDist,
                                      string comment, MqlTradeResult &res)
     {
      MqlTradeRequest req;
      ZeroMemory(req);
      req.action   = TRADE_ACTION_DEAL;
      req.symbol   = symbol;
      req.magic    = m_magic;
      req.volume   = lots;
      req.deviation = m_deviation;
      req.comment  = comment;
      req.type     = (dir == POSITION_TYPE_LONG) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      req.price    = (dir == POSITION_TYPE_LONG) ? Ask(symbol) : Bid(symbol);

      double minDist = MinStopDist(symbol);
      if(slDist > 0.0)
         slDist = MathMax(slDist, minDist);
      if(tpDist > 0.0)
         tpDist = MathMax(tpDist, minDist);
      if(dir == POSITION_TYPE_LONG)
        {
         if(slDist > 0.0) req.sl = req.price - slDist;
         if(tpDist > 0.0) req.tp = req.price + tpDist;
        }
      else
        {
         if(slDist > 0.0) req.sl = req.price + slDist;
         if(tpDist > 0.0) req.tp = req.price - tpDist;
        }

      req.type_filling = ORDER_FILLING_FOK;
      if(!OrderSend(req, res))
         return res.retcode;
      if(res.retcode == TRADE_RETCODE_INVALID_FILL)
        {
         // broker refused FOK — fall back to IOC
         req.type_filling = ORDER_FILLING_IOC;
         if(!OrderSend(req, res))
            return res.retcode;
        }
      return res.retcode;
     }

public:
                     CTradeManager() :
                        m_magic(0), m_deviation(30), m_maxRetries(3),
                        m_retryDelayMs(150), m_pendingMode(false),
                        m_pendingExpireBars(6), m_pendingTicket(0),
                        m_pendingBarsLeft(0), m_counter(0) {}

   void              Init(ulong magic, int deviation, int maxRetries,
                         int retryDelayMs, bool pendingMode, int pendingExpireBars)
     {
      m_magic             = magic;
      m_deviation         = deviation;
      m_maxRetries        = MathMax(0, maxRetries);
      m_retryDelayMs      = MathMax(0, retryDelayMs);
      m_pendingMode       = pendingMode;
      m_pendingExpireBars = MathMax(1, pendingExpireBars);
      m_pendingTicket     = 0;
     }

   bool              IsPendingMode() const { return m_pendingMode; }
   bool              HasPendingOrder() const { return m_pendingTicket != 0; }

   //-----------------------------------------------------------------
   // Market entry with retries
   //-----------------------------------------------------------------
   bool              SendMarket(string symbol, ENUM_POSITION_TYPE dir,
                               double lots, double slDist, double tpDist,
                               string prefix)
     {
      if(lots <= 0.0)
         return false;
      string comment = NextComment(prefix);
      MqlTradeResult res;
      ZeroMemory(res);

      for(int attempt = 0; attempt <= m_maxRetries; attempt++)
        {
         uint retcode = SendMarketRequest(symbol, dir, lots, slDist, tpDist,
                                          comment, res);
         if(retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_PLACED ||
            retcode == TRADE_RETCODE_DONE_PARTIAL)
            return true;

         if(retcode == TRADE_RETCODE_TIMEOUT || retcode == TRADE_RETCODE_RETRY)
           {
            // ambiguous: never blindly duplicate — verify first
            if(FindRecentDeal(m_magic, comment, 30))
               return true;
           }
         if(!IsRetryableRetcode(retcode))
            {
            PrintFormat("[mql5bot] market order failed: %s (%u)",
                        RetcodeToString(retcode), retcode);
            return false;
           }
         Sleep(m_retryDelayMs);
        }
      // exhausted retries — last resort history check
      return FindRecentDeal(m_magic, comment, 30);
     }

   //-----------------------------------------------------------------
   // Pending stop entry (price = market +/- offset, stops relative)
   //-----------------------------------------------------------------
   bool              SendPending(string symbol, ENUM_POSITION_TYPE dir,
                                double lots, double offsetPoints,
                                double slDist, double tpDist,
                                string prefix)
     {
      if(lots <= 0.0)
         return false;
      string comment = NextComment(prefix);
      MqlTradeResult res;
      ZeroMemory(res);

      for(int attempt = 0; attempt <= m_maxRetries; attempt++)
        {
         MqlTradeRequest req;
         ZeroMemory(req);
         req.action     = TRADE_ACTION_PENDING;
         req.symbol     = symbol;
         req.magic      = m_magic;
         req.volume     = lots;
         req.deviation  = m_deviation;
         req.comment    = comment;
         req.type_time  = ORDER_TIME_GTC;
         req.type       = (dir == POSITION_TYPE_LONG)
                              ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP;
         double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
         if(dir == POSITION_TYPE_LONG)
           {
            double offset = MathMax(offsetPoints * point,
                                    (Ask(symbol) - Bid(symbol)) + point);
            req.price = Ask(symbol) + offset;
           }
         else
           {
            double offset = MathMax(offsetPoints * point,
                                    (Ask(symbol) - Bid(symbol)) + point);
            req.price = Bid(symbol) - offset;
           }
         double minDist = MinStopDist(symbol);
         if(slDist > 0.0) slDist = MathMax(slDist, minDist);
         if(tpDist > 0.0) tpDist = MathMax(tpDist, minDist);
         if(dir == POSITION_TYPE_LONG)
           {
            if(slDist > 0.0) req.sl = req.price - slDist;
            if(tpDist > 0.0) req.tp = req.price + tpDist;
           }
         else
           {
            if(slDist > 0.0) req.sl = req.price + slDist;
            if(tpDist > 0.0) req.tp = req.price - tpDist;
           }

         if(OrderSend(req, res) &&
            (res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_PLACED))
           {
            m_pendingTicket  = res.order;
            m_pendingBarsLeft = m_pendingExpireBars;
            return true;
           }
         if(!IsRetryableRetcode(res.retcode))
           {
            PrintFormat("[mql5bot] pending order failed: %s (%u)",
                        RetcodeToString(res.retcode), res.retcode);
            return false;
           }
         Sleep(m_retryDelayMs);
        }
      return false;
     }

   //-----------------------------------------------------------------
   // Called on every new bar: expires stale pending orders and detects
   // fills. Returns true when the pending slot was released (filled or
   // cancelled) so the EA may consider a fresh entry.
   //-----------------------------------------------------------------
   bool              OnBar(string symbol)
     {
      if(m_pendingTicket == 0)
         return false;
      // still pending?
      bool stillThere = false;
      for(int i = OrdersTotal() - 1; i >= 0; i--)
        {
         ulong t = OrderGetTicket(i);
         if(t == m_pendingTicket)
           {
            stillThere = true;
            break;
           }
        }
      if(!stillThere)
        {
         // gone — either filled (a position should now exist) or rejected
         m_pendingTicket = 0;
         m_pendingBarsLeft = 0;
         return true;
        }
      m_pendingBarsLeft--;
      if(m_pendingBarsLeft <= 0)
        {
         if(CancelPending(symbol))
           {
            m_pendingTicket = 0;
            return true;
           }
        }
      return false;
     }

   bool              CancelPending(string symbol)
     {
      if(m_pendingTicket == 0)
         return false;
      MqlTradeRequest req;
      ZeroMemory(req);
      req.action = TRADE_ACTION_REMOVE;
      req.order  = m_pendingTicket;
      MqlTradeResult res;
      ZeroMemory(res);
      if(OrderSend(req, res) && res.retcode == TRADE_RETCODE_DONE)
         return true;
      PrintFormat("[mql5bot] cancel pending failed: %s (%u)",
                  RetcodeToString(res.retcode), res.retcode);
      return false;
     }

   //-----------------------------------------------------------------
   // Close a position (volume<=0 means the whole position)
   //-----------------------------------------------------------------
   bool              ClosePosition(string symbol, ulong ticket, double volume)
     {
      if(!PositionSelectByTicket(ticket))
         return false;
      double vol = (volume > 0.0) ? volume :
                   PositionGetDouble(POSITION_VOLUME);
      ENUM_POSITION_TYPE dir = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

      MqlTradeResult res;
      ZeroMemory(res);
      for(int attempt = 0; attempt <= m_maxRetries; attempt++)
        {
         MqlTradeRequest req;
         ZeroMemory(req);
         req.action     = TRADE_ACTION_DEAL;
         req.symbol     = symbol;
         req.magic      = m_magic;
         req.position   = ticket;
         req.volume     = vol;
         req.deviation  = m_deviation;
         req.comment    = StringFormat("mql5bot-close-%d", m_counter++);
         req.type       = (dir == POSITION_TYPE_LONG)
                              ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         req.price      = (dir == POSITION_TYPE_LONG) ? Bid(symbol) : Ask(symbol);
         if(OrderSend(req, res) &&
            (res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_PLACED ||
             res.retcode == TRADE_RETCODE_DONE_PARTIAL))
            return true;
         if(!IsRetryableRetcode(res.retcode))
           {
            PrintFormat("[mql5bot] close failed: %s (%u)",
                        RetcodeToString(res.retcode), res.retcode);
            return false;
           }
         Sleep(m_retryDelayMs);
        }
      // closed meanwhile?
      return !PositionSelectByTicket(ticket);
     }

   //-----------------------------------------------------------------
   // Modify SL/TP of an existing position (pass current values through)
   //-----------------------------------------------------------------
   bool              ModifySLTP(string symbol, ulong ticket, double sl, double tp)
     {
      if(!PositionSelectByTicket(ticket))
         return false;
      MqlTradeResult res;
      ZeroMemory(res);
      for(int attempt = 0; attempt <= m_maxRetries; attempt++)
        {
         MqlTradeRequest req;
         ZeroMemory(req);
         req.action   = TRADE_ACTION_SLTP;
         req.symbol   = symbol;
         req.magic    = m_magic;
         req.position = ticket;
         req.sl       = sl;
         req.tp       = tp;
         if(OrderSend(req, res) && res.retcode == TRADE_RETCODE_DONE)
            return true;
         if(!IsRetryableRetcode(res.retcode))
           {
            if(res.retcode != TRADE_RETCODE_INVALID_STOPS &&
               res.retcode != TRADE_RETCODE_NO_CHANGES)
               PrintFormat("[mql5bot] SLTP modify failed: %s (%u)",
                           RetcodeToString(res.retcode), res.retcode);
            return false;
           }
         Sleep(m_retryDelayMs);
        }
      return false;
     }
  };

#endif // MQL5BOT_TRADEMANAGER_MQH
//+------------------------------------------------------------------+
