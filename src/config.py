"""Configuration management using environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from datetime import timezone, timedelta

# Load .env file from project root
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

# Default Timezone (Vietnam / Asia/Ho_Chi_Minh UTC+7)
DEFAULT_TIMEZONE_NAME = os.getenv("DEFAULT_TIMEZONE", "Asia/Ho_Chi_Minh")
try:
    DEFAULT_TIMEZONE = ZoneInfo(DEFAULT_TIMEZONE_NAME)
except Exception:
    DEFAULT_TIMEZONE = timezone(timedelta(hours=7))


# Server & Channel Binding
GUILD_ID_RAW = os.getenv("GUILD_ID", "0")
SANTA_CHANNEL_ID_RAW = os.getenv("SANTA_CHANNEL_ID", "0")
SANTA_ADMIN_ROLE_ID_RAW = os.getenv("SANTA_ADMIN_ROLE_ID", "0")

try:
    GUILD_ID = int(GUILD_ID_RAW)
except ValueError:
    GUILD_ID = 0

try:
    SANTA_CHANNEL_ID = int(SANTA_CHANNEL_ID_RAW)
except ValueError:
    SANTA_CHANNEL_ID = 0

try:
    SANTA_ADMIN_ROLE_ID = int(SANTA_ADMIN_ROLE_ID_RAW)
except ValueError:
    SANTA_ADMIN_ROLE_ID = 0

# Database path
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "secretsanta.db"))

# Ensure directory exists for database
db_parent = Path(DATABASE_PATH).parent
db_parent.mkdir(parents=True, exist_ok=True)

# Routine Reminders
ROUTINE_REMINDERS_ENABLED = os.getenv("ROUTINE_REMINDERS_ENABLED", "true").lower() in ("true", "1", "yes")
try:
    ROUTINE_REMINDER_HOURS = max(1, int(os.getenv("ROUTINE_REMINDER_HOURS", "24")))
except ValueError:
    ROUTINE_REMINDER_HOURS = 24

# Default Branding & Appearance
DEFAULT_EVENT_NAME = os.getenv("DEFAULT_EVENT_NAME", "Buda Secret Santa")
DEFAULT_LOGO_URL = os.getenv("DEFAULT_LOGO_URL", "")
DEFAULT_BANNER_URL = os.getenv("DEFAULT_BANNER_URL", "")
DEFAULT_FOOTER_TEXT = os.getenv("DEFAULT_FOOTER_TEXT", "Buda Secret Santa • Happy Holidays! 🎄")
DEFAULT_THEME_COLOR = os.getenv("DEFAULT_THEME_COLOR", "RED")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

