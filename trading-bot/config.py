import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Webhook security
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

    # Risk management defaults
    DEFAULT_LOT_SIZE = float(os.getenv("DEFAULT_LOT_SIZE", "0.01"))
    MAX_LOT_SIZE = float(os.getenv("MAX_LOT_SIZE", "1.0"))
    MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "5"))
    DEFAULT_SL_PIPS = float(os.getenv("DEFAULT_SL_PIPS", "50"))
    DEFAULT_TP_PIPS = float(os.getenv("DEFAULT_TP_PIPS", "100"))

    # Server
    PORT = int(os.getenv("PORT", "5000"))
