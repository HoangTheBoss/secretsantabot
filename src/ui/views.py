"""Discord UI Views for buttons and interactive menus."""

import discord
import logging
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from src.database.repo import SantaRepository

logger = logging.getLogger("secretsanta.views")


class RegistrationView(discord.ui.View):
    """Persistent registration view displayed in the public Santa channel."""

    def __init__(self, repo: "SantaRepository", session_id: int):
        super().__init__(timeout=None)
        self.repo = repo
        self.session_id = session_id

    @discord.ui.button(
        label="Join Event 🎁",
        style=discord.ButtonStyle.primary,
        custom_id="santa:reg:join",
    )
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = await self.repo.get_session_by_id(self.session_id)
        if not session or session.get("status") != "REGISTRATION":
            await interaction.response.send_message(
                "⚠️ Registration is currently closed for this event.", ephemeral=True
            )
            return

        # Pre-check: Verify the user can receive DMs from the bot
        try:
            # Send a silent/ephemeral test DM handshake
            await interaction.user.send(
                "🎄 **Hi there!** This is a verification message to confirm the bot can send you "
                "your Secret Santa target assignment. Please complete your registration in the server!"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ **Cannot receive Direct Messages!**\n"
                "The bot cannot send you your secret target because your Discord Privacy Settings block DMs from server members.\n\n"
                "**How to fix:**\n"
                "1. Right-click this server icon (or tap server name on mobile).\n"
                "2. Go to **Privacy Settings**.\n"
                "3. Enable **'Allow direct messages from server members'**.\n"
                "4. Click **[Join Event 🎁]** again!",
                ephemeral=True,
            )
            return
        except Exception as e:
            logger.warning("Error verifying DM for user %s: %s", interaction.user.id, e)

        # Fetch existing participant data if any
        existing = await self.repo.get_participant(self.session_id, interaction.user.id)
        existing_wishlist = existing["wishlist"] if existing else ""
        existing_dislikes = existing["dislikes"] if existing else ""
        existing_notes = existing["offline_notes"] if existing else ""

        from src.ui.modals import WishlistModal

        modal = WishlistModal(
            repo=self.repo,
            session_id=self.session_id,
            existing_wishlist=existing_wishlist,
            existing_dislikes=existing_dislikes,
            existing_notes=existing_notes,
            on_refresh_callback=self._refresh_channel_message,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Update Wishlist 📝",
        style=discord.ButtonStyle.secondary,
        custom_id="santa:reg:update",
    )
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        existing = await self.repo.get_participant(self.session_id, interaction.user.id)
        if not existing:
            await interaction.response.send_message(
                "ℹ️ You are not registered yet! Click **[Join Event 🎁]** to sign up.",
                ephemeral=True,
            )
            return

        from src.ui.modals import WishlistModal

        modal = WishlistModal(
            repo=self.repo,
            session_id=self.session_id,
            existing_wishlist=existing.get("wishlist", ""),
            existing_dislikes=existing.get("dislikes", ""),
            existing_notes=existing.get("offline_notes", ""),
            on_refresh_callback=self._refresh_channel_message,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Leave Event ❌",
        style=discord.ButtonStyle.danger,
        custom_id="santa:reg:leave",
    )
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = await self.repo.get_session_by_id(self.session_id)
        if not session or session.get("status") != "REGISTRATION":
            await interaction.response.send_message(
                "⚠️ Cannot leave once pairings have already been drawn! Contact the host.",
                ephemeral=True,
            )
            return

        removed = await self.repo.remove_participant(self.session_id, interaction.user.id)
        if removed:
            await interaction.response.send_message(
                "👋 You have been removed from the Secret Santa registration.",
                ephemeral=True,
            )
            await self._refresh_channel_message(interaction)
        else:
            await interaction.response.send_message(
                "ℹ️ You are not registered in this event.", ephemeral=True
            )

    async def _refresh_channel_message(self, interaction: discord.Interaction):
        """Update the channel embed with the latest participant count and list."""
        try:
            from src.ui.embeds import build_registration_embed

            session = await self.repo.get_session_by_id(self.session_id)
            if not session:
                return
            participants = await self.repo.get_all_participants(self.session_id)
            embed = build_registration_embed(session, participants)
            if interaction.message:
                await interaction.message.edit(embed=embed, view=self)
        except Exception as e:
            logger.error("Failed to refresh channel message: %s", e)


class SantaDmView(discord.ui.View):
    """View attached to Santa's private assignment DM."""

    def __init__(self, repo: "SantaRepository", session_id: int, baby_id: int):
        super().__init__(timeout=None)
        self.repo = repo
        self.session_id = session_id
        self.baby_id = baby_id

    @discord.ui.button(
        label="Ask Baby Anonymously ✉️",
        style=discord.ButtonStyle.primary,
        custom_id="santa:dm:ask",
    )
    async def ask_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import AnonymousMessageModal

        modal = AnonymousMessageModal(
            repo=self.repo,
            session_id=self.session_id,
            target_user_id=self.baby_id,
            direction="SANTA_TO_BABY",
            title="Ask Baby Anonymously",
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Mark as Bought 🛍️",
        style=discord.ButtonStyle.secondary,
        custom_id="santa:dm:bought",
    )
    async def bought_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.repo.update_gift_status(self.session_id, interaction.user.id, "BOUGHT")
        await interaction.response.send_message(
            "🛍️ **Status updated to: Purchased!** Don't forget to mark it as wrapped once packed.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Mark as Wrapped & Ready 🎁",
        style=discord.ButtonStyle.success,
        custom_id="santa:dm:wrapped",
    )
    async def wrapped_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.repo.update_gift_status(self.session_id, interaction.user.id, "WRAPPED")
        await interaction.response.send_message(
            "🎁 **Awesome! Status updated to: Wrapped & Ready!** See you at the party!",
            ephemeral=True,
        )


class BabyReplyView(discord.ui.View):
    """View attached to an anonymous message received by Baby."""

    def __init__(self, repo: "SantaRepository", session_id: int, santa_id: int):
        super().__init__(timeout=None)
        self.repo = repo
        self.session_id = session_id
        self.santa_id = santa_id

    @discord.ui.button(
        label="Reply to Secret Santa ↩️",
        style=discord.ButtonStyle.primary,
        custom_id="santa:dm:reply",
    )
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import AnonymousMessageModal

        modal = AnonymousMessageModal(
            repo=self.repo,
            session_id=self.session_id,
            target_user_id=self.santa_id,
            direction="BABY_TO_SANTA",
            title="Reply to Secret Santa",
        )
        await interaction.response.send_modal(modal)


class PollView(discord.ui.View):
    """Interactive poll buttons for voting on Budget or Date."""

    def __init__(self, question: str, options: list[str], callback: Optional[Callable] = None):
        super().__init__(timeout=86400 * 7)  # 7 days
        self.question = question
        self.options = options
        self.callback = callback
        self.votes: dict[int, int] = {}  # user_id -> option_index

        for idx, option in enumerate(options[:5]):  # Up to 5 button choices
            button = discord.ui.Button(
                label=f"{option} (0)",
                style=discord.ButtonStyle.secondary,
                custom_id=f"poll:opt:{idx}",
            )
            button.callback = self._create_option_callback(idx)
            self.add_item(button)

    def _create_option_callback(self, option_index: int):
        async def option_click(interaction: discord.Interaction):
            self.votes[interaction.user.id] = option_index
            self._update_button_labels()
            await interaction.response.edit_message(view=self)
            if self.callback:
                await self.callback(self.options[option_index], self.votes)

        return option_click

    def _update_button_labels(self):
        counts = {i: 0 for i in range(len(self.options))}
        for user_vote in self.votes.values():
            counts[user_vote] = counts.get(user_vote, 0) + 1

        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id and child.custom_id.startswith("poll:opt:"):
                idx = int(child.custom_id.split(":")[-1])
                opt_name = self.options[idx]
                child.label = f"{opt_name} ({counts[idx]})"
