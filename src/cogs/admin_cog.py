"""Administrative Slash commands for managing Secret Santa."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional

from src.database.repo import SantaRepository
from src.services.matcher import generate_pairings, MatchingError
from src.services.draw_service import execute_draw
from src.utils.time_parser import parse_deadline, format_discord_timestamp
from src.ui.embeds import (

    build_registration_embed,
    build_santa_dm_embed,
    build_prep_dashboard_embed,
    build_admin_export_embed,
)
from src.ui.views import RegistrationView, SantaDmView, PollView
from src.config import SANTA_CHANNEL_ID, SANTA_ADMIN_ROLE_ID

logger = logging.getLogger("secretsanta.admin_cog")


def is_admin():
    """Check if the user is a server admin or holds the configured SANTA_ADMIN_ROLE_ID."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        # Server administrators or owner
        if interaction.user.guild_permissions.administrator:
            return True
        if interaction.guild.owner_id == interaction.user.id:
            return True
        # Check specific role
        if SANTA_ADMIN_ROLE_ID and isinstance(interaction.user, discord.Member):
            role_ids = [r.id for r in interaction.user.roles]
            if SANTA_ADMIN_ROLE_ID in role_ids:
                return True
        await interaction.response.send_message(
            "🚫 You do not have permission to manage Secret Santa.", ephemeral=True
        )
        return False

    return app_commands.check(predicate)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot, repo: SantaRepository):
        self.bot = bot
        self.repo = repo

    group = app_commands.Group(name="secretsanta", description="Secret Santa event management")

    @group.command(name="setup", description="Open interactive modal to configure or update Secret Santa settings.")
    @is_admin()
    async def setup_event(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        channel_id = interaction.channel_id
        if not guild_id or not channel_id:
            return

        # Check existing active session
        existing = await self.repo.get_active_session(guild_id)
        if existing:
            session_id = existing["id"]
        else:
            session_id = await self.repo.create_session(
                guild_id=guild_id,
                channel_id=channel_id,
            )
            existing = await self.repo.get_session_by_id(session_id)

        from src.ui.modals import SetupModal

        modal = SetupModal(
            repo=self.repo,
            session_id=session_id,
            channel_id=existing.get("channel_id") or channel_id,
            existing_budget=existing.get("budget") or "",
            existing_party_date=existing.get("party_date") or "",
            existing_party_venue=existing.get("party_venue") or "",
            existing_deadline=existing.get("signup_deadline") or "",
        )
        await interaction.response.send_modal(modal)

    @group.command(name="reset", description="Cancel or wipe the active Secret Santa session to start fresh.")
    @is_admin()
    async def reset_event(self, interaction: discord.Interaction):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found to reset.", ephemeral=True)
            return

        class ConfirmResetView(discord.ui.View):
            def __init__(self, repo: SantaRepository, session_id: int):
                super().__init__(timeout=60)
                self.repo = repo
                self.session_id = session_id

            @discord.ui.button(label="Confirm Reset ⚠️", style=discord.ButtonStyle.danger)
            async def confirm(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                await self.repo.archive_or_cancel_session(self.session_id, status="CANCELLED")
                await btn_interaction.response.send_message(
                    "🗑️ **Secret Santa event has been cancelled.** You can now run `/secretsanta setup` to start fresh.",
                    ephemeral=True,
                )

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                await btn_interaction.response.send_message("Action cancelled.", ephemeral=True)

        await interaction.response.send_message(
            "⚠️ **Are you sure you want to cancel the active Secret Santa session?**\n"
            "This will archive the current event, cancel any pending auto-draws, and allow you to configure a fresh event.",
            view=ConfirmResetView(self.repo, session["id"]),
            ephemeral=True,
        )



    @group.command(name="poll", description="Post an interactive voting poll in the channel.")
    @is_admin()
    @app_commands.describe(
        question="The question to ask (e.g. Budget limit? or Party Date?)",
        options="Comma-separated options (e.g. '$20, $30, $40' or 'Dec 20, Dec 21')",
    )
    async def run_poll(
        self,
        interaction: discord.Interaction,
        question: str,
        options: str,
    ):
        opts = [o.strip() for o in options.split(",") if o.strip()]
        if len(opts) < 2:
            await interaction.response.send_message(
                "⚠️ Please provide at least 2 comma-separated options.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📊 Vote: {question}",
            description="Click a button below to cast or change your vote!",
            color=discord.Color.blue(),
        )
        for i, opt in enumerate(opts[:5]):
            embed.add_field(name=f"Option {i + 1}", value=f"**{opt}**", inline=True)

        view = PollView(question=question, options=opts)
        await interaction.response.send_message(embed=embed, view=view)

    @group.command(name="set_details", description="Update budget, date, or venue for the active session.")
    @is_admin()
    @app_commands.describe(
        budget="Budget limit (e.g. $30)",
        party_date="Party Date & Time (e.g. Dec 22, 19:00)",
        party_venue="Venue name or address",
    )
    async def set_details(
        self,
        interaction: discord.Interaction,
        budget: Optional[str] = None,
        party_date: Optional[str] = None,
        party_venue: Optional[str] = None,
    ):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        await self.repo.update_session_details(
            session_id=session["id"],
            budget=budget,
            party_date=party_date,
            party_venue=party_venue,
        )
        await interaction.response.send_message(
            f"✅ **Event details updated!**\n"
            f"• Budget: `{budget or session.get('budget', 'Unset')}`\n"
            f"• Date: `{party_date or session.get('party_date', 'Unset')}`\n"
            f"• Venue: `{party_venue or session.get('party_venue', 'Unset')}`",
            ephemeral=True,
        )

    @group.command(name="set_deadline", description="Set or change the sign-up deadline and automatic draw schedule.")
    @is_admin()
    @app_commands.describe(
        deadline="Deadline string (e.g. '3d', '7 days', '2026-12-10 20:00')",
        auto_draw="Automatically execute the draw when the deadline arrives",
    )
    async def set_deadline(
        self,
        interaction: discord.Interaction,
        deadline: str,
        auto_draw: bool = True,
    ):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        if session.get("status") != "REGISTRATION":
            await interaction.response.send_message("⚠️ Sign-ups are already closed for this event.", ephemeral=True)
            return

        try:
            _, epoch, formatted = parse_deadline(deadline)
        except ValueError as e:
            await interaction.response.send_message(f"⚠️ {e}", ephemeral=True)
            return

        await self.repo.update_session_details(
            session_id=session["id"],
            signup_deadline=formatted,
            signup_deadline_epoch=epoch,
            auto_draw=auto_draw,
        )

        auto_note = (
            "• **Auto-Draw:** Enabled 🤖 (pairs will be drawn automatically on time!)"
            if auto_draw
            else "• **Auto-Draw:** Disabled (manual `/secretsanta draw` required)"
        )
        await interaction.response.send_message(
            f"✅ **Sign-up deadline updated!**\n"
            f"• **Deadline:** {format_discord_timestamp(epoch)}\n"
            f"{auto_note}",
            ephemeral=True,
        )


    @group.command(name="exclude", description="Prevent two participants from drawing each other (e.g. couples).")
    @is_admin()
    @app_commands.describe(
        user_a="First participant",
        user_b="Second participant",
    )
    async def add_exclusion(
        self,
        interaction: discord.Interaction,
        user_a: discord.Member,
        user_b: discord.Member,
    ):
        if user_a.id == user_b.id:
            await interaction.response.send_message("❌ Cannot exclude a user from themselves.", ephemeral=True)
            return

        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        await self.repo.add_exclusion(session["id"], user_a.id, user_b.id)
        await interaction.response.send_message(
            f"✅ **Exclusion added:** {user_a.mention} and {user_b.mention} will not be paired together.",
            ephemeral=True,
        )

    @group.command(name="unexclude", description="Remove an existing exclusion between two participants.")
    @is_admin()
    @app_commands.describe(
        user_a="First participant",
        user_b="Second participant",
    )
    async def remove_exclusion(
        self,
        interaction: discord.Interaction,
        user_a: discord.Member,
        user_b: discord.Member,
    ):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        removed = await self.repo.remove_exclusion(session["id"], user_a.id, user_b.id)
        if removed:
            await interaction.response.send_message(
                f"✅ **Exclusion removed** between {user_a.mention} and {user_b.mention}.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "ℹ️ No active exclusion was found between these users.", ephemeral=True
            )

    @group.command(name="list_exclusions", description="List all configured exclusion rules.")
    @is_admin()
    async def list_exclusions(self, interaction: discord.Interaction):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        exclusions = await self.repo.get_exclusions(session["id"])
        if not exclusions:
            await interaction.response.send_message("ℹ️ No exclusions are currently configured.", ephemeral=True)
            return

        lines = []
        guild = interaction.guild
        for a_id, b_id in exclusions:
            m_a = guild.get_member(a_id) if guild else None
            m_b = guild.get_member(b_id) if guild else None
            name_a = m_a.display_name if m_a else f"User {a_id}"
            name_b = m_b.display_name if m_b else f"User {b_id}"
            lines.append(f"• **{name_a}** ⛔ **{name_b}**")

        embed = discord.Embed(
            title="🚫 Configured Exclusion Rules",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @group.command(name="draw", description="Close signups, compute secret pairings, and dispatch DMs to Santas.")
    @is_admin()
    async def run_draw(self, interaction: discord.Interaction):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active session found.", ephemeral=True)
            return

        session_id = session["id"]
        participants = await self.repo.get_all_participants(session_id)
        if len(participants) < 3:
            await interaction.response.send_message(
                f"⚠️ Need at least 3 participants to draw pairs (currently have {len(participants)}).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=False)

        success, message, failed_dms = await execute_draw(
            bot=self.bot,
            repo=self.repo,
            session_id=session_id,
            trigger_type="MANUAL",
        )

        if not success:
            await interaction.followup.send(f"❌ {message}")
        else:
            await interaction.followup.send("🎉 **Draw completed and dispatched!** Pairings sent via DM.")


    @group.command(name="dashboard", description="Display the spoiler-free gift preparation progress meter.")
    async def show_dashboard(self, interaction: discord.Interaction):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        participants = await self.repo.get_all_participants(session["id"])
        embed = build_prep_dashboard_embed(session, participants)
        await interaction.response.send_message(embed=embed)

    @group.command(name="admin_export", description="Privately export master pairing cheat sheet for the organizer.")
    @is_admin()
    async def admin_export(self, interaction: discord.Interaction):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        pairings = await self.repo.get_all_pairings(session["id"])
        embed = build_admin_export_embed(pairings)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @group.command(name="resend", description="Privately resend assignment DM to a participant.")
    @is_admin()
    @app_commands.describe(member="The Santa participant to resend to")
    async def resend_assignment(self, interaction: discord.Interaction, member: discord.Member):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active session found.", ephemeral=True)
            return

        pairing = await self.repo.get_pairing_for_santa(session["id"], member.id)
        if not pairing:
            await interaction.response.send_message(
                f"ℹ️ No pairing found for {member.mention}.", ephemeral=True
            )
            return

        try:
            client = interaction.client
            baby_user = await client.fetch_user(pairing["baby_id"])
            avatar_url = baby_user.display_avatar.url if baby_user else None

            embed = build_santa_dm_embed(
                baby_name=pairing["baby_display_name"],
                baby_username=pairing["baby_username"],
                avatar_url=avatar_url,
                wishlist=pairing["baby_wishlist"],
                dislikes=pairing["baby_dislikes"],
                offline_notes=pairing["baby_offline_notes"],
                gift_tag_code=pairing["gift_tag_code"],
                budget=session.get("budget"),
                party_date=session.get("party_date"),
                party_venue=session.get("party_venue"),
            )
            view = SantaDmView(repo=self.repo, session_id=session["id"], baby_id=pairing["baby_id"])
            await member.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ **Assignment resent to {member.mention} successfully.**", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to send DM to {member.mention}: {e}", ephemeral=True
            )
