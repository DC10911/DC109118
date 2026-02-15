//+------------------------------------------------------------------+
//|                                              TradingViewBot.mq5  |
//|                        TradingView Webhook Signal Receiver        |
//|                                                                    |
//| This EA polls the webhook server for signals from TradingView     |
//| and executes trades automatically on MT5.                          |
//|                                                                    |
//| Setup:                                                             |
//| 1. Copy this file to: MT5 Data Folder/MQL5/Experts/               |
//| 2. Compile it in MetaEditor                                        |
//| 3. Attach to any chart                                             |
//| 4. Set the ServerURL and WebhookSecret inputs                      |
//| 5. Enable "Allow WebRequest" in MT5 Tools -> Options -> Expert     |
//|    Advisors and add your server URL                                 |
//+------------------------------------------------------------------+

#property copyright "TradingView-MT5 Bot"
#property version   "2.00"
#property strict

//--- Input parameters
input string   ServerURL      = "https://my-trading-bot.onrender.com"; // Webhook server URL
input string   WebhookSecret  = "";                                     // Webhook secret key
input int      PollInterval   = 3;                                      // Poll interval (seconds)
input int      MaxOpenTrades  = 5;                                      // Max open trades allowed
input double   MaxLotSize     = 1.0;                                    // Maximum lot size
input int      Slippage       = 10;                                     // Max slippage in points
input int      MagicNumber    = 123456;                                 // Magic number for EA trades

//--- Global variables
datetime lastPollTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("TradingView Bot EA initialized");
   Print("Server: ", ServerURL);
   Print("Poll interval: ", PollInterval, " seconds");
   Print("Max open trades: ", MaxOpenTrades);

   // Verify WebRequest is allowed
   string testUrl = ServerURL + "/";
   char   postData[];
   char   resultData[];
   string resultHeaders;
   int    timeout = 5000;

   int res = WebRequest("GET", testUrl, "", "", timeout, postData, 0, resultData, resultHeaders);
   if(res == -1)
   {
      int err = GetLastError();
      if(err == 4014)
      {
         Alert("WebRequest not allowed! Go to Tools -> Options -> Expert Advisors -> ",
               "Enable 'Allow WebRequest for listed URL' and add: ", ServerURL);
         return INIT_FAILED;
      }
      Print("Warning: Could not reach server. Error: ", err, ". Will keep trying...");
   }
   else
   {
      Print("Server connection OK");
   }

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                    |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("TradingView Bot EA stopped. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                                |
//+------------------------------------------------------------------+
void OnTick()
{
   // Only poll at the specified interval
   if(TimeCurrent() - lastPollTime < PollInterval)
      return;

   lastPollTime = TimeCurrent();
   PollForSignal();
}

//+------------------------------------------------------------------+
//| Poll server for new signals                                        |
//+------------------------------------------------------------------+
void PollForSignal()
{
   string url = ServerURL + "/signal";
   if(WebhookSecret != "")
      url = url + "?secret=" + WebhookSecret;

   char   postData[];
   char   resultData[];
   string resultHeaders;
   int    timeout = 5000;

   int res = WebRequest("GET", url, "", "", timeout, postData, 0, resultData, resultHeaders);

   if(res == -1)
   {
      // Network error - silently retry next tick
      return;
   }

   if(res != 200)
      return;

   string response = CharArrayToString(resultData);

   // Parse has_signal
   if(StringFind(response, "\"has_signal\": true") == -1 &&
      StringFind(response, "\"has_signal\":true") == -1)
      return;

   // We have a signal - parse it
   string action   = ParseJsonString(response, "action");
   string symbol   = ParseJsonString(response, "symbol");
   double lotSize  = ParseJsonDouble(response, "lot_size");
   double slPips   = ParseJsonDouble(response, "sl_pips");
   double tpPips   = ParseJsonDouble(response, "tp_pips");

   Print("Signal received: ", action, " ", symbol, " lot:", lotSize, " SL:", slPips, " TP:", tpPips);

   // Execute the signal
   bool success = false;
   string message = "";

   if(action == "buy")
   {
      success = ExecuteBuy(symbol, lotSize, slPips, tpPips, message);
   }
   else if(action == "sell")
   {
      success = ExecuteSell(symbol, lotSize, slPips, tpPips, message);
   }
   else if(action == "close")
   {
      success = CloseSymbol(symbol, message);
   }
   else if(action == "close_all")
   {
      success = CloseAll(message);
   }
   else
   {
      message = "Unknown action: " + action;
   }

   // Report back to server
   ConfirmSignal(success, message);
}

//+------------------------------------------------------------------+
//| Execute BUY order                                                  |
//+------------------------------------------------------------------+
bool ExecuteBuy(string symbol, double lotSize, double slPips, double tpPips, string &message)
{
   // Check max open trades
   if(CountOpenTrades() >= MaxOpenTrades)
   {
      message = "Max open trades reached (" + IntegerToString(MaxOpenTrades) + ")";
      Print(message);
      return false;
   }

   // Enforce max lot size
   if(lotSize > MaxLotSize) lotSize = MaxLotSize;

   // Get symbol info
   if(!SymbolSelect(symbol, true))
   {
      message = "Symbol not found: " + symbol;
      Print(message);
      return false;
   }

   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);

   // Calculate pip value
   double pipValue = GetPipValue(symbol, point, digits);

   // Calculate SL and TP prices
   double sl = 0, tp = 0;
   if(slPips > 0) sl = NormalizeDouble(ask - slPips * pipValue, digits);
   if(tpPips > 0) tp = NormalizeDouble(ask + tpPips * pipValue, digits);

   // Send order
   MqlTradeRequest tradeReq;
   MqlTradeResult  tradeRes;
   ZeroMemory(tradeReq);
   ZeroMemory(tradeRes);

   tradeReq.action    = TRADE_ACTION_DEAL;
   tradeReq.symbol    = symbol;
   tradeReq.volume    = lotSize;
   tradeReq.type      = ORDER_TYPE_BUY;
   tradeReq.price     = ask;
   tradeReq.sl        = sl;
   tradeReq.tp        = tp;
   tradeReq.deviation = Slippage;
   tradeReq.magic     = MagicNumber;
   tradeReq.comment   = "TV-Bot BUY";

   if(!OrderSend(tradeReq, tradeRes))
   {
      message = "BUY failed: " + IntegerToString(tradeRes.retcode) + " " + tradeRes.comment;
      Print(message);
      return false;
   }

   if(tradeRes.retcode == TRADE_RETCODE_DONE || tradeRes.retcode == TRADE_RETCODE_PLACED)
   {
      message = "BUY " + DoubleToString(lotSize, 2) + " " + symbol +
                " @ " + DoubleToString(ask, digits) +
                " SL:" + DoubleToString(sl, digits) +
                " TP:" + DoubleToString(tp, digits);
      Print(message);
      return true;
   }

   message = "BUY retcode: " + IntegerToString(tradeRes.retcode) + " " + tradeRes.comment;
   Print(message);
   return false;
}

//+------------------------------------------------------------------+
//| Execute SELL order                                                 |
//+------------------------------------------------------------------+
bool ExecuteSell(string symbol, double lotSize, double slPips, double tpPips, string &message)
{
   // Check max open trades
   if(CountOpenTrades() >= MaxOpenTrades)
   {
      message = "Max open trades reached (" + IntegerToString(MaxOpenTrades) + ")";
      Print(message);
      return false;
   }

   // Enforce max lot size
   if(lotSize > MaxLotSize) lotSize = MaxLotSize;

   // Get symbol info
   if(!SymbolSelect(symbol, true))
   {
      message = "Symbol not found: " + symbol;
      Print(message);
      return false;
   }

   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);

   // Calculate pip value
   double pipValue = GetPipValue(symbol, point, digits);

   // Calculate SL and TP prices
   double sl = 0, tp = 0;
   if(slPips > 0) sl = NormalizeDouble(bid + slPips * pipValue, digits);
   if(tpPips > 0) tp = NormalizeDouble(bid - tpPips * pipValue, digits);

   // Send order
   MqlTradeRequest tradeReq;
   MqlTradeResult  tradeRes;
   ZeroMemory(tradeReq);
   ZeroMemory(tradeRes);

   tradeReq.action    = TRADE_ACTION_DEAL;
   tradeReq.symbol    = symbol;
   tradeReq.volume    = lotSize;
   tradeReq.type      = ORDER_TYPE_SELL;
   tradeReq.price     = bid;
   tradeReq.sl        = sl;
   tradeReq.tp        = tp;
   tradeReq.deviation = Slippage;
   tradeReq.magic     = MagicNumber;
   tradeReq.comment   = "TV-Bot SELL";

   if(!OrderSend(tradeReq, tradeRes))
   {
      message = "SELL failed: " + IntegerToString(tradeRes.retcode) + " " + tradeRes.comment;
      Print(message);
      return false;
   }

   if(tradeRes.retcode == TRADE_RETCODE_DONE || tradeRes.retcode == TRADE_RETCODE_PLACED)
   {
      message = "SELL " + DoubleToString(lotSize, 2) + " " + symbol +
                " @ " + DoubleToString(bid, digits) +
                " SL:" + DoubleToString(sl, digits) +
                " TP:" + DoubleToString(tp, digits);
      Print(message);
      return true;
   }

   message = "SELL retcode: " + IntegerToString(tradeRes.retcode) + " " + tradeRes.comment;
   Print(message);
   return false;
}

//+------------------------------------------------------------------+
//| Close all positions for a symbol                                   |
//+------------------------------------------------------------------+
bool CloseSymbol(string symbol, string &message)
{
   int closed = 0;
   int total = PositionsTotal();

   for(int i = total - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(PositionGetString(POSITION_SYMBOL) == symbol)
      {
         if(ClosePosition(ticket))
            closed++;
      }
   }

   message = "Closed " + IntegerToString(closed) + " positions for " + symbol;
   Print(message);
   return (closed > 0);
}

//+------------------------------------------------------------------+
//| Close ALL open positions                                           |
//+------------------------------------------------------------------+
bool CloseAll(string &message)
{
   int closed = 0;
   int total = PositionsTotal();

   for(int i = total - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(ClosePosition(ticket))
         closed++;
   }

   message = "Closed all: " + IntegerToString(closed) + " positions";
   Print(message);
   return true;
}

//+------------------------------------------------------------------+
//| Close a single position by ticket                                  |
//+------------------------------------------------------------------+
bool ClosePosition(ulong ticket)
{
   MqlTradeRequest tradeReq;
   MqlTradeResult  tradeRes;
   ZeroMemory(tradeReq);
   ZeroMemory(tradeRes);

   if(!PositionSelectByTicket(ticket))
      return false;

   string symbol = PositionGetString(POSITION_SYMBOL);
   double volume = PositionGetDouble(POSITION_VOLUME);
   ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   tradeReq.action    = TRADE_ACTION_DEAL;
   tradeReq.symbol    = symbol;
   tradeReq.volume    = volume;
   tradeReq.deviation = Slippage;
   tradeReq.position  = ticket;

   if(posType == POSITION_TYPE_BUY)
   {
      tradeReq.type  = ORDER_TYPE_SELL;
      tradeReq.price = SymbolInfoDouble(symbol, SYMBOL_BID);
   }
   else
   {
      tradeReq.type  = ORDER_TYPE_BUY;
      tradeReq.price = SymbolInfoDouble(symbol, SYMBOL_ASK);
   }

   if(!OrderSend(tradeReq, tradeRes))
   {
      Print("Close position failed. Ticket: ", ticket, " Error: ", tradeRes.retcode);
      return false;
   }

   return (tradeRes.retcode == TRADE_RETCODE_DONE);
}

//+------------------------------------------------------------------+
//| Confirm signal execution to server                                 |
//+------------------------------------------------------------------+
void ConfirmSignal(bool success, string message)
{
   string url = ServerURL + "/signal/done";

   // Build JSON body
   string resultStr = success ? "success" : "error";
   // Escape quotes in message
   StringReplace(message, "\"", "'");
   string body = "{\"secret\":\"" + WebhookSecret + "\","
                 "\"result\":\"" + resultStr + "\","
                 "\"message\":\"" + message + "\"}";

   char   postData[];
   char   resultData[];
   string resultHeaders;
   int    timeout = 5000;

   StringToCharArray(body, postData, 0, WHOLE_ARRAY, CP_UTF8);
   // Remove null terminator
   ArrayResize(postData, ArraySize(postData) - 1);

   string headers = "Content-Type: application/json\r\n";

   int res = WebRequest("POST", url, headers, "", timeout, postData, ArraySize(postData), resultData, resultHeaders);

   if(res == -1)
   {
      Print("Failed to confirm signal to server. Will retry.");
   }
   else
   {
      Print("Signal confirmed to server: ", resultStr);
   }
}

//+------------------------------------------------------------------+
//| Count currently open trades (by this EA)                           |
//+------------------------------------------------------------------+
int CountOpenTrades()
{
   int count = 0;
   int total = PositionsTotal();

   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      // Count all positions (or filter by magic number)
      if(PositionGetInteger(POSITION_MAGIC) == MagicNumber || MagicNumber == 0)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Get pip value for a symbol                                         |
//+------------------------------------------------------------------+
double GetPipValue(string symbol, double point, int digits)
{
   // For 5/3 digit brokers: 1 pip = 10 points
   // For 4/2 digit brokers: 1 pip = 1 point
   // Special: JPY pairs (2/3 digits), Gold (2 digits)

   if(digits == 5 || digits == 3)
      return point * 10;
   else if(digits == 2 || digits == 4)
      return point;
   else
      return point * 10; // Default: assume 5-digit
}

//+------------------------------------------------------------------+
//| Parse a string value from JSON                                     |
//+------------------------------------------------------------------+
string ParseJsonString(string json, string key)
{
   string search = "\"" + key + "\"";
   int pos = StringFind(json, search);
   if(pos == -1) return "";

   // Find the colon after the key
   pos = StringFind(json, ":", pos + StringLen(search));
   if(pos == -1) return "";

   // Find opening quote
   int start = StringFind(json, "\"", pos + 1);
   if(start == -1) return "";
   start++; // Move past the quote

   // Find closing quote
   int end = StringFind(json, "\"", start);
   if(end == -1) return "";

   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Parse a double value from JSON                                     |
//+------------------------------------------------------------------+
double ParseJsonDouble(string json, string key)
{
   string search = "\"" + key + "\"";
   int pos = StringFind(json, search);
   if(pos == -1) return 0;

   // Find the colon after the key
   pos = StringFind(json, ":", pos + StringLen(search));
   if(pos == -1) return 0;

   // Skip whitespace
   pos++;
   while(pos < StringLen(json) && StringGetCharacter(json, pos) == ' ')
      pos++;

   // Read the number
   string numStr = "";
   while(pos < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, pos);
      if((ch >= '0' && ch <= '9') || ch == '.' || ch == '-')
         numStr += ShortToString(ch);
      else
         break;
      pos++;
   }

   return StringToDouble(numStr);
}
//+------------------------------------------------------------------+
