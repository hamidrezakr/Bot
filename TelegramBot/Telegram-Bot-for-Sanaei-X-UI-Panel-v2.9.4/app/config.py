import os
from dotenv import load_dotenv

# بارگذاری فایل .env
load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]

# Panel X-UI
PANEL_URL = os.getenv("PANEL_URL", "")
PANEL_USERNAME = os.getenv("PANEL_USERNAME", "")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "")

# Zarinpal
ZARINPAL_MERCHANT_ID = os.getenv("ZARINPAL_MERCHANT_ID", "")
ZARINPAL_CALLBACK_URL = os.getenv("ZARINPAL_CALLBACK_URL", "")

# Server
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:8000")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8000))
