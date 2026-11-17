"""Discord UI Views for buttons and interactive menus."""

import discord
import logging
from typing import TYPE_CHECKING, Optional, Callable, Any
from src.config import SANTA_CHANNEL_ID

if TYPE_CHECKING:
    from src.database.repo import SantaRepository

logger = logging.getLogger("secretsanta.views")


class RegistrationView(discord.ui.View):
    """Persistent registration view displayed in the public Santa channel."""

    def __init__(self, repo: "SantaRepository", session_id: int = 0):
        super().__init__(timeout=None)
        self.repo = repo
        self.session_id = session_id

    async def _resolve_session(self, interaction: discord.Interaction) -> Optional[dict[str, Any]]:
        """Resolves the session by bound session_id or active session in current guild."""
        if self.session_id and self.session_id > 0:
            session = await self.repo.get_session_by_id(self.session_id)
            if session:
                return session
        if interaction.guild_id and isinstance(interaction.guild_id, int):
            return await self.repo.get_active_session(interaction.guild_id)
        return None

    @discord.ui.button(
        label="Join Event 🎁",
        style=discord.ButtonStyle.primary,
        custom_id="santa:reg:join",
    )
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = await self._resolve_session(interaction)
        if not session or session.get("status") != "REGISTRATION":
            await interaction.response.send_message(
                "⚠️ Registration is currently closed for this event.", ephemeral=True
            )
            return

        session_id = session["id"]

        # Fetch existing participant data if any
        existing = await self.repo.get_participant(session_id, interaction.user.id)
        existing_wishlist = existing["wishlist"] if existing else ""
        existing_dislikes = existing["dislikes"] if existing else ""
        existing_notes = existing["offline_notes"] if existing else ""

        from src.ui.modals import WishlistModal

        modal = WishlistModal(
            repo=self.repo,
            session_id=session_id,
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
        session = await self._resolve_session(interaction)
        session_id = session["id"] if session else self.session_id

        existing = await self.repo.get_participant(session_id, interaction.user.id)
        if not existing:
            await interaction.response.send_message(
                "ℹ️ You are not registered yet! Click **[Join Event 🎁]** to sign up.",
                ephemeral=True,
            )
            return

        from src.ui.modals import WishlistModal

        modal = WishlistModal(
            repo=self.repo,
            session_id=session_id,
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
        session = await self._resolve_session(interaction)
        if not session or session.get("status") != "REGISTRATION":
            await interaction.response.send_message(
                "⚠️ Cannot leave once pairings have already been drawn! Contact the host.",
                ephemeral=True,
            )
            return

        session_id = session["id"]
        removed = await self.repo.remove_participant(session_id, interaction.user.id)
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

            session = await self._resolve_session(interaction)
            if not session:
                return
            session_id = session["id"]
            participants = await self.repo.get_all_participants(session_id)
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
    """View attached to Santa's private assignment DM (persistent across restarts)."""

    def __init__(self, repo: "SantaRepository", session_id: Optional[int] = None, baby_id: Optional[int] = None):
        super().__init__(timeout=None)
        self.repo = repo
        self.session_id = session_id
        self.baby_id = baby_id

    async def _resolve_pairing(self, interaction: discord.Interaction) -> Optional[tuple[int, int]]:
        """Returns (session_id, baby_id) using bound state or dynamic active pairing lookup."""
        if self.session_id and self.baby_id:
            return self.session_id, self.baby_id
        pairing = await self.repo.get_active_pairing_by_santa(interaction.user.id)
        if pairing:
            return pairing["session_id"], pairing["baby_id"]
        return None

    @discord.ui.button(
        label="Ask Baby Anonymously ✉️",
        style=discord.ButtonStyle.primary,
        custom_id="santa:dm:ask",
    )
    async def ask_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        resolved = await self._resolve_pairing(interaction)
        if not resolved:
            await interaction.response.send_message("❌ No active Secret Santa assignment found.", ephemeral=True)
            return

        session_id, baby_id = resolved
        from src.ui.modals import AnonymousMessageModal

        modal = AnonymousMessageModal(
            repo=self.repo,
            session_id=session_id,
            target_user_id=baby_id,
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
        resolved = await self._resolve_pairing(interaction)
        if not resolved:
            await interaction.response.send_message("❌ No active Secret Santa assignment found.", ephemeral=True)
            return

        session_id, _ = resolved
        await self.repo.update_gift_status(session_id, interaction.user.id, "BOUGHT")
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
        resolved = await self._resolve_pairing(interaction)
        if not resolved:
            await interaction.response.send_message("❌ No active Secret Santa assignment found.", ephemeral=True)
            return

        session_id, _ = resolved
        await self.repo.update_gift_status(session_id, interaction.user.id, "WRAPPED")
        await interaction.response.send_message(
            "🎁 **Awesome! Status updated to: Wrapped & Ready!** See you at the party!",
            ephemeral=True,
        )


class BabyReplyView(discord.ui.View):
    """View attached to an anonymous message received by Baby (persistent across restarts)."""

    def __init__(self, repo: "SantaRepository", session_id: Optional[int] = None, santa_id: Optional[int] = None):
        super().__init__(timeout=None)
        self.repo = repo
        self.session_id = session_id
        self.santa_id = santa_id

    async def _resolve_pairing(self, interaction: discord.Interaction) -> Optional[tuple[int, int]]:
        """Returns (session_id, santa_id) using bound state or dynamic active pairing lookup."""
        if self.session_id and self.santa_id:
            return self.session_id, self.santa_id
        pairing = await self.repo.get_active_pairing_by_baby(interaction.user.id)
        if pairing:
            return pairing["session_id"], pairing["santa_id"]
        return None

    @discord.ui.button(
        label="Reply to Secret Santa ↩️",
        style=discord.ButtonStyle.primary,
        custom_id="santa:dm:reply",
    )
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        resolved = await self._resolve_pairing(interaction)
        if not resolved:
            await interaction.response.send_message("❌ No active Secret Santa assignment found.", ephemeral=True)
            return

        session_id, santa_id = resolved
        from src.ui.modals import AnonymousMessageModal

        modal = AnonymousMessageModal(
            repo=self.repo,
            session_id=session_id,
            target_user_id=santa_id,
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
    """Interactive view for managing pair and group exclusions using UserSelect, Remove dropdown, and Bulk Modal."""

    def __init__(self, repo: "SantaRepository", session_id: int):
        super().__init__(timeout=300)
        self.repo = repo
        self.session_id = session_id
        self._add_static_items()

    def _add_static_items(self):
        # 1. UserSelect for pair/group exclusion (min=2, max=25)
        self.user_select = discord.ui.UserSelect(
            placeholder="Select 2 or more members to mutually exclude...",
            min_values=2,
            max_values=25,
            row=0,
        )
        self.user_select.callback = self._on_users_selected
        self.add_item(self.user_select)

        # Static buttons (Row 2)
        bulk_btn = discord.ui.Button(
            label="Bulk Add / Paste 📝",
            style=discord.ButtonStyle.primary,
            row=2,
        )
        bulk_btn.callback = self._on_bulk_button
        self.add_item(bulk_btn)

        clear_btn = discord.ui.Button(
            label="Clear All 🗑️",
            style=discord.ButtonStyle.danger,
            row=2,
        )
        clear_btn.callback = self._on_clear_button
        self.add_item(clear_btn)

        refresh_btn = discord.ui.Button(
            label="Refresh 🔄",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        refresh_btn.callback = self._on_refresh_button
        self.add_item(refresh_btn)

    async def setup_components(self, guild: Optional[discord.Guild] = None):
        """Re-render components dynamically based on current exclusions count."""
        self.clear_items()

        # 1. UserSelect (Row 0)
        self.user_select = discord.ui.UserSelect(
            placeholder="Select 2 or more members to mutually exclude...",
            min_values=2,
            max_values=25,
            row=0,
        )
        self.user_select.callback = self._on_users_selected
        self.add_item(self.user_select)

        # 2. Dropdown to remove specific exclusion if any exist (Row 1)
        exclusions = await self.repo.get_exclusions(self.session_id)
        if exclusions:
            participants = await self.repo.get_all_participants(self.session_id)
            p_map = {p["user_id"]: p.get("display_name") or p.get("username") for p in participants}

            remove_options: list[discord.SelectOption] = []
            for a_id, b_id in exclusions[:25]:
                m_a = guild.get_member(a_id) if guild else None
                m_b = guild.get_member(b_id) if guild else None
                name_a = (m_a.display_name if m_a else None) or p_map.get(a_id) or f"User {a_id}"
                name_b = (m_b.display_name if m_b else None) or p_map.get(b_id) or f"User {b_id}"
                label = f"{name_a} ⛔ {name_b}"[:100]
                remove_options.append(
                    discord.SelectOption(
                        label=label,
                        value=f"{a_id}_{b_id}",
                        description="Remove this exclusion rule",
                    )
                )

            self.remove_select = discord.ui.Select(
                placeholder="Select an exclusion rule to remove...",
                options=remove_options,
                row=1,
            )
            self.remove_select.callback = self._on_remove_selected
            self.add_item(self.remove_select)

        # 3. Action Buttons row (Row 2)
        bulk_btn = discord.ui.Button(
            label="Bulk Add / Paste 📝",
            style=discord.ButtonStyle.primary,
            row=2,
        )
        bulk_btn.callback = self._on_bulk_button
        self.add_item(bulk_btn)

        clear_btn = discord.ui.Button(
            label="Clear All 🗑️",
            style=discord.ButtonStyle.danger,
            row=2,
            disabled=(len(exclusions) == 0),
        )
        clear_btn.callback = self._on_clear_button
        self.add_item(clear_btn)

        refresh_btn = discord.ui.Button(
            label="Refresh 🔄",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        refresh_btn.callback = self._on_refresh_button
        self.add_item(refresh_btn)

    async def _on_users_selected(self, interaction: discord.Interaction, select: Optional[Any] = None):
        selected_users = self.user_select.values
        if len(selected_users) < 2:
            await interaction.response.send_message("⚠️ Please select at least 2 members.", ephemeral=True)
            return

        import itertools

        pairs = list(itertools.combinations([u.id for u in selected_users], 2))
        added = await self.repo.add_exclusions_bulk(self.session_id, pairs)

        await self.setup_components(interaction.guild)
        embed = await self.build_exclusions_embed(interaction.guild)

        if len(selected_users) == 2:
            conf = f"✅ **Exclusion rule added between {selected_users[0].mention} and {selected_users[1].mention}!**"
        else:
            conf = f"✅ **Group exclusion added:** Created {added} mutual pair rules between {len(selected_users)} members."

        await interaction.response.edit_message(content=conf, embed=embed, view=self)

    async def _on_remove_selected(self, interaction: discord.Interaction, select: Optional[Any] = None):
        remove_sel = getattr(self, "remove_select", None)
        values = remove_sel.values if remove_sel else []
        if not values:
            return
        u_a_str, u_b_str = values[0].split("_")
        u_a, u_b = int(u_a_str), int(u_b_str)

        await self.repo.remove_exclusion(self.session_id, u_a, u_b)

        await self.setup_components(interaction.guild)
        embed = await self.build_exclusions_embed(interaction.guild)
        await interaction.response.edit_message(
            content="🗑️ **Exclusion rule removed.**",
            embed=embed,
            view=self,
        )

    async def _on_bulk_button(self, interaction: discord.Interaction, button: Optional[Any] = None):
        from src.ui.modals import BulkExclusionModal

        modal = BulkExclusionModal(self.repo, self.session_id)
        await interaction.response.send_modal(modal)

    async def _on_clear_button(self, interaction: discord.Interaction, button: Optional[Any] = None):
        count = await self.repo.clear_all_exclusions(self.session_id)
        await self.setup_components(interaction.guild)
        embed = await self.build_exclusions_embed(interaction.guild)
        await interaction.response.edit_message(
            content=f"🗑️ **Cleared all {count} exclusion rules.**",
            embed=embed,
            view=self,
        )

    async def _on_refresh_button(self, interaction: discord.Interaction, button: Optional[Any] = None):
        await self.setup_components(interaction.guild)
        embed = await self.build_exclusions_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def build_exclusions_embed(self, guild: Optional[discord.Guild]) -> discord.Embed:
        exclusions = await self.repo.get_exclusions(self.session_id)
        participants = await self.repo.get_all_participants(self.session_id)
        p_map = {
            p["user_id"]: (guild.get_member(p["user_id"]).display_name if guild and guild.get_member(p["user_id"]) else None)
            or p.get("display_name")
            or p.get("username")
            or f"User {p['user_id']}"
            for p in participants
        }

        embed = discord.Embed(
            title="🚫 Pair & Group Exclusion Rules",
            description=(
                "Exclusion rules prevent pairs or groups (couples, roommates, family) "
                "from drawing each other during the Secret Santa match.\n\n"
                "• **Dropdown:** Select 2 members for a pair, or 3+ members for group mutual exclusion.\n"
                "• **Bulk Paste:** Click `Bulk Add / Paste 📝` to paste multiple pairs or groups at once."
            ),
            color=discord.Color.orange(),
        )

        # 1. Feasibility Pre-Check (when participants have joined)
        if participants:
            from src.services.matcher import validate_draw_feasibility
            report = validate_draw_feasibility([p["user_id"] for p in participants], exclusions, names=p_map)

            if report.status == "IMPOSSIBLE":
                embed.color = discord.Color.red()
                details_text = "\n" + "\n".join(f"• {d}" for d in report.details[:3]) if report.details else ""
                embed.add_field(
                    name="🚨 Matching Feasibility: IMPOSSIBLE",
                    value=f"⚠️ **{report.headline}**{details_text}",
                    inline=False,
                )
            elif report.status == "WARNING":
                embed.color = discord.Color.gold()
                details_text = "\n" + "\n".join(f"• {d}" for d in report.details[:3]) if report.details else ""
                embed.add_field(
                    name="⚠️ Matching Feasibility: TIGHT CONSTRAINTS",
                    value=f"⚡ **{report.headline}**{details_text}",
                    inline=False,
                )
            elif report.status == "READY":
                embed.color = discord.Color.green()
                embed.add_field(
                    name="🎯 Matching Feasibility: READY",
                    value="✅ **Valid Secret Santa circle is mathematically guaranteed!**",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="ℹ️ Matching Feasibility",
                    value=f"⏳ *{report.headline}*",
                    inline=False,
                )

        # 2. Existing exclusions list
        if not exclusions:
            embed.add_field(
                name="Current Exclusions (0)",
                value="*No exclusion rules set yet.*",
                inline=False,
            )
        else:
            lines = []
            for a_id, b_id in exclusions:
                name_a = p_map.get(a_id, f"User {a_id}")
                name_b = p_map.get(b_id, f"User {b_id}")
                lines.append(f"• **{name_a}** ⛔ **{name_b}**")

            chunk_size = 15
            for i in range(0, len(lines), chunk_size):
                chunk = lines[i : i + chunk_size]
                title = f"Current Exclusions ({len(exclusions)})" if i == 0 else "Exclusions (cont.)"
                embed.add_field(name=title, value="\n".join(chunk), inline=False)

        embed.set_footer(text="Select members above, click Bulk Add, or select a rule to remove.")
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
    """All-in-one interactive control dashboard for the event host (persistent across restarts)."""

    def __init__(self, repo: "SantaRepository", session_id: int = 0):
        super().__init__(timeout=None)
        self.repo = repo
        self.session_id = session_id

    async def _resolve_session(self, interaction: discord.Interaction) -> Optional[dict[str, Any]]:
        """Resolves the session by bound session_id or active session in current guild."""
        if self.session_id and self.session_id > 0:
            session = await self.repo.get_session_by_id(self.session_id)
            if session:
                return session
        if interaction.guild_id and isinstance(interaction.guild_id, int):
            return await self.repo.get_active_session(interaction.guild_id)
        return None

    @discord.ui.button(
        label="⚙️ Settings",
        style=discord.ButtonStyle.primary,
        custom_id="santa:panel:settings",
        row=0,
    )
    async def settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import SetupModal

        session = await self._resolve_session(interaction)
        if not session:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        session_id = session["id"]
        modal = SetupModal(
            repo=self.repo,
            session_id=session_id,
            channel_id=session.get("channel_id") or SANTA_CHANNEL_ID or interaction.channel_id,
            existing_budget=session.get("budget") or "",
            existing_party_date=session.get("party_date") or "",
            existing_party_venue=session.get("party_venue") or "",
            existing_deadline=session.get("signup_deadline") or "",
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="📊 Create Poll",
        style=discord.ButtonStyle.secondary,
        custom_id="santa:panel:poll",
        row=0,
    )
    async def poll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import CreatePollModal

        session = await self._resolve_session(interaction)
        ch_id = (session.get("channel_id") if session else None) or SANTA_CHANNEL_ID or interaction.channel_id
        modal = CreatePollModal(target_channel_id=ch_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="⏰ Set Deadline",
        style=discord.ButtonStyle.secondary,
        custom_id="santa:panel:deadline",
        row=0,
    )
    async def deadline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import DeadlineModal

        session = await self._resolve_session(interaction)
        if not session:
            await interaction.response.send_message("❌ No active session found.", ephemeral=True)
            return

        modal = DeadlineModal(
            repo=self.repo,
            session_id=session["id"],
            existing_deadline=session.get("signup_deadline") or "",
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="🚫 Exclusions",
        style=discord.ButtonStyle.secondary,
        custom_id="santa:panel:exclusions",
        row=1,
    )
    async def exclusions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = await self._resolve_session(interaction)
        if not session:
            await interaction.response.send_message("❌ No active session found.", ephemeral=True)
            return

        view = ExclusionManageView(self.repo, session["id"])
        await view.setup_components(interaction.guild)
        embed = await view.build_exclusions_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="📢 Reminders",
        style=discord.ButtonStyle.secondary,
        custom_id="santa:panel:reminders",
        row=1,
    )
    async def reminders_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = await self._resolve_session(interaction)
        if not session:
            await interaction.response.send_message("❌ No active session found.", ephemeral=True)
            return

        view = RemindMenuView(self.repo, session["id"])
        await interaction.response.send_message(
            "📢 **Reminder Center:** Choose an action below:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="🔒 Master Sheet",
        style=discord.ButtonStyle.secondary,
        custom_id="santa:panel:export",
        row=1,
    )
    async def export_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.embeds import build_admin_export_embed

        session = await self._resolve_session(interaction)
        if not session:
            await interaction.response.send_message("❌ No active session found.", ephemeral=True)
            return

        pairings = await self.repo.get_all_pairings(session["id"])
        embed = build_admin_export_embed(pairings)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="🎲 Draw Pairs",
        style=discord.ButtonStyle.success,
        custom_id="santa:panel:draw",
        row=2,
    )
    async def draw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.services.draw_service import execute_draw

        session = await self._resolve_session(interaction)
        if not session:
            await interaction.response.send_message("❌ No active session found.", ephemeral=True)
            return

        session_id = session["id"]
        if session.get("status") == "IN_PROGRESS":
            await interaction.response.send_message(
                "⚠️ Pairings have already been drawn for this event!", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        success, msg, _ = await execute_draw(
            interaction.client, self.repo, session_id, trigger_type="MANUAL"
        )
        if success:
            await interaction.followup.send("🎉 **Secret Santa Draw executed successfully!** Targets dispatched in DM.")
        else:
            await interaction.followup.send(f"❌ {msg}")

    @discord.ui.button(
        label="📦 Backup",
        style=discord.ButtonStyle.secondary,
        custom_id="santa:panel:backup",
        row=2,
    )
    async def backup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from src.services.backup_service import create_migration_bundle, list_backups
        from src.config import DATABASE_PATH, ASSETS_DIR

        bundle_path = create_migration_bundle(DATABASE_PATH, ASSETS_DIR)
        backups = list_backups(DATABASE_PATH)

        embed = discord.Embed(
            title="📦 Secret Santa Backup & Migration Bundle",
            description=(
                "A hot, crash-safe snapshot of your database and branding assets has been created.\n\n"
                "**To migrate or move host:**\n"
                "1. Download the attached `.zip` bundle.\n"
                "2. Extract onto your new host server or container.\n"
                "3. Run `python3 run.py` (all active sign-ups, pairings, and settings are restored)."
            ),
            color=discord.Color.green(),
        )
        embed.add_field(name="Bundle File", value=f"`{bundle_path.name}`", inline=True)
        embed.add_field(name="Size", value=f"`{round(bundle_path.stat().st_size / 1024, 1)} KB`", inline=True)
        embed.add_field(name="Local Backups", value=f"**{len(backups)}** retained in `data/backups/`", inline=True)

        file = discord.File(str(bundle_path), filename=bundle_path.name)
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)

    @discord.ui.button(
        label="Refresh 🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="santa:panel:refresh",
        row=2,
    )
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = await self._resolve_session(interaction)
        if not session:
            await interaction.response.send_message("❌ Session not found.", ephemeral=True)
            return

        session_id = session["id"]
        participants = await self.repo.get_all_participants(session_id)
        exclusions = await self.repo.get_exclusions(session_id)
        from src.ui.embeds import build_host_control_panel_embed

        embed = build_host_control_panel_embed(
            session=session,
            participants=participants,
            exclusions=exclusions,
            guild=interaction.guild,
        )
        await interaction.response.edit_message(embed=embed, view=self)


class MyStatusView(discord.ui.View):
    """View attached to /my_status giving the user an interactive button to edit their wishlist (persistent)."""

    def __init__(self, repo: "SantaRepository", session_id: int = 0):
        super().__init__(timeout=None)
        self.repo = repo
        self.session_id = session_id

    async def _resolve_session_id(self, interaction: discord.Interaction) -> Optional[int]:
        if self.session_id and self.session_id > 0:
            return self.session_id
        if interaction.guild_id and isinstance(interaction.guild_id, int):
            s = await self.repo.get_active_session(interaction.guild_id)
            if s:
                return s["id"]
        # In DM fallback: look up active pairing
        if hasattr(interaction, "user") and interaction.user and hasattr(interaction.user, "id"):
            p = await self.repo.get_active_pairing_by_santa(interaction.user.id)
            if p:
                return p["session_id"]
        return None

    @discord.ui.button(
        label="Edit Wishlist 📝",
        style=discord.ButtonStyle.primary,
        custom_id="santa:status:edit",
    )
    async def edit_wishlist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.ui.modals import WishlistModal

        session_id = await self._resolve_session_id(interaction)
        if not session_id:
            await interaction.response.send_message("❌ No active Secret Santa session found.", ephemeral=True)
            return

        participant = await self.repo.get_participant(session_id, interaction.user.id)
        if not participant:
            await interaction.response.send_message("ℹ️ You are not registered yet.", ephemeral=True)
            return

        modal = WishlistModal(
            repo=self.repo,
            session_id=session_id,
            existing_wishlist=participant.get("wishlist", ""),
            existing_dislikes=participant.get("dislikes", ""),
            existing_notes=participant.get("offline_notes", ""),
        )
        await interaction.response.send_modal(modal)

