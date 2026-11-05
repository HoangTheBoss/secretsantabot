"""Draw execution service shared between manual /secretsanta draw and automatic deadline trigger."""

import discord
import logging
from src.database.repo import SantaRepository
from src.services.matcher import generate_pairings, MatchingError
from src.ui.embeds import build_santa_dm_embed
from src.ui.views import SantaDmView

logger = logging.getLogger("secretsanta.draw_service")


async def execute_draw(
    bot: discord.Client,
    repo: SantaRepository,
    session_id: int,
    trigger_type: str = "MANUAL",  # 'MANUAL' or 'AUTOMATIC'
) -> tuple[bool, str, list[str]]:
    """
    Executes the pairing algorithm, stores results in DB, sends private DMs to Santas,
    and posts public announcement to the bound channel.

    Returns:
        (success: bool, message: str, failed_dm_names: list[str])
    """
    session = await repo.get_session_by_id(session_id)
    if not session:
        return False, "Session not found.", []

    participants = await repo.get_all_participants(session_id)
    user_ids = [p["user_id"] for p in participants]

    if len(user_ids) < 3:
        msg = f"Need at least 3 participants to draw pairs (currently have {len(user_ids)})."
        return False, msg, []

    exclusions = await repo.get_exclusions(session_id)

    try:
        pairings = generate_pairings(user_ids, exclusions=exclusions)
    except MatchingError as e:
        logger.error("Matching error during %s draw for session %s: %s", trigger_type, session_id, e)
        return False, f"Matching Failed: {e}", []

    # Save pairings & update status
    await repo.save_pairings(session_id, pairings)
    await repo.update_session_status(session_id, "IN_PROGRESS")

    part_map = {p["user_id"]: p for p in participants}
    failed_dms: list[str] = []

    # Dispatch private assignment DMs
    for santa_id, baby_id, gift_tag_code in pairings:
        santa_part = part_map.get(santa_id)
        baby_part = part_map.get(baby_id)
        if not santa_part or not baby_part:
            continue

        try:
            santa_user = await bot.fetch_user(santa_id)
            baby_user = await bot.fetch_user(baby_id)
            avatar_url = baby_user.display_avatar.url if baby_user else None

            embed = build_santa_dm_embed(
                baby_name=baby_part["display_name"],
                baby_username=baby_part["username"],
                avatar_url=avatar_url,
                wishlist=baby_part["wishlist"],
                dislikes=baby_part["dislikes"],
                offline_notes=baby_part["offline_notes"],
                gift_tag_code=gift_tag_code,
                budget=session.get("budget"),
                party_date=session.get("party_date"),
                party_venue=session.get("party_venue"),
                event_name=session.get("event_name"),
                logo_url=session.get("logo_url"),
                footer_text=session.get("footer_text"),
                theme_color=session.get("theme_color"),
            )
            view = SantaDmView(repo=repo, session_id=session_id, baby_id=baby_id)
            await santa_user.send(embed=embed, view=view)
        except Exception as e:
            logger.error("Failed to send assignment DM to %s: %s", santa_id, e)
            failed_dms.append(santa_part["display_name"])

    # Post public announcement in the bound channel
    channel_id = session.get("channel_id")
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            channel = None

    trigger_banner = "⏰ **Signup deadline has arrived! Automatic draw complete!** 🎅" if trigger_type == "AUTOMATIC" else "🎉 **The Secret Santa Draw is Complete!** 🎅"

    announcement = (
        f"{trigger_banner}\n\n"
        f"• **{len(pairings)} Santas** have received their secret targets in private DM!\n"
        f"• Check your Direct Messages for your target's wishlist and your secret physical gift tag code.\n"
        f"• Budget: **{session.get('budget', 'Unset')}** | Party Date: **{session.get('party_date', 'TBA')}**\n"
        f"• Happy gift hunting, and see everyone at the party! 🥂"
    )
    if failed_dms:
        announcement += f"\n\n⚠️ **Notice:** Could not deliver DMs to: {', '.join(failed_dms)}. Please check server privacy settings."

    if channel and isinstance(channel, discord.TextChannel):
        try:
            await channel.send(announcement)
        except Exception as e:
            logger.error("Failed to send draw announcement to channel %s: %s", channel_id, e)

    return True, announcement, failed_dms
