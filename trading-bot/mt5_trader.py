"""
MT5 Trade Execution Module via MetaApi Cloud.

MetaApi provides cloud access to MT5 accounts - no local MT5 terminal needed.
This allows the bot to run entirely on a cloud server (works from phone).
"""

import logging
from metaapi_cloud_sdk import MetaApi
from config import Config

logger = logging.getLogger(__name__)


class MT5Trader:
    def __init__(self):
        self.api = None
        self.account = None
        self.connection = None
        self.connected = False

    async def connect(self):
        """Connect to MT5 account via MetaApi."""
        try:
            self.api = MetaApi(Config.METAAPI_TOKEN)
            self.account = await self.api.metatrader_account_api.get_account(
                Config.METAAPI_ACCOUNT_ID
            )

            if self.account.state != "DEPLOYED":
                logger.info("Deploying MT5 account...")
                await self.account.deploy()

            logger.info("Waiting for MT5 API server connection...")
            await self.account.wait_connected()

            self.connection = self.account.get_rpc_connection()
            await self.connection.connect()
            await self.connection.wait_synchronized()

            self.connected = True
            logger.info("Successfully connected to MT5 account via MetaApi")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MT5: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from MT5 account."""
        try:
            if self.connection:
                await self.connection.close()
            self.connected = False
            logger.info("Disconnected from MT5")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

    async def get_account_info(self):
        """Get MT5 account information."""
        if not self.connected:
            await self.connect()
        try:
            info = await self.connection.get_account_information()
            return {
                "balance": info.get("balance"),
                "equity": info.get("equity"),
                "margin": info.get("margin"),
                "free_margin": info.get("freeMargin"),
                "leverage": info.get("leverage"),
                "currency": info.get("currency"),
            }
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return None

    async def get_open_positions(self):
        """Get all open positions."""
        if not self.connected:
            await self.connect()
        try:
            positions = await self.connection.get_positions()
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    async def open_trade(self, symbol, action, lot_size, sl_pips=None, tp_pips=None):
        """
        Open a new trade on MT5.

        Args:
            symbol: Trading pair (e.g., "EURUSD", "XAUUSD")
            action: "buy" or "sell"
            lot_size: Trade volume
            sl_pips: Stop loss in pips (optional)
            tp_pips: Take profit in pips (optional)

        Returns:
            Trade result dict or None on failure
        """
        if not self.connected:
            await self.connect()

        # Enforce max lot size
        lot_size = min(lot_size, Config.MAX_LOT_SIZE)

        # Check max open trades
        positions = await self.get_open_positions()
        if len(positions) >= Config.MAX_OPEN_TRADES:
            logger.warning(
                f"Max open trades ({Config.MAX_OPEN_TRADES}) reached. "
                f"Rejecting new trade."
            )
            return {
                "success": False,
                "error": f"Max open trades limit ({Config.MAX_OPEN_TRADES}) reached",
            }

        try:
            # Get current price for SL/TP calculation
            price = await self.connection.get_symbol_price(symbol)
            if not price:
                return {"success": False, "error": f"Cannot get price for {symbol}"}

            ask = price.get("ask")
            bid = price.get("bid")

            # Get symbol specification for pip calculation
            spec = await self.connection.get_symbol_specification(symbol)
            digits = spec.get("digits", 5)
            pip_size = 0.01 if digits == 3 or digits == 2 else 0.0001
            # Special handling for JPY pairs and gold
            if "JPY" in symbol:
                pip_size = 0.01
            elif symbol in ("XAUUSD", "GOLD"):
                pip_size = 0.1

            sl_pips = sl_pips or Config.DEFAULT_SL_PIPS
            tp_pips = tp_pips or Config.DEFAULT_TP_PIPS

            trade_params = {
                "symbol": symbol,
                "volume": lot_size,
            }

            if action.lower() == "buy":
                trade_params["actionType"] = "ORDER_TYPE_BUY"
                if sl_pips:
                    trade_params["stopLoss"] = round(bid - sl_pips * pip_size, digits)
                if tp_pips:
                    trade_params["takeProfit"] = round(
                        ask + tp_pips * pip_size, digits
                    )
            elif action.lower() == "sell":
                trade_params["actionType"] = "ORDER_TYPE_SELL"
                if sl_pips:
                    trade_params["stopLoss"] = round(ask + sl_pips * pip_size, digits)
                if tp_pips:
                    trade_params["takeProfit"] = round(
                        bid - tp_pips * pip_size, digits
                    )
            else:
                return {"success": False, "error": f"Invalid action: {action}"}

            result = await self.connection.create_market_buy_order(
                symbol, lot_size, trade_params.get("stopLoss"),
                trade_params.get("takeProfit")
            ) if action.lower() == "buy" else await self.connection.create_market_sell_order(
                symbol, lot_size, trade_params.get("stopLoss"),
                trade_params.get("takeProfit")
            )

            logger.info(
                f"Trade opened: {action.upper()} {lot_size} {symbol} | "
                f"SL: {trade_params.get('stopLoss')} | "
                f"TP: {trade_params.get('takeProfit')}"
            )

            return {
                "success": True,
                "action": action.upper(),
                "symbol": symbol,
                "lot_size": lot_size,
                "sl": trade_params.get("stopLoss"),
                "tp": trade_params.get("takeProfit"),
                "result": str(result),
            }

        except Exception as e:
            logger.error(f"Failed to open trade: {e}")
            return {"success": False, "error": str(e)}

    async def close_trade(self, symbol=None, position_id=None):
        """
        Close a trade by symbol or position ID.

        Args:
            symbol: Close all positions for this symbol
            position_id: Close specific position by ID

        Returns:
            Result dict
        """
        if not self.connected:
            await self.connect()

        try:
            positions = await self.get_open_positions()
            closed = []

            for pos in positions:
                should_close = False
                if position_id and str(pos.get("id")) == str(position_id):
                    should_close = True
                elif symbol and pos.get("symbol") == symbol:
                    should_close = True

                if should_close:
                    result = await self.connection.close_position(pos.get("id"))
                    closed.append(
                        {
                            "id": pos.get("id"),
                            "symbol": pos.get("symbol"),
                            "result": str(result),
                        }
                    )
                    logger.info(f"Closed position: {pos.get('id')} {pos.get('symbol')}")

            if not closed:
                return {
                    "success": False,
                    "error": "No matching positions found to close",
                }

            return {"success": True, "closed_positions": closed}

        except Exception as e:
            logger.error(f"Failed to close trade: {e}")
            return {"success": False, "error": str(e)}

    async def close_all(self):
        """Close all open positions."""
        if not self.connected:
            await self.connect()

        try:
            positions = await self.get_open_positions()
            closed = []

            for pos in positions:
                result = await self.connection.close_position(pos.get("id"))
                closed.append(
                    {
                        "id": pos.get("id"),
                        "symbol": pos.get("symbol"),
                        "result": str(result),
                    }
                )
                logger.info(f"Closed position: {pos.get('id')} {pos.get('symbol')}")

            return {"success": True, "closed_count": len(closed), "closed": closed}

        except Exception as e:
            logger.error(f"Failed to close all trades: {e}")
            return {"success": False, "error": str(e)}
