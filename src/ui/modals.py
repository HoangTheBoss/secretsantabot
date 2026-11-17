"""Discord UI Modals for collecting wishlists and anonymous relay messages."""

import discord
import logging
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from src.database.repo import SantaRepository

logger = logging.getLogger("secretsanta.modals")


class WishlistModal(discord.ui.Modal, title="Secret Santa: Wishlist & Notes"):
    def __init__(
        self,
        repo: "SantaRepository",
        session_id: int,
        existing_wishlist: str = "",
        existing_dislikes: str = "",
        existing_notes: str = "",
        on_refresh_callback=None,
    ):
        super().__init__()
        self.repo = repo
        self.session_id = session_id
        self.on_refresh_callback = on_refresh_callback

        self.wishlist_input = discord.ui.TextInput(
            label="🎁 Wishlist & Interests",
            style=discord.TextStyle.paragraph,
            placeholder="Links, favorite hobbies, authors, games, clothing sizes...",
            default=existing_wishlist,
            required=True,
            max_length=1000,
        )
        self.add_item(self.wishlist_input)

        self.dislikes_input = discord.ui.TextInput(
            label="🚫 Dislikes & Allergies",
            style=discord.TextStyle.paragraph,
            placeholder="Allergies, things you don't like, items you already own...",
            default=existing_dislikes,
            required=False,
            max_length=500,
        )
        self.add_item(self.dislikes_input)

        self.offline_notes_input = discord.ui.TextInput(
            label="🥂 In-Person Party & Drink Notes",
            style=discord.TextStyle.paragraph,
            placeholder="Favorite beer/wine/cocktail, dietary restrictions, arrival notes...",
            default=existing_notes,
            required=False,
            max_length=500,
        )
        self.add_item(self.offline_notes_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = interaction.user
        wishlist = self.wishlist_input.value.strip()
        dislikes = self.dislikes_input.value.strip()
        offline_notes = self.offline_notes_input.value.strip()

        dm_verified = True
        try:
            await user.send(
                "🎄 **Hi there!** This confirms you are registered for Secret Santa! "
                "We will deliver your secret target assignment here once the draw takes place."
            )
        except discord.Forbidden:
            dm_verified = False
        except Exception as e:
            logger.warning("Could not send confirmation DM to %s: %s", user.id, e)
            dm_verified = False

        await self.repo.add_or_update_participant(
            session_id=self.session_id,
            user_id=user.id,
            username=user.name,
            display_name=user.display_name,
            wishlist=wishlist,
            dislikes=dislikes,
            offline_notes=offline_notes,
            dm_verified=dm_verified,
        )

        if dm_verified:
            resp_msg = (
                "✅ **Your Secret Santa wishlist and preferences have been saved!**\n"
                "You are officially registered for the event. A confirmation message was sent to your DMs."
            )
        else:
            resp_msg = (
                "⚠️ **Your preferences were saved, BUT your DMs are closed!**\n"
                "The bot cannot deliver your secret target assignment because your Discord Privacy Settings block DMs from server members.\n\n"
                "**How to fix:**\n"
                "1. Right-click this server icon (or tap server name on mobile).\n"
                "2. Go to **Privacy Settings**.\n"
                "3. Enable **'Allow direct messages from server members'**."
            )

        await interaction.followup.send(resp_msg, ephemeral=True)

        # Trigger channel embed refresh if callback provided
        if self.on_refresh_callback:
            try:
                await self.on_refresh_callback(interaction)
            except Exception as e:
                logger.error("Failed to execute refresh callback: %s", e)


class AnonymousMessageModal(discord.ui.Modal):
    def __init__(
        self,
        repo: "SantaRepository",
        session_id: int,
        target_user_id: int,
        direction: str,  # 'SANTA_TO_BABY' or 'BABY_TO_SANTA'
        title: str = "Send Anonymous Message",
    ):
        super().__init__(title=title)
        self.repo = repo
        self.session_id = session_id
        self.target_user_id = target_user_id
        self.direction = direction

        self.message_input = discord.ui.TextInput(
            label="Your Message (Delivered Anonymously)",
            style=discord.TextStyle.paragraph,
            placeholder="Type your question or reply here...",
            required=True,
            max_length=1500,
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        from src.ui.embeds import build_relay_embed
        from src.ui.views import BabyReplyView, SantaDmView

        content = self.message_input.value.strip()

        # Log to DB
        if self.direction == "SANTA_TO_BABY":
            santa_id = interaction.user.id
            baby_id = self.target_user_id
        else:
            santa_id = self.target_user_id
            baby_id = interaction.user.id

        await self.repo.log_relay_message(
            session_id=self.session_id,
            santa_id=santa_id,
            baby_id=baby_id,
            direction=self.direction,
            content=content,
        )

        # Fetch recipient
        client = interaction.client
        try:
            target_user = await client.fetch_user(self.target_user_id)
            if self.direction == "SANTA_TO_BABY":
                embed = build_relay_embed("santa", content)
                view = BabyReplyView(repo=self.repo, session_id=self.session_id, santa_id=santa_id)
            else:
                embed = build_relay_embed("baby", content)
                view = SantaDmView(repo=self.repo, session_id=self.session_id, baby_id=baby_id)

            await target_user.send(embed=embed, view=view)
            await interaction.response.send_message(
                "📨 **Your anonymous message has been safely delivered!**",
                ephemeral=True,
            )
        except Exception as e:
            logger.error("Failed to relay message to %s: %s", self.target_user_id, e)
            await interaction.response.send_message(
                "❌ **Could not deliver the message.** The recipient may have DMs closed or blocked the bot.",
                ephemeral=True,
            )


class SetupModal(discord.ui.Modal, title="Secret Santa: Event Settings"):
    """Modal for configuring or updating Secret Santa event parameters."""

    def __init__(
        self,
        repo: "SantaRepository",
        session_id: int,
        channel_id: int,
        existing_budget: str = "",
        existing_party_date: str = "",
        existing_party_venue: str = "",
        existing_deadline: str = "",
    ):
        super().__init__()
        self.repo = repo
        self.session_id = session_id
        self.channel_id = channel_id

        self.budget_input = discord.ui.TextInput(
            label="💰 Budget Ceiling",
            placeholder="e.g. $25 - $35",
            default=existing_budget,
            required=False,
            max_length=100,
        )
        self.add_item(self.budget_input)

        self.party_date_input = discord.ui.TextInput(
            label="📅 Party Date & Time (Vietnam Time)",
            placeholder="e.g. Dec 24, 19:00 or 2026-12-24 19:00",
            default=existing_party_date,
            required=False,
            max_length=100,
        )
        self.add_item(self.party_date_input)

        self.party_venue_input = discord.ui.TextInput(
            label="📍 Party Venue / Location",
            placeholder="e.g. Alice's House / Bistro 42",
            default=existing_party_venue,
            required=False,
            max_length=150,
        )
        self.add_item(self.party_venue_input)

        self.deadline_input = discord.ui.TextInput(
            label="⏰ Sign-Up Deadline (Auto-Draws Pairs)",
            placeholder="e.g. 3d, 7 days, or 2026-12-10 20:00",
            default=existing_deadline,
            required=False,
            max_length=100,
        )
        self.add_item(self.deadline_input)

    async def on_submit(self, interaction: discord.Interaction):
        from src.utils.time_parser import parse_deadline, format_discord_timestamp
        from src.ui.embeds import build_registration_embed
        from src.ui.views import RegistrationView

        budget = self.budget_input.value.strip() or None
        party_date = self.party_date_input.value.strip() or None
        party_venue = self.party_venue_input.value.strip() or None
        deadline_raw = self.deadline_input.value.strip()

        deadline_str = None
        deadline_epoch = None
        if deadline_raw:
            try:
                _, deadline_epoch, deadline_str = parse_deadline(deadline_raw)
            except ValueError as e:
                await interaction.response.send_message(f"⚠️ {e}", ephemeral=True)
                return

        # Update in database
        await self.repo.update_session_details(
            session_id=self.session_id,
            budget=budget,
            party_date=party_date,
            party_venue=party_venue,
            signup_deadline=deadline_str,
            signup_deadline_epoch=deadline_epoch,
            auto_draw=True if deadline_epoch else False,
        )

        session = await self.repo.get_session_by_id(self.session_id)
        participants = await self.repo.get_all_participants(self.session_id)

        embed = build_registration_embed(session or {}, participants)
        view = RegistrationView(repo=self.repo, session_id=self.session_id)
        interaction.client.add_view(view)

        # Check existing channel message
        target_channel = interaction.client.get_channel(self.channel_id)
        if not target_channel:
            try:
                target_channel = await interaction.client.fetch_channel(self.channel_id)
            except Exception:
                target_channel = None

        if not target_channel or not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message(
                "⚠️ Settings saved, but could not find the target text channel.", ephemeral=True
            )
            return

        existing_msg_id = session.get("registration_message_id") if session else None
        updated_existing = False

        if existing_msg_id:
            try:
                existing_msg = await target_channel.fetch_message(existing_msg_id)
                await existing_msg.edit(embed=embed, view=view)
                updated_existing = True
            except Exception:
                logger.info("Could not fetch existing registration message %s, posting fresh message", existing_msg_id)

        if not updated_existing:
            new_msg = await target_channel.send(embed=embed, view=view)
            await self.repo.update_registration_message_id(self.session_id, new_msg.id)
            await self.repo.update_session_status(self.session_id, "REGISTRATION")
            await self.repo.update_session_reminded(self.session_id)
        else:
            await self.repo.update_session_status(self.session_id, "REGISTRATION")

        conf_msg = "✅ **Secret Santa event settings updated!** Channel card refreshed in-place." if updated_existing else "✅ **Secret Santa event initialized!** Registration card posted."
        if deadline_epoch:
            conf_msg += f"\n⏳ **Draw scheduled for:** {format_discord_timestamp(deadline_epoch)}"

        await interaction.response.send_message(conf_msg, ephemeral=True)


class CreatePollModal(discord.ui.Modal, title="Create Secret Santa Poll"):
    """Modal allowing the host to create an interactive reaction voting poll."""

    def __init__(self, target_channel_id: Optional[int] = None):
        super().__init__()
        self.target_channel_id = target_channel_id

        self.question_input = discord.ui.TextInput(
            label="📊 Poll Question",
            placeholder="e.g. Budget ceiling limit? or Which party date works best?",
            required=True,
            max_length=200,
        )
        self.add_item(self.question_input)

        self.options_input = discord.ui.TextInput(
            label="📝 Choices (One per line, 2 to 10 options)",
            style=discord.TextStyle.paragraph,
            placeholder="Option 1\nOption 2\nOption 3\n(e.g.\n$25\n$35\n$50)",
            required=True,
            max_length=1000,
        )
        self.add_item(self.options_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        question = self.question_input.value.strip()
        raw_options = [line.strip() for line in self.options_input.value.split("\n") if line.strip()]

        if len(raw_options) < 2:
            await interaction.followup.send(
                "⚠️ Please provide at least 2 options (one per line).", ephemeral=True
            )
            return

        if len(raw_options) > 10:
            await interaction.followup.send(
                "⚠️ A maximum of 10 options is supported for reaction polling. Please reduce to 10 or fewer.",
                ephemeral=True,
            )
            return

        from src.ui.embeds import build_poll_embed

        embed, emojis = build_poll_embed(question=question, options=raw_options)

        target_channel = (
            interaction.client.get_channel(self.target_channel_id)
            if self.target_channel_id
            else interaction.channel
        )
        if not target_channel and self.target_channel_id:
            try:
                target_channel = await interaction.client.fetch_channel(self.target_channel_id)
            except Exception:
                target_channel = interaction.channel

        if target_channel and isinstance(target_channel, discord.TextChannel):
            poll_msg = await target_channel.send(embed=embed)
            for emoji in emojis:
                try:
                    await poll_msg.add_reaction(emoji)
                except Exception as e:
                    logger.warning("Failed to add reaction %s to poll message: %s", emoji, e)
            await interaction.followup.send(
                f"✅ **Reaction poll posted in {target_channel.mention}!**", ephemeral=True
            )
        else:
            await interaction.followup.send("❌ Could not find target text channel to post poll.", ephemeral=True)


class DeadlineModal(discord.ui.Modal, title="Set Sign-Up Deadline"):
    """Modal allowing the host to set or change the sign-up deadline and auto-draw toggle."""

    def __init__(
        self,
        repo: "SantaRepository",
        session_id: int,
        existing_deadline: str = "",
    ):
        super().__init__()
        self.repo = repo
        self.session_id = session_id

        self.deadline_input = discord.ui.TextInput(
            label="⏰ Sign-Up Deadline (Vietnam Time / ICT)",
            placeholder="e.g. 3d, 7 days, 24h, or 2026-12-10 20:00",
            default=existing_deadline,
            required=False,
            max_length=100,
        )
        self.add_item(self.deadline_input)

        self.auto_draw_input = discord.ui.TextInput(
            label="🤖 Auto-Draw on Time? (yes / no)",
            placeholder="yes (draws pairs on deadline) or no (manual draw)",
            default="yes",
            required=False,
            max_length=10,
        )
        self.add_item(self.auto_draw_input)

    async def on_submit(self, interaction: discord.Interaction):
        from src.utils.time_parser import parse_deadline, format_discord_timestamp
        from src.ui.embeds import build_registration_embed
        from src.ui.views import RegistrationView

        raw = self.deadline_input.value.strip()
        auto_draw_val = self.auto_draw_input.value.strip().lower() not in ("no", "0", "false", "off")

        if not raw:
            # Clear deadline
            await self.repo.update_session_details(
                self.session_id,
                signup_deadline=None,
                signup_deadline_epoch=None,
                auto_draw=False,
            )
            await interaction.response.send_message(
                "✅ **Sign-up deadline cleared.** Auto-draw disabled (use `/secretsanta draw` when ready).",
                ephemeral=True,
            )
        else:
            try:
                _, epoch, formatted = parse_deadline(raw)
            except ValueError as e:
                await interaction.response.send_message(f"⚠️ {e}", ephemeral=True)
                return

            await self.repo.update_session_details(
                self.session_id,
                signup_deadline=formatted,
                signup_deadline_epoch=epoch,
                auto_draw=auto_draw_val,
            )
            auto_note = (
                "• **Auto-Draw:** Enabled 🤖" if auto_draw_val else "• **Auto-Draw:** Disabled (manual `/secretsanta draw`)"
            )
            await interaction.response.send_message(
                f"✅ **Sign-up deadline updated!**\n"
                f"• **Deadline:** {format_discord_timestamp(epoch)}\n"
                f"{auto_note}",
                ephemeral=True,
            )

        # Refresh channel registration card in-place
        session = await self.repo.get_session_by_id(self.session_id)
        if session and session.get("channel_id"):
            ch = interaction.client.get_channel(session["channel_id"])
            msg_id = session.get("registration_message_id")
            if ch and msg_id and isinstance(ch, discord.TextChannel):
                try:
                    msg = await ch.fetch_message(msg_id)
                    parts = await self.repo.get_all_participants(self.session_id)
                    emb = build_registration_embed(session, parts)
                    view = RegistrationView(self.repo, self.session_id)
                    await msg.edit(embed=emb, view=view)
                except Exception:
                    pass


class RemindNoteModal(discord.ui.Modal):
    """Modal for inputting a custom note when sending reminders."""

    def __init__(self, title: str, on_submit_callback):
        super().__init__(title=title)
        self.on_submit_callback = on_submit_callback

        self.note_input = discord.ui.TextInput(
            label="📢 Announcement Note (Optional)",
            style=discord.TextStyle.paragraph,
            placeholder="Type a custom message or leave blank for standard reminder...",
            required=False,
            max_length=500,
        )
        self.add_item(self.note_input)

    async def on_submit(self, interaction: discord.Interaction):
        note = self.note_input.value.strip() or None
        await self.on_submit_callback(interaction, note)


class BulkExclusionModal(discord.ui.Modal, title="Bulk Add Exclusion Rules"):
    """Modal allowing hosts to enter multiple pair or group exclusions at once."""

    def __init__(self, repo: "SantaRepository", session_id: int):
        super().__init__()
        self.repo = repo
        self.session_id = session_id

        self.input_text = discord.ui.TextInput(
            label="Pairs or Groups (One per line)",
            style=discord.TextStyle.paragraph,
            placeholder=(
                "@Alice, @Bob\n"
                "@Charlie, @Dave\n"
                "@Eve, @Frank, @Grace (group: none can pair)"
            ),
            required=True,
            max_length=2000,
        )
        self.add_item(self.input_text)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        from src.utils.exclusion_parser import parse_bulk_exclusions

        participants = await self.repo.get_all_participants(self.session_id)
        raw_text = self.input_text.value.strip()

        valid_pairs, unresolved = parse_bulk_exclusions(
            raw_text=raw_text,
            guild=interaction.guild,
            participants=participants,
        )

        added_count = 0
        if valid_pairs:
            added_count = await self.repo.add_exclusions_bulk(self.session_id, valid_pairs)

        from src.ui.views import ExclusionManageView

        view = ExclusionManageView(self.repo, self.session_id)
        await view.setup_components(interaction.guild)
        embed = await view.build_exclusions_embed(interaction.guild)

        msg = f"✅ **Processed exclusion rules:** Added {added_count} mutual exclusion pair(s)."
        if unresolved:
            msg += f"\n⚠️ **Could not resolve {len(unresolved)} line(s):**\n" + "\n".join(
                f"• `{line}`" for line in unresolved[:5]
            )

        await interaction.followup.send(msg, embed=embed, view=view, ephemeral=True)




