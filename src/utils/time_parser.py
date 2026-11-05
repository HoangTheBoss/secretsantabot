"""Parser for date, time, and relative duration strings into epoch timestamps."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional


def parse_deadline(input_str: str) -> tuple[datetime, int, str]:
    """
    Parse a deadline string (relative or absolute) into UTC datetime, epoch seconds, and display string.

    Supports:
      - Relative: "3d", "7 days", "24h", "12 hours", "30m", "45 minutes"
      - Absolute: "YYYY-MM-DD HH:MM", "YYYY-MM-DD", "Dec 15 20:00", "Dec 15", "December 20, 2026 19:00"

    Returns:
        (target_datetime_utc, epoch_timestamp_int, human_readable_string)

    Raises:
        ValueError: If input string cannot be parsed.
    """
    raw = input_str.strip()
    if not raw:
        raise ValueError("Deadline string cannot be empty.")

    now = datetime.now(timezone.utc)

    # 1. Check relative format: e.g. "3d", "5 days", "12h", "30m"
    rel_match = re.fullmatch(
        r"^(?:in\s+)?(\d+)\s*(d|day|days|h|hr|hrs|hour|hours|m|min|mins|minute|minutes)$",
        raw,
        re.IGNORECASE,
    )
    if rel_match:
        qty = int(rel_match.group(1))
        unit = rel_match.group(2).lower()
        if unit.startswith("d"):
            delta = timedelta(days=qty)
        elif unit.startswith("h"):
            delta = timedelta(hours=qty)
        else:
            delta = timedelta(minutes=qty)

        target_dt = now + delta
        epoch = int(target_dt.timestamp())
        formatted = target_dt.strftime("%Y-%m-%d %H:%M UTC")
        return target_dt, epoch, formatted

    # 2. Check standard absolute formats
    formats_with_year = [
        ("%Y-%m-%d %H:%M", False),
        ("%Y-%m-%d %H:%M:%S", False),
        ("%Y-%m-%d", True),
        ("%b %d %Y %H:%M", False),
        ("%B %d %Y %H:%M", False),
        ("%b %d %Y", True),
        ("%B %d %Y", True),
    ]

    for fmt, is_date_only in formats_with_year:
        try:
            parsed = datetime.strptime(raw, fmt)
            if is_date_only:
                parsed = parsed.replace(hour=23, minute=59, second=59)
            target_dt = parsed.replace(tzinfo=timezone.utc)
            epoch = int(target_dt.timestamp())
            formatted = target_dt.strftime("%Y-%m-%d %H:%M UTC")
            return target_dt, epoch, formatted
        except ValueError:
            continue

    # 3. Formats where year is omitted (append current year to avoid ambiguous year warning)
    formats_without_year = [
        ("%b %d %H:%M", "%b %d %Y %H:%M", False),
        ("%B %d %H:%M", "%B %d %Y %H:%M", False),
        ("%b %d", "%b %d %Y", True),
        ("%B %d", "%B %d %Y", True),
    ]

    for _, full_fmt, is_date_only in formats_without_year:
        try:
            raw_with_year = f"{raw} {now.year}"
            parsed = datetime.strptime(raw_with_year, full_fmt)
            if parsed.replace(tzinfo=timezone.utc) < now:
                parsed = parsed.replace(year=now.year + 1)
            if is_date_only:
                parsed = parsed.replace(hour=23, minute=59, second=59)
            target_dt = parsed.replace(tzinfo=timezone.utc)
            epoch = int(target_dt.timestamp())
            formatted = target_dt.strftime("%Y-%m-%d %H:%M UTC")
            return target_dt, epoch, formatted
        except ValueError:
            continue

    raise ValueError(
        f"Could not parse deadline '{input_str}'.\n"
        "Supported formats:\n"
        "• Relative: '3d', '7 days', '24h', '30m'\n"
        "• Absolute: '2026-12-10 20:00', '2026-12-10', 'Dec 15 20:00', 'Dec 15'"
    )


def format_discord_timestamp(epoch: int) -> str:
    """Format an epoch timestamp using Discord's dynamic local timestamp tags."""
    return f"<t:{epoch}:F> (<t:{epoch}:R>)"
