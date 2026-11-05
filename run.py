#!/usr/bin/env python3
"""Entry point for running the Buda Secret Santa Discord Bot."""

import sys
import logging
from src.config import DISCORD_TOKEN
from src.bot import create_bot

logger = logging.getLogger("secretsanta.main")


def main():
    if not DISCORD_TOKEN or DISCORD_TOKEN.strip() in ("", "your_bot_token_here"):
        print("\n" + "=" * 60)
        print("❌ ERROR: DISCORD_TOKEN is missing or empty in .env!")
        print("Please copy .env.example to .env and fill in your Discord Bot Token:")
        print("  cp .env.example .env")
        print("  nano .env")
        print("=" * 60 + "\n")
        sys.exit(1)

    bot = create_bot()
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot process interrupted by user. Shutting down gracefully...")
    except Exception as e:
        logger.critical("Fatal error running bot: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
