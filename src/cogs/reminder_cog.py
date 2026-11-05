"""Cog managing routine background reminders and on-demand reminder commands."""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging
from typing import Optional
from datetime import datetime, timezone

from src.database.repo import SantaRepository
from src.ui.embeds import (
    build_public_reminder_embed,
    build_dm_reminder_embed,
    build_milestone_reminder_embed,
)

from src.ui.views import SantaDmView
from src.services.draw_service import execute_draw
from src.config import (

    ROUTINE_REMINDERS_ENABLED,
    ROUTINE_REMINDER_HOURS,
    SANTA_ADMIN_ROLE_ID,
)

logger = logging.getLogger("secretsanta.reminder_cog")


DEADLINE_MILESTONES = [
    ("72h", 72 * 3600, "⏰ 3 Days Left to Sign Up for Secret Santa!", discord.Color.blue()),
    ("48h", 48 * 3600, "⏰ 48 Hours Remaining: Secret Santa Signups Closing Soon!", discord.Color.gold()),
    ("24h", 24 * 3600, "🚨 Final 24 Hours! Automatic Draw Takes Place Tomorrow!", discord.Color.orange()),
    ("12h", 12 * 3600, "⚡ 12 Hours Left! Don't Miss Out on Secret Santa!", discord.Color.orange()),
    ("6h", 6 * 3600, "🔥 6 Hours Remaining: Registration Closing Today!", discord.Color.red()),
    ("2h", 2 * 3600, "🚨 Urgent: 2 Hours Left! Last Call Before the Draw!", discord.Color.red()),
    ("1h", 1 * 3600, "⚡ Last Chance: 1 Hour Remaining Until the Secret Draw!", discord.Color.dark_red()),
]


def is_admin():

    """Admin check matching admin_cog."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        if interaction.user.guild_permissions.administrator:
            return True
        if interaction.guild.owner_id == interaction.user.id:
            return True
        if SANTA_ADMIN_ROLE_ID and isinstance(interaction.user, discord.Member):
            role_ids = [r.id for r in interaction.user.roles]
            if SANTA_ADMIN_ROLE_ID in role_ids:
                return True
        await interaction.response.send_message(
            "🚫 You do not have permission to manage Secret Santa reminders.", ephemeral=True
        )
        return False

    return app_commands.check(predicate)


class ReminderCog(commands.Cog):
    def __init__(self, bot: commands.Bot, repo: SantaRepository):
        self.bot = bot
        self.repo = repo

        if ROUTINE_REMINDERS_ENABLED:
            logger.info("Starting routine reminder loop (every %s hours)...", ROUTINE_REMINDER_HOURS)
            self.routine_reminder_loop.change_interval(hours=ROUTINE_REMINDER_HOURS)
            self.routine_reminder_loop.start()

        # Start auto-draw deadline checker
        self.auto_draw_checker_loop.start()

    def cog_unload(self):
        if self.routine_reminder_loop.is_running():
            self.routine_reminder_loop.cancel()
        if self.auto_draw_checker_loop.is_running():
            self.auto_draw_checker_loop.cancel()

    @tasks.loop(seconds=30)
    async def auto_draw_checker_loop(self):
        """Checks if any active session has reached its signup_deadline for auto-draw or escalating reminders."""
        await self.bot.wait_until_ready()
        now_epoch = int(datetime.now(timezone.utc).timestamp())

        # 1. Check for due auto-draw sessions
        due_sessions = await self.repo.get_due_auto_draw_sessions(now_epoch)
        for session in due_sessions:
            session_id = session["id"]
            logger.info("Session %s reached signup deadline. Executing auto-draw...", session_id)
            success, message, failed_dms = await execute_draw(
                bot=self.bot,
                repo=self.repo,
                session_id=session_id,
                trigger_type="AUTOMATIC",
            )
            if not success:
                channel_id = session.get("channel_id")
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    await channel.send(
                        f"⚠️ **Automatic Draw Postponed:** {message}\n"
                        "Registration will remain open. An admin can use `/secretsanta set_deadline` to set a new deadline or `/secretsanta draw` when ready."
                    )
                # Disable auto_draw to prevent re-triggering repeatedly
                await self.repo.update_session_details(session_id, auto_draw=False)

        # 2. Check for escalating countdown reminders before deadline
        active_sessions = await self.repo.get_all_active_sessions()
        for session in active_sessions:
            if session.get("status") != "REGISTRATION":
                continue

            deadline_epoch = session.get("signup_deadline_epoch")
            if not deadline_epoch:
                continue

            time_left = deadline_epoch - now_epoch
            if time_left <= 0:
                continue  # Handled above

            triggered = set(session.get("triggered_milestones", "").split(",")) if session.get("triggered_milestones") else set()

            for key, threshold_sec, title, color in DEADLINE_MILESTONES:
                if time_left <= threshold_sec and key not in triggered:
                    channel_id = session.get("channel_id")
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        try:
                            channel = await self.bot.fetch_channel(channel_id)
                        except Exception:
                            channel = None

                    if channel and isinstance(channel, discord.TextChannel):
                        participants = await self.repo.get_all_participants(session["id"])
                        embed = build_milestone_reminder_embed(session, participants, title, color)
                        await channel.send(embed=embed)
                        logger.info("Sent escalating milestone reminder (%s) to #%s", key, channel.name)

                    await self.repo.add_session_milestone(session["id"], key)
                    triggered.add(key)
                    break



    @tasks.loop(hours=24)
    async def routine_reminder_loop(self):
        """Periodic background task that posts routine channel updates and nudges unwrapped Santas."""
        await self.bot.wait_until_ready()
        logger.info("Executing routine reminder background task...")

        sessions = await self.repo.get_all_active_sessions()
        for session in sessions:
            try:
                await self._process_session_routine_update(session)
            except Exception as e:
                logger.error("Error running routine reminder for session %s: %s", session.get("id"), e)

    async def _process_session_routine_update(self, session: dict):
        session_id = session["id"]
        channel_id = session["channel_id"]
        status = session.get("status")

        # 1. Public Channel Update
        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                channel = None

        participants = await self.repo.get_all_participants(session_id)
        if channel and isinstance(channel, discord.TextChannel):
            embed = build_public_reminder_embed(session, participants)
            await channel.send(embed=embed)
            await self.repo.update_session_reminded(session_id)
            logger.info("Sent routine public channel reminder to #%s", channel.name)

        # 2. Private DM Nudges (only when IN_PROGRESS)
        if status == "IN_PROGRESS":
            unwrapped = await self.repo.get_unwrapped_pairings(session_id)
            for p in unwrapped:
                santa_id = p["santa_id"]
                try:
                    santa_user = await self.bot.fetch_user(santa_id)
                    dm_embed = build_dm_reminder_embed(
                        baby_name=p["baby_name"],
                        gift_tag_code=p["gift_tag_code"],
                        party_date=session.get("party_date"),
                        party_venue=session.get("party_venue"),
                    )
                    view = SantaDmView(repo=self.repo, session_id=session_id, baby_id=p["baby_id"])
                    await santa_user.send(embed=dm_embed, view=view)
                    await self.repo.update_pairing_reminded(session_id, santa_id)
                    logger.info("Sent routine DM reminder to Santa %s", santa_id)
                except discord.Forbidden:
                    logger.warning("Could not send routine DM to user %s (DMs closed)", santa_id)
                except Exception as e:
                    logger.error("Failed to deliver routine DM to %s: %s", santa_id, e)

    # =========================================================================
    # Slash Commands for Manual / On-Demand Reminders
    # =========================================================================

    group = app_commands.Group(name="remind", description="Send routine and manual Secret Santa reminders")

    @group.command(name="channel", description="Immediately post a public reminder & countdown in the Santa channel.")
    @is_admin()
    @app_commands.describe(custom_note="Optional custom announcement message from the host")
    async def remind_channel(
        self,
        interaction: discord.Interaction,
        custom_note: Optional[str] = None,
    ):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        participants = await self.repo.get_all_participants(session["id"])
        embed = build_public_reminder_embed(session, participants, custom_note=custom_note)

        # Post to session channel
        target_channel = self.bot.get_channel(session["channel_id"]) or interaction.channel
        if isinstance(target_channel, discord.TextChannel):
            await target_channel.send(embed=embed)
            await self.repo.update_session_reminded(session["id"])
            await interaction.response.send_message(
                f"✅ **Public reminder posted in {target_channel.mention}!**", ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Could not find the bound text channel.", ephemeral=True)

    @group.command(name="dms", description="Send a gentle reminder DM to all Santas who haven't marked gifts as wrapped.")
    @is_admin()
    @app_commands.describe(custom_note="Optional custom note from the host to include in the DM")
    async def remind_dms(
        self,
        interaction: discord.Interaction,
        custom_note: Optional[str] = None,
    ):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        if session.get("status") != "IN_PROGRESS":
            await interaction.response.send_message(
                "⚠️ Pairings have not been drawn yet! Use `/remind channel` to remind people to register.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        session_id = session["id"]
        unwrapped = await self.repo.get_unwrapped_pairings(session_id)

        if not unwrapped:
            await interaction.followup.send(
                "🎉 **All Santas have already marked their gifts as wrapped!** No DM reminders needed."
            )
            return

        sent_count = 0
        failed_names: list[str] = []

        for p in unwrapped:
            santa_id = p["santa_id"]
            try:
                santa_user = await self.bot.fetch_user(santa_id)
                dm_embed = build_dm_reminder_embed(
                    baby_name=p["baby_name"],
                    gift_tag_code=p["gift_tag_code"],
                    party_date=session.get("party_date"),
                    party_venue=session.get("party_venue"),
                    custom_note=custom_note,
                )
                view = SantaDmView(repo=self.repo, session_id=session_id, baby_id=p["baby_id"])
                await santa_user.send(embed=dm_embed, view=view)
                await self.repo.update_pairing_reminded(session_id, santa_id)
                sent_count += 1
            except Exception as e:
                logger.error("Failed to deliver reminder DM to %s: %s", santa_id, e)
                failed_names.append(p.get("santa_name", str(santa_id)))

        msg = f"✅ **Sent private reminder DMs to {sent_count} unwrapped Santa(s).**"
        if failed_names:
            msg += f"\n⚠️ Could not deliver DMs to: {', '.join(failed_names)} (DMs closed)."

        await interaction.followup.send(msg)

    @group.command(name="user", description="Send a gentle private reminder DM to a specific Santa.")
    @is_admin()
    @app_commands.describe(
        member="The Santa participant to nudge",
        custom_note="Optional custom note from the host",
    )
    async def remind_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        custom_note: Optional[str] = None,
    ):
        session = await self.repo.get_active_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        pairing = await self.repo.get_pairing_for_santa(session["id"], member.id)
        if not pairing:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} is not an assigned Santa in this event.", ephemeral=True
            )
            return

        try:
            dm_embed = build_dm_reminder_embed(
                baby_name=pairing["baby_display_name"],
                gift_tag_code=pairing["gift_tag_code"],
                party_date=session.get("party_date"),
                party_venue=session.get("party_venue"),
                custom_note=custom_note,
            )
            view = SantaDmView(repo=self.repo, session_id=session["id"], baby_id=pairing["baby_id"])
            await member.send(embed=dm_embed, view=view)
            await self.repo.update_pairing_reminded(session["id"], member.id)
            await interaction.response.send_message(
                f"✅ **Reminder DM sent to {member.mention}!**", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Could not send DM to {member.mention} (their DMs are closed).", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error sending DM to {member.mention}: {e}", ephemeral=True
            )
