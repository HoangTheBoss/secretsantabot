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

# Assets Directory
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Branding & Appearance (Environment / Config-driven)
EVENT_NAME = os.getenv("EVENT_NAME", os.getenv("DEFAULT_EVENT_NAME", "Buda Secret Santa"))
THEME_COLOR = os.getenv("THEME_COLOR", os.getenv("DEFAULT_THEME_COLOR", "RED"))
FOOTER_TEXT = os.getenv("FOOTER_TEXT", os.getenv("DEFAULT_FOOTER_TEXT", "Buda Secret Santa • Happy Holidays! 🎄"))
LOGO_FILENAME = os.getenv("LOGO_FILENAME", "logo.png")
BANNER_FILENAME = os.getenv("BANNER_FILENAME", "banner.png")

# Built-in HTTP Asset Server & Reverse Proxy Configuration
HTTP_SERVER_ENABLED = os.getenv("HTTP_SERVER_ENABLED", "true").lower() in ("true", "1", "yes")
HTTP_HOST = os.getenv("HTTP_HOST", "0.0.0.0")
try:
    HTTP_PORT = int(os.getenv("HTTP_PORT", "8080"))
except ValueError:
    HTTP_PORT = 8080

PUBLIC_HOSTNAME = os.getenv("PUBLIC_HOSTNAME", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip()


def get_base_url() -> str:
    """Resolve the public base URL for static assets (supporting reverse proxy hostnames)."""
    if PUBLIC_URL:
        return PUBLIC_URL.rstrip("/")
    if PUBLIC_HOSTNAME:
        host = PUBLIC_HOSTNAME
        if not host.startswith(("http://", "https://")):
            return f"https://{host}".rstrip("/")
        return host.rstrip("/")
    return f"http://localhost:{HTTP_PORT}"


def resolve_asset_url(filename_or_url: str | None) -> str | None:
    """Resolve asset filename to a full public URL, or keep external URLs as is."""
    if not filename_or_url or not filename_or_url.strip():
        return None
    val = filename_or_url.strip()
    if val.startswith(("http://", "https://")):
        return val
    clean_name = val.lstrip("/")
    return f"{get_base_url()}/assets/{clean_name}"


def get_logo_url() -> str | None:
    """Return public URL for the event logo."""
    return resolve_asset_url(LOGO_FILENAME)


def get_banner_url() -> str | None:
    """Return public URL for the event banner."""
    return resolve_asset_url(BANNER_FILENAME)


# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


