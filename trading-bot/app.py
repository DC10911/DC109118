"""
TradingView → MT5 Trading Bot

Receives webhook alerts from TradingView indicators and executes
trades on MT5 via MetaApi cloud. Designed to run entirely on a
cloud server so you can manage everything from your phone.

Supported TradingView alert JSON formats:

1. Open a trade:
   {
     "secret": "your_webhook_secret",
     "action": "buy" | "sell",
     "symbol": "EURUSD",
     "lot_size": 0.01,
     "sl_pips": 50,
     "tp_pips": 100
   }

2. Close trades for a symbol:
   {
     "secret": "your_webhook_secret",
     "action": "close",
     "symbol": "EURUSD"
   }

3. Close all trades:
   {
     "secret": "your_webhook_secret",
     "action": "close_all"
   }
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from config import Config
from mt5_trader import MT5Trader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
trader = MT5Trader()

# Trade log stored in memory (last 100 trades)
trade_log = []
MAX_LOG_SIZE = 100


def log_trade(action, data, result):
    """Log trade to in-memory history."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "data": data,
        "result": result,
    }
    trade_log.append(entry)
    if len(trade_log) > MAX_LOG_SIZE:
        trade_log.pop(0)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.route("/", methods=["GET"])
def home():
    """Health check and status page."""
    return jsonify(
        {
            "status": "running",
            "bot": "TradingView-MT5 Bot",
            "version": "1.0.0",
            "message": "Bot is active. Send POST to /webhook with TradingView alerts.",
            "endpoints": {
                "webhook": "POST /webhook - Receive TradingView alerts",
                "status": "GET /status - Account info and open positions",
                "trades": "GET /trades - Recent trade history",
                "health": "GET / - This page",
            },
        }
    )


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Receive and process TradingView webhook alerts.

    TradingView sends a POST request with JSON body when an alert fires.
    The bot validates the secret, parses the signal, and executes the trade.
    """
    try:
        # Parse request data
        if request.content_type and "json" in request.content_type:
            data = request.get_json(silent=True)
        else:
            # TradingView sometimes sends as plain text
            raw = request.get_data(as_text=True)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {raw[:200]}")
                return jsonify({"error": "Invalid JSON"}), 400

        if not data:
            return jsonify({"error": "No data received"}), 400

        logger.info(f"Webhook received: {json.dumps(data)}")

        # Validate webhook secret
        if Config.WEBHOOK_SECRET:
            received_secret = data.get("secret", "")
            if received_secret != Config.WEBHOOK_SECRET:
                logger.warning("Invalid webhook secret received")
                return jsonify({"error": "Unauthorized"}), 401

        action = data.get("action", "").lower()
        symbol = data.get("symbol", "").upper()
        lot_size = float(data.get("lot_size", Config.DEFAULT_LOT_SIZE))
        sl_pips = data.get("sl_pips")
        tp_pips = data.get("tp_pips")

        if sl_pips is not None:
            sl_pips = float(sl_pips)
        if tp_pips is not None:
            tp_pips = float(tp_pips)

        # Execute action
        if action in ("buy", "sell"):
            if not symbol:
                return jsonify({"error": "Symbol is required for buy/sell"}), 400

            result = run_async(
                trader.open_trade(symbol, action, lot_size, sl_pips, tp_pips)
            )
            log_trade(action, data, result)
            return jsonify(result), 200 if result.get("success") else 400

        elif action == "close":
            if not symbol:
                return jsonify({"error": "Symbol is required for close"}), 400

            position_id = data.get("position_id")
            result = run_async(trader.close_trade(symbol=symbol, position_id=position_id))
            log_trade(action, data, result)
            return jsonify(result), 200 if result.get("success") else 400

        elif action == "close_all":
            result = run_async(trader.close_all())
            log_trade(action, data, result)
            return jsonify(result), 200 if result.get("success") else 400

        else:
            return (
                jsonify(
                    {
                        "error": f"Unknown action: {action}",
                        "supported_actions": ["buy", "sell", "close", "close_all"],
                    }
                ),
                400,
            )

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/status", methods=["GET"])
def status():
    """Get account status and open positions."""
    try:
        account_info = run_async(trader.get_account_info())
        positions = run_async(trader.get_open_positions())

        position_list = []
        for pos in (positions or []):
            position_list.append(
                {
                    "id": pos.get("id"),
                    "symbol": pos.get("symbol"),
                    "type": pos.get("type"),
                    "volume": pos.get("volume"),
                    "open_price": pos.get("openPrice"),
                    "current_price": pos.get("currentPrice"),
                    "profit": pos.get("profit"),
                    "sl": pos.get("stopLoss"),
                    "tp": pos.get("takeProfit"),
                }
            )

        return jsonify(
            {
                "account": account_info,
                "open_positions": position_list,
                "positions_count": len(position_list),
            }
        )
    except Exception as e:
        logger.error(f"Status error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/trades", methods=["GET"])
def trades():
    """Get recent trade history."""
    return jsonify({"trades": trade_log, "total": len(trade_log)})


if __name__ == "__main__":
    logger.info("Starting TradingView-MT5 Trading Bot...")
    logger.info(f"Webhook secret configured: {'Yes' if Config.WEBHOOK_SECRET else 'No'}")
    logger.info(f"Default lot size: {Config.DEFAULT_LOT_SIZE}")
    logger.info(f"Max open trades: {Config.MAX_OPEN_TRADES}")
    app.run(host="0.0.0.0", port=Config.PORT, debug=False)
