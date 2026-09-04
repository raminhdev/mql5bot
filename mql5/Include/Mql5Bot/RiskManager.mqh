//+------------------------------------------------------------------+
//|                                        Mql5Bot/RiskManager.mqh   |
//|     Position sizing, daily loss limit and drawdown kill-switch   |
//+------------------------------------------------------------------+
#property strict

#ifndef MQL5BOT_RISKMANAGER_MQH
#define MQL5BOT_RISKMANAGER_MQH

#include <Mql5Bot/Config.mqh>

class CRiskManager
  {
private:
   double            m_riskPercent;      // % of equity risked per trade
   double            m_maxLots;
   double            m_dailyLossPct;     // 0 = disabled
   double            m_maxDrawdownPct;   // 0 = disabled
   double            m_maxSpreadPoints;
   double            m_dayStartEquity;
   double            m_peakEquity;
   bool              m_limitsInitialized;
   bool              m_killSwitch;

public:
                     CRiskManager() :
                        m_riskPercent(1.0), m_maxLots(100.0),
                        m_dailyLossPct(0.0), m_maxDrawdownPct(0.0),
                        m_maxSpreadPoints(0.0), m_dayStartEquity(0.0),
                        m_peakEquity(0.0), m_limitsInitialized(false),
                        m_killSwitch(false) {}

   void              Init(double riskPercent, double maxLots,
                         double dailyLossPct, double maxDrawdownPct,
                         double maxSpreadPoints)
     {
      m_riskPercent     = riskPercent;
      m_maxLots         = maxLots;
      m_dailyLossPct    = dailyLossPct;
      m_maxDrawdownPct  = maxDrawdownPct;
      m_maxSpreadPoints = maxSpreadPoints;
      ResetDayAndPeak();
     }

   void              ResetDayAndPeak()
     {
      double equity = AccountInfoDouble(ACCOUNT_EQUITY);
      m_dayStartEquity   = equity;
      m_peakEquity       = equity;
      m_limitsInitialized = true;
      m_killSwitch       = false;
     }

   bool              IsKillSwitch() const { return m_killSwitch; }
   void              TripKillSwitch()     { m_killSwitch = true; }

   // call once per day rollover
   void              OnNewDay()
     {
      m_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
     }

   // Check equity-based limits; returns true when trading must stop.
   // Sets the kill switch permanently when the drawdown limit is hit.
   bool              CheckLimits(bool &dailyHit, bool &drawdownHit)
     {
      dailyHit    = false;
      drawdownHit = false;
      double equity = AccountInfoDouble(ACCOUNT_EQUITY);
      if(m_dailyLossPct > 0.0 &&
         equity <= m_dayStartEquity * (1.0 - m_dailyLossPct / 100.0))
        {
         dailyHit = true;
         return true;
        }
      if(m_maxDrawdownPct > 0.0 &&
         equity <= m_peakEquity * (1.0 - m_maxDrawdownPct / 100.0))
        {
         drawdownHit = true;
         m_killSwitch = true;
         return true;
        }
      if(equity > m_peakEquity)
         m_peakEquity = equity;
      return false;
     }

   // risk-based position sizing from stop distance (in price units)
   double            GetLots(double price, double slPrice, double &outRiskMoney)
     {
      outRiskMoney = 0.0;
      if(m_riskPercent <= 0.0 || slPrice <= 0.0)
         return 0.0;

      double stopDist = MathAbs(price - slPrice);
      if(stopDist <= 0.0)
         return 0.0;

      double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      if(tickSize <= 0.0 || tickValue <= 0.0)
         return 0.0;

      double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
      double riskMoney  = equity * m_riskPercent / 100.0;
      double lossPerLot = stopDist / tickSize * tickValue;
      if(lossPerLot <= 0.0)
         return 0.0;

      double lots = riskMoney / lossPerLot;
      lots = NormalizeLots(lots,
                           SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP),
                           SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
                           MathMin(m_maxLots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX)));
      outRiskMoney = lots * lossPerLot;
      return lots;
     }

   // spread guard: block entries when the spread is too wide
   bool              IsSpreadOK() const
     {
      if(m_maxSpreadPoints <= 0.0)
         return true;
      double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) -
                       SymbolInfoDouble(_Symbol, SYMBOL_BID)) /
                      SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      return spread <= m_maxSpreadPoints;
     }

   double            DailyLossPct()  const { return m_dailyLossPct; }
   double            MaxDrawdownPct() const { return m_maxDrawdownPct; }
   double            RiskPercent()   const { return m_riskPercent; }
  };

#endif // MQL5BOT_RISKMANAGER_MQH
//+------------------------------------------------------------------+
