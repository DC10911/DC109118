"""
TradingView → MT5 Trading Bot (Free Edition)

Receives webhook alerts from TradingView indicators and stores them
as signals. An MQL5 Expert Advisor running on MT5 polls this server
and executes trades directly. No paid API services needed.

Architecture:
  TradingView Alert → POST /webhook → Signal stored
  MT5 EA → GET /signal → Reads & executes → POST /signal/done

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

import logging
import json
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ----- Signal Queue -----
# Signals waiting to be picked up by the MT5 EA.
# Each signal is a dict with: action, symbol, lot_size, sl_pips, tp_pips, timestamp
signal_queue = []
signal_lock = threading.Lock()

# Trade log stored in memory (last 100 entries)
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


# ===================== ENDPOINTS =====================


@app.route("/", methods=["GET"])
def home():
    """Health check and status page."""
    with signal_lock:
        pending = len(signal_queue)
    return jsonify(
        {
            "status": "running",
            "bot": "TradingView-MT5 Bot (Free)",
            "version": "2.0.0",
            "pending_signals": pending,
            "message": "Bot is active. Send POST to /webhook with TradingView alerts.",
            "endpoints": {
                "webhook": "POST /webhook - Receive TradingView alerts",
                "signal": "GET /signal - EA picks up next signal",
                "signal_done": "POST /signal/done - EA confirms execution",
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
    The bot validates the secret, parses the signal, and queues it for
    the MT5 EA to pick up.
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
        else:
            sl_pips = Config.DEFAULT_SL_PIPS

        if tp_pips is not None:
            tp_pips = float(tp_pips)
        else:
            tp_pips = Config.DEFAULT_TP_PIPS

        # Enforce max lot size
        lot_size = min(lot_size, Config.MAX_LOT_SIZE)

        # Validate action
        if action in ("buy", "sell"):
            if not symbol:
                return jsonify({"error": "Symbol is required for buy/sell"}), 400
        elif action == "close":
            if not symbol:
                return jsonify({"error": "Symbol is required for close"}), 400
        elif action == "close_all":
            pass
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

        # Build signal and queue it
        signal = {
            "action": action,
            "symbol": symbol,
            "lot_size": lot_size,
            "sl_pips": sl_pips,
            "tp_pips": tp_pips,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with signal_lock:
            signal_queue.append(signal)

        log_trade(action, data, {"status": "queued"})
        logger.info(f"Signal queued: {action} {symbol} {lot_size}")

        return jsonify({"success": True, "signal": signal}), 200

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/signal", methods=["GET"])
def get_signal():
    """
    EA polls this endpoint to get the next pending signal.

    The EA calls this every few seconds. If there's a signal waiting,
    it returns the signal data. If not, returns empty.

    Query params:
        secret - webhook secret for authentication
    """
    # Authenticate
    if Config.WEBHOOK_SECRET:
        secret = request.args.get("secret", "")
        if secret != Config.WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

    with signal_lock:
        if signal_queue:
            signal = signal_queue[0]  # Peek at first signal
            return jsonify({"has_signal": True, "signal": signal}), 200
        else:
            return jsonify({"has_signal": False}), 200


@app.route("/signal/done", methods=["POST"])
def signal_done():
    """
    EA confirms it has executed the signal.

    After the EA successfully executes a trade, it calls this endpoint
    to remove the signal from the queue so it's not executed again.

    JSON body:
        secret - webhook secret
        result - "success" or "error"
        message - optional details
    """
    try:
        data = request.get_json(silent=True) or {}

        # Authenticate
        if Config.WEBHOOK_SECRET:
            secret = data.get("secret", "")
            if secret != Config.WEBHOOK_SECRET:
                return jsonify({"error": "Unauthorized"}), 401

        result = data.get("result", "unknown")
        message = data.get("message", "")

        with signal_lock:
            if signal_queue:
                completed_signal = signal_queue.pop(0)
                log_trade(
                    completed_signal.get("action"),
                    completed_signal,
                    {"result": result, "message": message},
                )
                logger.info(
                    f"Signal completed: {completed_signal.get('action')} "
                    f"{completed_signal.get('symbol')} - {result}: {message}"
                )
                return jsonify({"success": True, "completed": completed_signal}), 200
            else:
                return jsonify({"success": False, "error": "No signal in queue"}), 400

    except Exception as e:
        logger.error(f"Signal done error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/trades", methods=["GET"])
def trades():
    """Get recent trade history."""
    return jsonify({"trades": trade_log, "total": len(trade_log)})


@app.route("/queue", methods=["GET"])
def queue():
    """View all pending signals in the queue."""
    if Config.WEBHOOK_SECRET:
        secret = request.args.get("secret", "")
        if secret != Config.WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

    with signal_lock:
        return jsonify({"queue": list(signal_queue), "count": len(signal_queue)})


@app.route("/clear", methods=["POST"])
def clear_queue():
    """Clear all pending signals (emergency stop)."""
    data = request.get_json(silent=True) or {}

    if Config.WEBHOOK_SECRET:
        secret = data.get("secret", "")
        if secret != Config.WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

    with signal_lock:
        count = len(signal_queue)
        signal_queue.clear()

    logger.info(f"Queue cleared: {count} signals removed")
    return jsonify({"success": True, "cleared": count})


if __name__ == "__main__":
    logger.info("Starting TradingView-MT5 Trading Bot (Free Edition)...")
    logger.info(f"Webhook secret configured: {'Yes' if Config.WEBHOOK_SECRET else 'No'}")
    logger.info(f"Default lot size: {Config.DEFAULT_LOT_SIZE}")
    logger.info(f"Max lot size: {Config.MAX_LOT_SIZE}")
    app.run(host="0.0.0.0", port=Config.PORT, debug=False)
