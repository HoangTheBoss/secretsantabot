"""Utility for parsing bulk pair and group exclusion rules from text or modal input."""

import re
import itertools
from typing import Optional, Any
import discord

MENTION_REGEX = re.compile(r"<@!?(\d+)>")
DIGIT_REGEX = re.compile(r"^\d{15,22}$")
DELIMITER_REGEX = re.compile(r"[,;&+]|\band\b|\bwith\b|\bto\b|⛔", re.IGNORECASE)


def resolve_token_to_user_id(
    token: str,
    guild: Optional[discord.Guild] = None,
    participant_map: Optional[dict[str, int]] = None,
) -> Optional[int]:
    """Resolve a mention, raw ID, username, or display name to a Discord user ID."""
    clean = token.strip().lstrip("@")
    if not clean:
        return None

    # 1. Mention format (<@123...> or <@!123...>)
    m = MENTION_REGEX.search(token)
    if m:
        return int(m.group(1))

    # 2. Raw Discord Snowflake ID
    if DIGIT_REGEX.match(clean):
        return int(clean)

    token_lower = clean.lower()

    # 3. Match against session participants (fast dictionary lookup)
    if participant_map and token_lower in participant_map:
        return participant_map[token_lower]

    # 4. Match against guild members cache
    if guild:
        for member in guild.members:
            if member.name.lower() == token_lower:
                return member.id
            if member.display_name.lower() == token_lower:
                return member.id
            if member.global_name and member.global_name.lower() == token_lower:
                return member.id

    return None


def parse_bulk_exclusions(
    raw_text: str,
    guild: Optional[discord.Guild] = None,
    participants: Optional[list[dict[str, Any]]] = None,
) -> tuple[list[tuple[int, int]], list[str]]:
    """
    Parse multiline text containing pairs or groups of participants to exclude.

    Each line can contain 2 or more members separated by commas, semicolons, '&', 'and', etc.
    Mentions, user IDs, usernames, and display names are supported.

    Returns:
        (valid_pairs, unresolved_lines)
        valid_pairs: list of unique (low_id, high_id) tuples.
        unresolved_lines: list of input lines that couldn't be resolved to >= 2 members.
    """
    participant_map: dict[str, int] = {}
    if participants:
        for p in participants:
            uid = p.get("user_id")
            if not uid:
                continue
            if p.get("username"):
                participant_map[p["username"].lower()] = uid
            if p.get("display_name"):
                participant_map[p["display_name"].lower()] = uid

    raw_lines = [
        line.strip()
        for chunk in raw_text.split("\n")
        for line in chunk.split(";")
        if line.strip()
    ]

    pairs_set: set[tuple[int, int]] = set()
    unresolved_lines: list[str] = []

    for line in raw_lines:
        tokens = [t.strip() for t in DELIMITER_REGEX.split(line) if t.strip()]
        resolved_ids: list[int] = []

        for t in tokens:
            uid = resolve_token_to_user_id(t, guild=guild, participant_map=participant_map)
            if uid and uid not in resolved_ids:
                resolved_ids.append(uid)

        if len(resolved_ids) >= 2:
            for a, b in itertools.combinations(resolved_ids, 2):
                if a != b:
                    low, high = sorted([a, b])
                    pairs_set.add((low, high))
        else:
            unresolved_lines.append(line)

    return sorted(list(pairs_set)), unresolved_lines
