"""Discord Embed generators for Buda Secret Santa."""

import discord
from typing import Any, Optional


def create_progress_bar(current: int, total: int, bar_length: int = 10) -> str:
    """Generate a visual text progress bar: [████████░░]."""
    if total <= 0:
        return f"[{'░' * bar_length}] 0%"
    fraction = min(max(current / total, 0.0), 1.0)
    filled = int(fraction * bar_length)
    empty = bar_length - filled
    percent = int(fraction * 100)
    return f"`[{'█' * filled}{'░' * empty}]` **{percent}%** ({current}/{total})"


def build_registration_embed(
    session: dict[str, Any],
    participants: list[dict[str, Any]],
) -> discord.Embed:
    """Embed shown in the main #secret-santa channel during registration."""
    status = session.get("status", "REGISTRATION")
    budget = session.get("budget") or "To be determined"
    party_date = session.get("party_date") or "To be announced"
    party_venue = session.get("party_venue") or "To be announced"

    color = discord.Color.green() if status == "REGISTRATION" else discord.Color.gold()
    embed = discord.Embed(
        title="🎄 Buda Secret Santa: Annual Gift Exchange 🎅",
        description=(
            "Welcome to our private Secret Santa game! Sign up below, submit your wishlist, "
            "and get ready for our in-person holiday party.\n\n"
            "**Important:** Please ensure your server privacy settings allow Direct Messages "
            "so the bot can privately deliver your target and physical gift code!"
        ),
        color=color,
    )

    embed.add_field(name="💰 Budget Limit", value=budget, inline=True)
    embed.add_field(name="📅 Party Date", value=party_date, inline=True)
    embed.add_field(name="📍 Party Venue", value=party_venue, inline=True)

    # Participant roster
    count = len(participants)
    if count == 0:
        names_text = "*No participants registered yet. Be the first to join!*"
    else:
        names_list = [f"{i + 1}. {p['display_name']} (@{p['username']})" for i, p in enumerate(participants)]
        # Discord embed field value limit is 1024 characters
        names_text = "\n".join(names_list)
        if len(names_text) > 1000:
            names_text = names_text[:990] + f"\n*...and {count - 15} more*"

    embed.add_field(
        name=f"👥 Registered Santas ({count})",
        value=names_text,
        inline=False,
    )

    embed.set_footer(text="Click [Join 🎁] below to enter your wishlist and register!")
    return embed


def build_santa_dm_embed(
    baby_name: str,
    baby_username: str,
    avatar_url: Optional[str],
    wishlist: str,
    dislikes: str,
    offline_notes: str,
    gift_tag_code: str,
    budget: Optional[str] = None,
    party_date: Optional[str] = None,
    party_venue: Optional[str] = None,
) -> discord.Embed:
    """Secret DM embed sent to Santa."""
    embed = discord.Embed(
        title="🎅 Shh! Your Secret Santa Assignment is Here!",
        description=(
            f"You have been secretly chosen as the Santa for **{baby_name}** (@{baby_username})!\n"
            "Keep this strictly confidential until the in-person party!"
        ),
        color=discord.Color.red(),
    )

    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    embed.add_field(
        name="🎁 Baby's Wishlist & Interests",
        value=wishlist.strip() or "*No specific wishlist provided.*",
        inline=False,
    )

    embed.add_field(
        name="🚫 Dislikes & Allergies",
        value=dislikes.strip() or "*None specified.*",
        inline=False,
    )

    embed.add_field(
        name="🥂 Party & Drink Preferences",
        value=offline_notes.strip() or "*None specified.*",
        inline=False,
    )

    instructions = (
        f"1. **Recipient Tag:** Write `To: {baby_name}` on the wrapping.\n"
        f"2. **Secret Tag Code:** Write `Code: {gift_tag_code}` on the wrapping.\n"
        f"3. **Do NOT sign your real name** on the gift!\n"
        f"4. Quietly deposit your gift on the party table upon arrival."
    )
    embed.add_field(name="🏷️ Physical Gift Packaging Rule", value=instructions, inline=False)

    meta_info = []
    if budget:
        meta_info.append(f"• **Budget:** {budget}")
    if party_date:
        meta_info.append(f"• **Date:** {party_date}")
    if party_venue:
        meta_info.append(f"• **Venue:** {party_venue}")
    if meta_info:
        embed.add_field(name="📌 Event Info", value="\n".join(meta_info), inline=False)

    embed.set_footer(
        text="Need to ask a size or preference? Click [Ask Baby Anonymously ✉️] below!"
    )
    return embed


def build_prep_dashboard_embed(
    session: dict[str, Any],
    participants: list[dict[str, Any]],
) -> discord.Embed:
    """Public progress embed displayed in the channel."""
    total = len(participants)
    wrapped = sum(1 for p in participants if p.get("gift_status") in ("WRAPPED", "READY", "AT_PARTY"))
    bought = sum(1 for p in participants if p.get("gift_status") == "BOUGHT")

    party_date = session.get("party_date") or "Upcoming"
    party_venue = session.get("party_venue") or "Party Venue"

    embed = discord.Embed(
        title="🎁 Secret Santa Preparation Dashboard",
        description=(
            f"Here is how our group is progressing toward party day!\n"
            f"📅 **Party Date:** {party_date}\n"
            f"📍 **Venue:** {party_venue}\n\n"
            f"**Wrapped & Ready:**\n{create_progress_bar(wrapped, total)}\n"
        ),
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="📊 Breakdown (Spoiler-Free)",
        value=(
            f"• 🎁 **Wrapped & Packed:** {wrapped} / {total}\n"
            f"• 🛍️ **Purchased (Awaiting Wrap):** {bought} / {total}\n"
            f"• ⏳ **Still Shopping:** {total - wrapped - bought} / {total}"
        ),
        inline=False,
    )

    embed.set_footer(text="Santas can update their gift prep status privately in their DM with the bot!")
    return embed


def build_relay_embed(
    sender_role: str,
    content: str,
    sender_avatar_url: Optional[str] = None,
) -> discord.Embed:
    """Relay embed for anonymous messaging."""
    if sender_role.lower() == "santa":
        title = "📩 Anonymous Message from your Secret Santa"
        color = discord.Color.red()
        footer = "Click [Reply to Secret Santa ↩️] to answer anonymously!"
    else:
        title = "📩 Anonymous Reply from your Baby"
        color = discord.Color.green()
        footer = "Click [Ask Baby Anonymously ✉️] if you have more questions!"

    embed = discord.Embed(
        title=title,
        description=content,
        color=color,
    )
    if sender_avatar_url:
        embed.set_thumbnail(url=sender_avatar_url)
    embed.set_footer(text=footer)
    return embed


def build_admin_export_embed(pairings: list[dict[str, Any]]) -> discord.Embed:
    """Ephemeral cheat sheet for host."""
    embed = discord.Embed(
        title="🔒 Host Secret Santa Master Cheat Sheet",
        description="Confidential list of all pairings, gift tag codes, and statuses.",
        color=discord.Color.dark_grey(),
    )

    lines = []
    for i, p in enumerate(pairings, 1):
        santa = p.get("santa_name") or str(p["santa_id"])
        baby = p.get("baby_name") or str(p["baby_id"])
        code = p.get("gift_tag_code", "N/A")
        status = p.get("gift_status", "NOT_STARTED")
        lines.append(f"`{i:02d}.` **{santa}** ➡️ **{baby}** | Tag: `{code}` | Status: `{status}`")

    text = "\n".join(lines) if lines else "*No pairings generated yet.*"
    if len(text) > 4000:
        text = text[:3900] + "\n...[truncated]"

    embed.add_field(name="Pairings List", value=text, inline=False)
    embed.set_footer(text="Keep this strictly private!")
    return embed


def build_public_reminder_embed(
    session: dict[str, Any],
    participants: list[dict[str, Any]],
    custom_note: Optional[str] = None,
) -> discord.Embed:
    """Public announcement embed for countdown and periodic reminders."""
    status = session.get("status", "REGISTRATION")
    total = len(participants)
    party_date = session.get("party_date") or "Upcoming"
    party_venue = session.get("party_venue") or "Party Venue"

    if status == "REGISTRATION":
        embed = discord.Embed(
            title="⏰ Secret Santa Registration Reminder! 🎅",
            description=(
                "Don't miss out on our private Secret Santa game! "
                "Signups are currently open—make sure to join and fill out your wishlist."
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="👥 Currently Registered",
            value=f"**{total} Santas** have joined so far!",
            inline=True,
        )
        if session.get("signup_deadline"):
            embed.add_field(name="⏳ Sign-up Deadline", value=session["signup_deadline"], inline=True)
        embed.add_field(name="📅 Planned Party Date", value=party_date, inline=True)
        embed.set_footer(text="Click [Join Event 🎁] on the main registration message to participate!")
    else:  # IN_PROGRESS
        wrapped = sum(1 for p in participants if p.get("gift_status") in ("WRAPPED", "READY", "AT_PARTY"))
        embed = discord.Embed(
            title="⏰ Secret Santa Party Countdown & Prep Update! 🎅",
            description=(
                f"The countdown is on for our in-person holiday party!\n\n"
                f"📅 **Party Date:** {party_date}\n"
                f"📍 **Venue:** {party_venue}\n\n"
                f"**Preparation Progress:**\n{create_progress_bar(wrapped, total)}"
            ),
            color=discord.Color.red(),
        )
        embed.add_field(
            name="📦 Friendly Checklist for Santas",
            value=(
                "• Securely wrap your gift before the party.\n"
                "• Label with `To: [Baby Name]` and `Code: [Your Secret Code]`.\n"
                "• **Do not sign your real name!**\n"
                "• Click `Mark as Wrapped` in your DM with the bot once ready!"
            ),
            inline=False,
        )

    if custom_note:
        embed.add_field(name="📢 Message from the Host", value=custom_note, inline=False)

    return embed


def build_dm_reminder_embed(
    baby_name: str,
    gift_tag_code: str,
    party_date: Optional[str] = None,
    party_venue: Optional[str] = None,
    custom_note: Optional[str] = None,
) -> discord.Embed:
    """Targeted private reminder DM embed sent to an unwrapped Santa."""
    embed = discord.Embed(
        title="🎅 Secret Santa Check-In: Don't Forget Your Gift! 🎁",
        description=(
            f"Friendly reminder that you are the Secret Santa for **{baby_name}**!\n"
            "The in-person party is approaching, so make sure to get your gift ready and wrapped."
        ),
        color=discord.Color.gold(),
    )

    info_lines = [
        f"• **Target Baby:** {baby_name}",
        f"• **Secret Gift Code:** `{gift_tag_code}`",
    ]
    if party_date:
        info_lines.append(f"• **Party Date:** {party_date}")
    if party_venue:
        info_lines.append(f"• **Venue:** {party_venue}")

    embed.add_field(name="🏷️ Your Target Info", value="\n".join(info_lines), inline=False)
    embed.add_field(
        name="🏷️ Physical Wrapping Rule",
        value=(
            f"Write `To: {baby_name}` and `Code: {gift_tag_code}` on the wrapping paper "
            "so it can be identified under the tree without spoiling your identity!"
        ),
        inline=False,
    )

    if custom_note:
        embed.add_field(name="📢 Note from the Host", value=custom_note, inline=False)

    embed.set_footer(text="Use the buttons below to update your status once bought or wrapped!")
    return embed

