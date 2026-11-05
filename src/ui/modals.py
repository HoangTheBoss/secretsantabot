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
        user = interaction.user
        wishlist = self.wishlist_input.value.strip()
        dislikes = self.dislikes_input.value.strip()
        offline_notes = self.offline_notes_input.value.strip()

        await self.repo.add_or_update_participant(
            session_id=self.session_id,
            user_id=user.id,
            username=user.name,
            display_name=user.display_name,
            wishlist=wishlist,
            dislikes=dislikes,
            offline_notes=offline_notes,
            dm_verified=True,
        )

        await interaction.response.send_message(
            "✅ **Your Secret Santa wishlist and preferences have been saved!**\n"
            "You are officially registered for the event. You can edit this anytime using the `Update Wishlist` button.",
            ephemeral=True,
        )

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

        conf_msg = "✅ **Secret Santa event settings updated!** Channel card refreshed in-place." if updated_existing else "✅ **Secret Santa event initialized!** Registration card posted."
        if deadline_epoch:
            conf_msg += f"\n⏳ **Draw scheduled for:** {format_discord_timestamp(deadline_epoch)}"

        await interaction.response.send_message(conf_msg, ephemeral=True)


class CreatePollModal(discord.ui.Modal, title="Create Secret Santa Poll"):
    """Modal allowing the host to create an interactive channel poll."""

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
            label="📝 Choices (One per line, 2 to 5 options)",
            style=discord.TextStyle.paragraph,
            placeholder="Option 1\nOption 2\nOption 3\n(e.g.\n$25\n$35\n$50)",
            required=True,
            max_length=500,
        )
        self.add_item(self.options_input)

    async def on_submit(self, interaction: discord.Interaction):
        from src.ui.views import PollView

        question = self.question_input.value.strip()
        raw_options = [line.strip() for line in self.options_input.value.split("\n") if line.strip()]

        if len(raw_options) < 2:
            await interaction.response.send_message(
                "⚠️ Please provide at least 2 options (one per line).", ephemeral=True
            )
            return

        if len(raw_options) > 5:
            await interaction.response.send_message(
                "⚠️ A maximum of 5 options can fit on Discord button rows. Please reduce to 5 or fewer.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"📊 Vote: {question}",
            description="Click a button below to cast or change your vote!",
            color=discord.Color.blue(),
        )
        for i, opt in enumerate(raw_options):
            embed.add_field(name=f"Option {i + 1}", value=f"**{opt}**", inline=True)

        view = PollView(question=question, options=raw_options)

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
            await target_channel.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ **Poll posted in {target_channel.mention}!**", ephemeral=True
            )
        else:
            await interaction.response.send_message(embed=embed, view=view)


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


class BrandingModal(discord.ui.Modal, title="🎨 Event Branding & Appearance"):
    """Modal for configuring event name, logo thumbnail, banner image, footer, and theme color."""

    def __init__(
        self,
        repo: "SantaRepository",
        session: dict[str, Any],
    ):
        super().__init__()
        self.repo = repo
        self.session = session
        self.session_id = session["id"]

        self.event_name_input = discord.ui.TextInput(
            label="🎉 Event Name / Title",
            placeholder="e.g. Buda Secret Santa 2026",
            default=session.get("event_name") or "",
            required=False,
            max_length=100,
        )
        self.add_item(self.event_name_input)

        self.theme_color_input = discord.ui.TextInput(
            label="🎨 Theme Color (Hex or Name)",
            placeholder="e.g. RED, GREEN, GOLD, BLUE, or #E74C3C",
            default=session.get("theme_color") or "",
            required=False,
            max_length=20,
        )
        self.add_item(self.theme_color_input)

        self.logo_url_input = discord.ui.TextInput(
            label="🖼️ Logo / Icon URL (Thumbnail)",
            placeholder="https://.../logo.png",
            default=session.get("logo_url") or "",
            required=False,
            max_length=300,
        )
        self.add_item(self.logo_url_input)

        self.banner_url_input = discord.ui.TextInput(
            label="🚩 Banner Image URL",
            placeholder="https://.../banner.png",
            default=session.get("banner_url") or "",
            required=False,
            max_length=300,
        )
        self.add_item(self.banner_url_input)

        self.footer_text_input = discord.ui.TextInput(
            label="📝 Footer Text",
            placeholder="e.g. Buda Holiday Season 2026",
            default=session.get("footer_text") or "",
            required=False,
            max_length=150,
        )
        self.add_item(self.footer_text_input)

    async def on_submit(self, interaction: discord.Interaction):
        from src.ui.embeds import build_registration_embed
        from src.ui.views import RegistrationView

        event_name = self.event_name_input.value.strip() or None
        theme_color = self.theme_color_input.value.strip() or None
        logo_url = self.logo_url_input.value.strip() or None
        banner_url = self.banner_url_input.value.strip() or None
        footer_text = self.footer_text_input.value.strip() or None

        await self.repo.update_session_details(
            session_id=self.session_id,
            event_name=event_name,
            theme_color=theme_color,
            logo_url=logo_url,
            banner_url=banner_url,
            footer_text=footer_text,
        )

        updated_session = await self.repo.get_session_by_id(self.session_id)
        participants = await self.repo.get_all_participants(self.session_id)

        # Refresh channel registration card in-place if message exists
        channel_updated = False
        ch_id = updated_session.get("channel_id") if updated_session else None
        msg_id = updated_session.get("registration_message_id") if updated_session else None

        if ch_id and msg_id:
            target_channel = interaction.client.get_channel(ch_id)
            if not target_channel:
                try:
                    target_channel = await interaction.client.fetch_channel(ch_id)
                except Exception:
                    target_channel = None

            if target_channel and isinstance(target_channel, discord.TextChannel):
                try:
                    existing_msg = await target_channel.fetch_message(msg_id)
                    embed = build_registration_embed(updated_session or {}, participants)
                    view = RegistrationView(repo=self.repo, session_id=self.session_id)
                    interaction.client.add_view(view)
                    await existing_msg.edit(embed=embed, view=view)
                    channel_updated = True
                except Exception as e:
                    logger.warning("Could not refresh registration message %s: %s", msg_id, e)

        status_note = " Main registration card updated in-place!" if channel_updated else ""
        summary_lines = [
            f"• **Event Name:** {event_name or 'Default'}",
            f"• **Theme Color:** {theme_color or 'Default'}",
            f"• **Logo / Icon:** {'Configured' if logo_url else 'None / Default'}",
            f"• **Banner Image:** {'Configured' if banner_url else 'None / Default'}",
            f"• **Footer Text:** {footer_text or 'Default'}",
        ]
        await interaction.response.send_message(
            f"🎨 **Event branding updated successfully!**{status_note}\n" + "\n".join(summary_lines),
            ephemeral=True,
        )



