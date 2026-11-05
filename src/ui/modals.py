"""Discord UI Modals for collecting wishlists and anonymous relay messages."""

import discord
import logging
from typing import TYPE_CHECKING, Optional

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
