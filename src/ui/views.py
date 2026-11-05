"""Discord UI Views for buttons and interactive menus."""

import discord
import logging
from typing import TYPE_CHECKING, Optional, Callable
from src.config import SANTA_CHANNEL_ID

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
            else:
                channel_id = session.get("channel_id")
                msg_id = session.get("registration_message_id")
                if channel_id and msg_id:
                    channel = interaction.client.get_channel(channel_id)
                    if not channel:
                        try:
                            channel = await interaction.client.fetch_channel(channel_id)
                        except Exception:
                            channel = None
                    if channel and isinstance(channel, discord.TextChannel):
                        try:
                            msg = await channel.fetch_message(msg_id)
                            await msg.edit(embed=embed, view=self)
                        except Exception:
                            pass
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


class ExclusionManageView(discord.ui.View):
    """Interactive view for managing pair exclusions using Discord's native UserSelect component."""

    def __init__(self, repo: "SantaRepository", session_id: int):
        super().__init__(timeout=300)
        self.repo = repo
        self.session_id = session_id

        self.user_select = discord.ui.UserSelect(
            placeholder="Select 2 members who cannot draw each other...",
            min_values=2,
            max_values=2,
        )
        self.user_select.callback = self._on_users_selected
        self.add_item(self.user_select)

    async def _on_users_selected(self, interaction: discord.Interaction):
        selected_users = self.user_select.values
        if len(selected_users) != 2:
            await interaction.response.send_message("⚠️ Please select exactly 2 members.", ephemeral=True)
            return

        u1, u2 = selected_users[0], selected_users[1]
        if u1.id == u2.id:
            await interaction.response.send_message("❌ Cannot exclude a user from themselves.", ephemeral=True)
            return

        await self.repo.add_exclusion(self.session_id, u1.id, u2.id)
        embed = await self.build_exclusions_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Clear All Exclusions 🗑️", style=discord.ButtonStyle.danger, row=1)
    async def clear_exclusions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        exclusions = await self.repo.get_exclusions(self.session_id)
        for a, b in exclusions:
            await self.repo.remove_exclusion(self.session_id, a, b)
        embed = await self.build_exclusions_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def build_exclusions_embed(self, guild: Optional[discord.Guild]) -> discord.Embed:
        exclusions = await self.repo.get_exclusions(self.session_id)
        embed = discord.Embed(
            title="🚫 Pair Exclusion Rules",
            description="Use the dropdown below to select 2 members (e.g. couples/roommates) who **cannot** be paired together.",
            color=discord.Color.orange(),
        )
        if not exclusions:
            embed.add_field(name="Current Exclusions", value="*No exclusion rules set yet.*", inline=False)
        else:
            lines = []
            for a_id, b_id in exclusions:
                m_a = guild.get_member(a_id) if guild else None
                m_b = guild.get_member(b_id) if guild else None
                name_a = m_a.display_name if m_a else f"User {a_id}"
                name_b = m_b.display_name if m_b else f"User {b_id}"
                lines.append(f"• **{name_a}** ⛔ **{name_b}**")
            embed.add_field(name=f"Current Exclusions ({len(exclusions)})", value="\n".join(lines), inline=False)

        embed.set_footer(text="Select 2 members from the dropdown to add a rule.")
        return embed


class RemindMenuView(discord.ui.View):
    """Interactive view for triggering channel and DM reminders."""

    def __init__(self, repo: "SantaRepository", session_id: int):
        super().__init__(timeout=180)
        self.repo = repo
        self.session_id = session_id

    @discord.ui.button(label="📢 Broadcast Channel Reminder", style=discord.ButtonStyle.primary, row=0)
    async def broadcast_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import RemindNoteModal
        from src.ui.embeds import build_public_reminder_embed

        async def callback(modal_interaction: discord.Interaction, note: Optional[str]):
            session = await self.repo.get_session_by_id(self.session_id)
            if not session:
                await modal_interaction.response.send_message("❌ Session not found.", ephemeral=True)
                return

            participants = await self.repo.get_all_participants(self.session_id)
            embed = build_public_reminder_embed(session, participants, custom_note=note)

            target_channel = modal_interaction.client.get_channel(session.get("channel_id"))
            if not target_channel:
                try:
                    target_channel = await modal_interaction.client.fetch_channel(session.get("channel_id"))
                except Exception:
                    target_channel = modal_interaction.channel

            if isinstance(target_channel, discord.TextChannel):
                await target_channel.send(embed=embed)
                await self.repo.update_session_reminded(self.session_id)
                await modal_interaction.response.send_message(
                    f"✅ **Announcement broadcast to {target_channel.mention}!**", ephemeral=True
                )
            else:
                await modal_interaction.response.send_message("❌ Could not reach text channel.", ephemeral=True)

        modal = RemindNoteModal(title="Channel Announcement Note", on_submit_callback=callback)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📩 Nudge Unwrapped Santas (DMs)", style=discord.ButtonStyle.secondary, row=0)
    async def nudge_dms_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import RemindNoteModal
        from src.ui.embeds import build_dm_reminder_embed

        session = await self.repo.get_session_by_id(self.session_id)
        if not session or session.get("status") != "IN_PROGRESS":
            await interaction.response.send_message(
                "⚠️ Pairings have not been drawn yet! Use the channel reminder button instead.",
                ephemeral=True,
            )
            return

        async def callback(modal_interaction: discord.Interaction, note: Optional[str]):
            await modal_interaction.response.defer(thinking=True, ephemeral=True)
            unwrapped = await self.repo.get_unwrapped_pairings(self.session_id)
            if not unwrapped:
                await modal_interaction.followup.send(
                    "🎉 **All Santas have already marked their gifts as wrapped!** No DMs needed."
                )
                return

            sent_count = 0
            failed_names = []
            for p in unwrapped:
                santa_id = p["santa_id"]
                try:
                    user = await modal_interaction.client.fetch_user(santa_id)
                    embed = build_dm_reminder_embed(
                        baby_name=p["baby_name"],
                        gift_tag_code=p["gift_tag_code"],
                        party_date=session.get("party_date"),
                        party_venue=session.get("party_venue"),
                        custom_note=note,
                    )
                    view = SantaDmView(repo=self.repo, session_id=self.session_id, baby_id=p["baby_id"])
                    await user.send(embed=embed, view=view)
                    await self.repo.update_pairing_reminded(self.session_id, santa_id)
                    sent_count += 1
                except Exception:
                    failed_names.append(p.get("santa_name", str(santa_id)))

            msg = f"✅ **Sent private reminder DMs to {sent_count} unwrapped Santa(s).**"
            if failed_names:
                msg += f"\n⚠️ DMs failed for: {', '.join(failed_names)}"
            await modal_interaction.followup.send(msg)

        modal = RemindNoteModal(title="Custom Note for Santa DMs", on_submit_callback=callback)
        await interaction.response.send_modal(modal)


class HostControlPanel(discord.ui.View):
    """All-in-one interactive control dashboard for the event host."""

    def __init__(self, repo: "SantaRepository", session_id: int):
        super().__init__(timeout=300)
        self.repo = repo
        self.session_id = session_id

    @discord.ui.button(label="⚙️ Settings", style=discord.ButtonStyle.primary, row=0)
    async def settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import SetupModal

        session = await self.repo.get_session_by_id(self.session_id)
        if not session:
            return
        modal = SetupModal(
            repo=self.repo,
            session_id=self.session_id,
            channel_id=session.get("channel_id") or SANTA_CHANNEL_ID or interaction.channel_id,
            existing_budget=session.get("budget") or "",
            existing_party_date=session.get("party_date") or "",
            existing_party_venue=session.get("party_venue") or "",
            existing_deadline=session.get("signup_deadline") or "",
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📊 Create Poll", style=discord.ButtonStyle.secondary, row=0)
    async def poll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import CreatePollModal

        session = await self.repo.get_session_by_id(self.session_id)
        ch_id = (session.get("channel_id") if session else None) or SANTA_CHANNEL_ID or interaction.channel_id
        modal = CreatePollModal(target_channel_id=ch_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⏰ Set Deadline", style=discord.ButtonStyle.secondary, row=0)
    async def deadline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import DeadlineModal

        session = await self.repo.get_session_by_id(self.session_id)
        modal = DeadlineModal(
            repo=self.repo,
            session_id=self.session_id,
            existing_deadline=session.get("signup_deadline") if session else "",
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🚫 Exclusions", style=discord.ButtonStyle.secondary, row=1)
    async def exclusions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ExclusionManageView(self.repo, self.session_id)
        embed = await view.build_exclusions_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="📢 Reminders", style=discord.ButtonStyle.secondary, row=1)
    async def reminders_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RemindMenuView(self.repo, self.session_id)
        await interaction.response.send_message(
            "📢 **Reminder Center:** Choose an action below:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="🔒 Master Sheet", style=discord.ButtonStyle.secondary, row=1)
    async def export_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.embeds import build_admin_export_embed

        pairings = await self.repo.get_all_pairings(self.session_id)
        embed = build_admin_export_embed(pairings)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎲 Draw Pairs", style=discord.ButtonStyle.success, row=2)
    async def draw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.services.draw_service import execute_draw

        session = await self.repo.get_session_by_id(self.session_id)
        if not session:
            return

        if session.get("status") == "IN_PROGRESS":
            await interaction.response.send_message(
                "⚠️ Pairings have already been drawn for this event!", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        success, msg, _ = await execute_draw(
            interaction.client, self.repo, self.session_id, trigger_type="MANUAL"
        )
        if success:
            await interaction.followup.send("🎉 **Secret Santa Draw executed successfully!** Targets dispatched in DM.")
        else:
            await interaction.followup.send(f"❌ {msg}")


class MyStatusView(discord.ui.View):
    """View attached to /my_status giving the user an interactive button to edit their wishlist."""

    def __init__(self, repo: "SantaRepository", session_id: int):
        super().__init__(timeout=180)
        self.repo = repo
        self.session_id = session_id

    @discord.ui.button(label="Edit Wishlist 📝", style=discord.ButtonStyle.primary)
    async def edit_wishlist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import WishlistModal

        participant = await self.repo.get_participant(self.session_id, interaction.user.id)
        if not participant:
            await interaction.response.send_message("ℹ️ You are not registered yet.", ephemeral=True)
            return

        modal = WishlistModal(
            repo=self.repo,
            session_id=self.session_id,
            existing_wishlist=participant.get("wishlist", ""),
            existing_dislikes=participant.get("dislikes", ""),
            existing_notes=participant.get("offline_notes", ""),
        )
        await interaction.response.send_modal(modal)

