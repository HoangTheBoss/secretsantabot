"""Bot client initialization, setup hook, and lifecycle management."""

import discord
from discord.ext import commands
import logging
from typing import Optional

from src.config import (
    GUILD_ID,
    DATABASE_PATH,
    LOG_LEVEL,
    HTTP_SERVER_ENABLED,
    HTTP_HOST,
    HTTP_PORT,
    ASSETS_DIR,
    EVENT_NAME,
    get_base_url,
)
from src.database.db import init_db
from src.database.repo import SantaRepository
from src.cogs.admin_cog import AdminCog
from src.cogs.user_cog import UserCog
from src.cogs.reminder_cog import ReminderCog
from src.services.asset_server import AssetServer
from src.ui.views import RegistrationView


logger = logging.getLogger("secretsanta.bot")


class SecretSantaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!santa ",
            intents=intents,
            help_command=None,
        )
        self.repo = SantaRepository(DATABASE_PATH)
        self.asset_server: Optional[AssetServer] = None

    async def setup_hook(self):
        """Called once during bot startup before connecting to Discord Gateway."""
        logger.info("Running setup_hook...")

        # Start built-in asset server for hosting branding assets
        if HTTP_SERVER_ENABLED:
            self.asset_server = AssetServer(
                host=HTTP_HOST,
                port=HTTP_PORT,
                assets_dir=ASSETS_DIR,
                event_name=EVENT_NAME,
                public_url=get_base_url(),
            )
            await self.asset_server.start()

        # Initialize SQLite schema
        await init_db(DATABASE_PATH)

        # Register cogs
        await self.add_cog(AdminCog(self, self.repo))
        await self.add_cog(UserCog(self, self.repo))
        await self.add_cog(ReminderCog(self, self.repo))


        # Re-attach persistent views for active session if one exists
        if GUILD_ID:
            active_session = await self.repo.get_active_session(GUILD_ID)
            if active_session:
                logger.info("Re-attaching persistent view for active session %s", active_session["id"])
                self.add_view(RegistrationView(self.repo, active_session["id"]))

        # Sync application commands
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d slash commands to Guild ID: %d", len(synced), GUILD_ID)
        else:
            synced = await self.tree.sync()
            logger.info("Synced %d global slash commands", len(synced))

    async def on_ready(self):
        logger.info("=" * 50)
        logger.info("🎅 Buda Secret Santa Bot is logged in as: %s (ID: %s)", self.user, self.user.id if self.user else "Unknown")
        logger.info("Connected to %d guild(s)", len(self.guilds))
        logger.info("=" * 50)

    async def close(self):
        """Clean up background services before closing the bot client."""
        if self.asset_server:
            await self.asset_server.stop()
        await super().close()


def create_bot() -> SecretSantaBot:
    """Factory function for bot instance."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return SecretSantaBot()
