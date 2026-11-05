"""Discord Embed generators for Buda Secret Santa."""

import discord
from typing import Any, Optional
from src.config import (
    DEFAULT_EVENT_NAME,
    DEFAULT_LOGO_URL,
    DEFAULT_BANNER_URL,
    DEFAULT_FOOTER_TEXT,
    DEFAULT_THEME_COLOR,
)


def resolve_color(color_str: Optional[str], default: discord.Color = discord.Color.red()) -> discord.Color:
    """Resolve a color name or hex code to a discord.Color."""
    if not color_str:
        return default
    clean = color_str.strip().upper()

    named_colors = {
        "RED": discord.Color.red(),
        "GREEN": discord.Color.green(),
        "GOLD": discord.Color.gold(),
        "YELLOW": discord.Color.yellow(),
        "BLUE": discord.Color.blue(),
        "BLURPLE": discord.Color.blurple(),
        "PURPLE": discord.Color.purple(),
        "DARK_RED": discord.Color.dark_red(),
        "TEAL": discord.Color.teal(),
        "ORANGE": discord.Color.orange(),
    }
    if clean in named_colors:
        return named_colors[clean]

    hex_clean = clean.lstrip("#")
    if len(hex_clean) == 6:
        try:
            return discord.Color(int(hex_clean, 16))
        except ValueError:
            pass

    return default


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

    event_name = session.get("event_name") or DEFAULT_EVENT_NAME
    default_c = discord.Color.green() if status == "REGISTRATION" else discord.Color.gold()
    color = resolve_color(session.get("theme_color") or DEFAULT_THEME_COLOR, default=default_c)

    embed = discord.Embed(
        title=f"🎄 {event_name} 🎅",
        description=(
            "Welcome to our private Secret Santa game! Sign up below, submit your wishlist, "
            "and get ready for our in-person holiday party.\n\n"
            "**Important:** Please ensure your server privacy settings allow Direct Messages "
            "so the bot can privately deliver your target and physical gift code!"
        ),
        color=color,
    )

    logo_url = session.get("logo_url") or DEFAULT_LOGO_URL or None
    banner_url = session.get("banner_url") or DEFAULT_BANNER_URL or None
    footer_text = session.get("footer_text") or DEFAULT_FOOTER_TEXT

    if logo_url:
        embed.set_thumbnail(url=logo_url)
    if banner_url:
        embed.set_image(url=banner_url)

    embed.add_field(name="💰 Budget Limit", value=budget, inline=True)
    embed.add_field(name="📅 Party Date", value=party_date, inline=True)
    embed.add_field(name="📍 Party Venue", value=party_venue, inline=True)

    # Deadline field
    deadline_epoch = session.get("signup_deadline_epoch")
    if deadline_epoch:
        deadline_val = f"<t:{deadline_epoch}:F>\n⏳ **Draws:** <t:{deadline_epoch}:R>"
        if session.get("auto_draw", 1):
            deadline_val += " *(Auto-draw enabled)*"
        embed.add_field(name="⏰ Sign-Up Deadline", value=deadline_val, inline=False)
    elif session.get("signup_deadline"):
        embed.add_field(name="⏰ Sign-Up Deadline", value=session["signup_deadline"], inline=False)

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

    if logo_url:
        embed.set_footer(text=f"{footer_text} • Click [Join 🎁] to participate!", icon_url=logo_url)
    else:
        embed.set_footer(text=f"{footer_text} • Click [Join 🎁] to participate!")

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
    event_name: Optional[str] = None,
    logo_url: Optional[str] = None,
    footer_text: Optional[str] = None,
    theme_color: Optional[str] = None,
) -> discord.Embed:
    """Secret DM embed sent to Santa."""
    name_display = event_name or DEFAULT_EVENT_NAME
    color = resolve_color(theme_color or DEFAULT_THEME_COLOR, default=discord.Color.red())
    resolved_logo = logo_url or DEFAULT_LOGO_URL or None
    resolved_footer = footer_text or DEFAULT_FOOTER_TEXT

    embed = discord.Embed(
        title=f"🎅 Shh! Your {name_display} Assignment is Here!",
        description=(
            f"You have been secretly chosen as the Santa for **{baby_name}** (@{baby_username})!\n"
            "Keep this strictly confidential until the in-person party!"
        ),
        color=color,
    )

    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    if resolved_logo:
        embed.set_author(name=name_display, icon_url=resolved_logo)

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

    footer_str = f"{resolved_footer} • Need to ask a size or preference? Click [Ask Baby Anonymously ✉️] below!"
    if resolved_logo:
        embed.set_footer(text=footer_str, icon_url=resolved_logo)
    else:
        embed.set_footer(text=footer_str)
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

    event_name = session.get("event_name") or DEFAULT_EVENT_NAME
    color = resolve_color(session.get("theme_color") or DEFAULT_THEME_COLOR, default=discord.Color.blurple())
    logo_url = session.get("logo_url") or DEFAULT_LOGO_URL or None
    banner_url = session.get("banner_url") or DEFAULT_BANNER_URL or None
    footer_text = session.get("footer_text") or DEFAULT_FOOTER_TEXT

    embed = discord.Embed(
        title=f"🎁 {event_name} Preparation Dashboard",
        description=(
            f"Here is how our group is progressing toward party day!\n"
            f"📅 **Party Date:** {party_date}\n"
            f"📍 **Venue:** {party_venue}\n\n"
            f"**Wrapped & Ready:**\n{create_progress_bar(wrapped, total)}\n"
        ),
        color=color,
    )

    if logo_url:
        embed.set_thumbnail(url=logo_url)
    if banner_url:
        embed.set_image(url=banner_url)

    embed.add_field(
        name="📊 Breakdown (Spoiler-Free)",
        value=(
            f"• 🎁 **Wrapped & Packed:** {wrapped} / {total}\n"
            f"• 🛍️ **Purchased (Awaiting Wrap):** {bought} / {total}\n"
            f"• ⏳ **Still Shopping:** {total - wrapped - bought} / {total}"
        ),
        inline=False,
    )

    if logo_url:
        embed.set_footer(
            text=f"{footer_text} • Santas can update their gift prep status privately in their DM with the bot!",
            icon_url=logo_url,
        )
    else:
        embed.set_footer(
            text=f"{footer_text} • Santas can update their gift prep status privately in their DM with the bot!"
        )
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

    event_name = session.get("event_name") or DEFAULT_EVENT_NAME
    logo_url = session.get("logo_url") or DEFAULT_LOGO_URL or None
    banner_url = session.get("banner_url") or DEFAULT_BANNER_URL or None
    footer_text = session.get("footer_text") or DEFAULT_FOOTER_TEXT
    theme_color = session.get("theme_color") or DEFAULT_THEME_COLOR

    if status == "REGISTRATION":
        color = resolve_color(theme_color, default=discord.Color.gold())
        embed = discord.Embed(
            title=f"⏰ {event_name} Registration Reminder! 🎅",
            description=(
                f"Don't miss out on {event_name}! "
                "Signups are currently open—make sure to join and fill out your wishlist."
            ),
            color=color,
        )
        embed.add_field(
            name="👥 Currently Registered",
            value=f"**{total} Santas** have joined so far!",
            inline=True,
        )
        if session.get("signup_deadline"):
            embed.add_field(name="⏳ Sign-up Deadline", value=session["signup_deadline"], inline=True)
        embed.add_field(name="📅 Planned Party Date", value=party_date, inline=True)
        if logo_url:
            embed.set_footer(
                text=f"{footer_text} • Click [Join Event 🎁] on the main registration message to participate!",
                icon_url=logo_url,
            )
        else:
            embed.set_footer(
                text=f"{footer_text} • Click [Join Event 🎁] on the main registration message to participate!"
            )
    else:  # IN_PROGRESS
        color = resolve_color(theme_color, default=discord.Color.red())
        wrapped = sum(1 for p in participants if p.get("gift_status") in ("WRAPPED", "READY", "AT_PARTY"))
        embed = discord.Embed(
            title=f"⏰ {event_name} Party Countdown & Prep Update! 🎅",
            description=(
                f"The countdown is on for our in-person holiday party!\n\n"
                f"📅 **Party Date:** {party_date}\n"
                f"📍 **Venue:** {party_venue}\n\n"
                f"**Preparation Progress:**\n{create_progress_bar(wrapped, total)}"
            ),
            color=color,
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
        if logo_url:
            embed.set_footer(
                text=f"{footer_text} • Keep your assignments secret until the party!",
                icon_url=logo_url,
            )
        else:
            embed.set_footer(
                text=f"{footer_text} • Keep your assignments secret until the party!"
            )

    if logo_url:
        embed.set_thumbnail(url=logo_url)
    if banner_url:
        embed.set_image(url=banner_url)

    if custom_note:
        embed.add_field(name="📢 Message from the Host", value=custom_note, inline=False)

    return embed


def build_milestone_reminder_embed(
    session: dict[str, Any],
    participants: list[dict[str, Any]],
    milestone_title: str,
    color: discord.Color,
) -> discord.Embed:
    """Escalating reminder embed sent to the channel as the signup deadline approaches."""
    total = len(participants)
    deadline_epoch = session.get("signup_deadline_epoch")
    time_display = f"<t:{deadline_epoch}:F>\n⏳ **Draw executes:** <t:{deadline_epoch}:R>" if deadline_epoch else "Soon"
    event_name = session.get("event_name") or DEFAULT_EVENT_NAME
    logo_url = session.get("logo_url") or DEFAULT_LOGO_URL or None
    footer_text = session.get("footer_text") or DEFAULT_FOOTER_TEXT

    embed = discord.Embed(
        title=f"{milestone_title} • {event_name}",
        description=(
            "The sign-up deadline is fast approaching! Once the timer expires, "
            "registration will be locked and pairings will be drawn automatically.\n\n"
            f"⏰ **Deadline:** {time_display}\n"
            f"👥 **Confirmed Santas:** **{total} participants**"
        ),
        color=color,
    )
    if logo_url:
        embed.set_thumbnail(url=logo_url)
        embed.set_footer(
            text=f"{footer_text} • Click [Join Event 🎁] on the registration message above to participate!",
            icon_url=logo_url,
        )
    else:
        embed.set_footer(text=f"{footer_text} • Click [Join Event 🎁] on the registration message above to participate!")
    return embed


def build_dm_reminder_embed(
    baby_name: str,
    gift_tag_code: str,
    party_date: Optional[str] = None,
    party_venue: Optional[str] = None,
    custom_note: Optional[str] = None,
    event_name: Optional[str] = None,
    logo_url: Optional[str] = None,
    footer_text: Optional[str] = None,
    theme_color: Optional[str] = None,
) -> discord.Embed:
    """Targeted private reminder DM embed sent to an unwrapped Santa."""
    name_display = event_name or DEFAULT_EVENT_NAME
    color = resolve_color(theme_color or DEFAULT_THEME_COLOR, default=discord.Color.gold())
    resolved_logo = logo_url or DEFAULT_LOGO_URL or None
    resolved_footer = footer_text or DEFAULT_FOOTER_TEXT

    embed = discord.Embed(
        title=f"🎅 {name_display} Check-In: Don't Forget Your Gift! 🎁",
        description=(
            f"Friendly reminder that you are the Secret Santa for **{baby_name}**!\n"
            "The in-person party is approaching, so make sure to get your gift ready and wrapped."
        ),
        color=color,
    )

    if resolved_logo:
        embed.set_author(name=name_display, icon_url=resolved_logo)

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

    footer_str = f"{resolved_footer} • Use the buttons below to update your status once bought or wrapped!"
    if resolved_logo:
        embed.set_footer(text=footer_str, icon_url=resolved_logo)
    else:
        embed.set_footer(text=footer_str)
    return embed

