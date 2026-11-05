"""User-facing Slash commands for Secret Santa participants."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from src.database.repo import SantaRepository
from src.ui.modals import WishlistModal

logger = logging.getLogger("secretsanta.user_cog")


class UserCog(commands.Cog):
    def __init__(self, bot: commands.Bot, repo: SantaRepository):
        self.bot = bot
        self.repo = repo

    @app_commands.command(name="my_status", description="Check your Secret Santa registration and gift preparation status.")
    async def my_status(self, interaction: discord.Interaction):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        participant = await self.repo.get_participant(session["id"], interaction.user.id)
        if not participant:
            await interaction.response.send_message(
                "ℹ️ You are not registered in the current Secret Santa event. "
                "Look for the registration post in the channel and click **[Join Event 🎁]**!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"🎁 Secret Santa Status: {interaction.user.display_name}",
            color=discord.Color.green(),
        )

        embed.add_field(name="Registration", value="✅ Registered", inline=True)
        embed.add_field(name="Gift Prep Status", value=f"`{participant.get('gift_status', 'NOT_STARTED')}`", inline=True)
        embed.add_field(name="DM Verified", value="✅ Yes" if participant.get("dm_verified") else "⚠️ No", inline=True)

        wishlist = participant.get("wishlist") or "*None*"
        dislikes = participant.get("dislikes") or "*None*"
        notes = participant.get("offline_notes") or "*None*"

        embed.add_field(name="Your Wishlist", value=wishlist[:300], inline=False)
        embed.add_field(name="Your Dislikes", value=dislikes[:200], inline=False)
        embed.add_field(name="Your Party Notes", value=notes[:200], inline=False)

        embed.set_footer(text="Click [Edit Wishlist 📝] below or use /update_wishlist to make changes anytime!")
        from src.ui.views import MyStatusView
        view = MyStatusView(repo=self.repo, session_id=session["id"])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    @app_commands.command(name="update_wishlist", description="Open modal to update your Secret Santa wishlist and party notes.")
    async def update_wishlist(self, interaction: discord.Interaction):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        participant = await self.repo.get_participant(session["id"], interaction.user.id)
        if not participant:
            await interaction.response.send_message(
                "ℹ️ You must first join the event via the channel registration embed.",
                ephemeral=True,
            )
            return

        modal = WishlistModal(
            repo=self.repo,
            session_id=session["id"],
            existing_wishlist=participant.get("wishlist", ""),
            existing_dislikes=participant.get("dislikes", ""),
            existing_notes=participant.get("offline_notes", ""),
        )
        await interaction.response.send_modal(modal)
