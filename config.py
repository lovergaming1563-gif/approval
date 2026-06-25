import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(id_.strip()) for id_ in os.getenv("ADMIN_IDS", "").split(",") if id_.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot_database.db")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
