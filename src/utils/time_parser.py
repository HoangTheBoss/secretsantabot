"""Parser for date, time, and relative duration strings into epoch timestamps (defaulting to Vietnam Time ICT / UTC+7)."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from src.config import DEFAULT_TIMEZONE


def parse_deadline(input_str: str) -> tuple[datetime, int, str]:
    """
    Parse a deadline string (relative or absolute) into timezone-aware datetime,
    epoch seconds, and human-readable string in Vietnam Time (ICT / UTC+7).

    Supports:
      - Relative: "3d", "7 days", "24h", "12 hours", "30m", "45 minutes"
      - Absolute: "YYYY-MM-DD HH:MM", "YYYY-MM-DD", "Dec 15 20:00", "Dec 15", "December 20, 2026 19:00"

    Returns:
        (target_datetime, epoch_timestamp_int, human_readable_string)

    Raises:
        ValueError: If input string cannot be parsed.
    """
    raw = input_str.strip()
    if not raw:
        raise ValueError("Deadline string cannot be empty.")

    now = datetime.now(DEFAULT_TIMEZONE)

    # Clean commas and extra spaces
    raw_clean = re.sub(r",\s*", " ", raw)
    # Normalize 1:30pm -> 1:30 PM, 1pm -> 1:00 PM
    raw_clean = re.sub(r"(\d{1,2}:\d{2})\s*(am|pm)\b", r"\1 \2", raw_clean, flags=re.I)
    raw_clean = re.sub(r"(?<!:)\b(\d{1,2})\s*(am|pm)\b", r"\1:00 \2", raw_clean, flags=re.I)
    raw_clean = re.sub(r"\s+", " ", raw_clean).strip()

    # 1. Check relative format: e.g. "3d", "5 days", "12h", "30m"
    rel_match = re.fullmatch(
        r"^(?:in\s+)?(\d+)\s*(d|day|days|h|hr|hrs|hour|hours|m|min|mins|minute|minutes)$",
        raw_clean,
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
        formatted = target_dt.strftime("%Y-%m-%d %H:%M ICT")
        return target_dt, epoch, formatted

    # 2. Check standard absolute formats with year
    formats_with_year = [
        # ISO / hyphen / slash
        ("%Y-%m-%d %H:%M", False),
        ("%Y-%m-%d %H:%M:%S", False),
        ("%Y/%m/%d %H:%M", False),
        ("%d/%m/%Y %H:%M", False),
        ("%d-%m-%Y %H:%M", False),
        ("%Y-%m-%d %I:%M %p", False),
        ("%Y/%m/%d %I:%M %p", False),
        ("%d/%m/%Y %I:%M %p", False),
        ("%d-%m-%Y %I:%M %p", False),
        ("%Y-%m-%d", True),
        ("%Y/%m/%d", True),
        ("%d/%m/%Y", True),
        ("%d-%m-%Y", True),
        # Month name + Day + Year + Time
        ("%b %d %Y %H:%M", False),
        ("%B %d %Y %H:%M", False),
        ("%b %d %Y %I:%M %p", False),
        ("%B %d %Y %I:%M %p", False),
        ("%d %b %Y %H:%M", False),
        ("%d %B %Y %H:%M", False),
        ("%d %b %Y %I:%M %p", False),
        ("%d %B %Y %I:%M %p", False),
        # Month name + Day + Time + Year
        ("%b %d %H:%M %Y", False),
        ("%B %d %H:%M %Y", False),
        ("%b %d %I:%M %p %Y", False),
        ("%B %d %I:%M %p %Y", False),
        ("%d %b %H:%M %Y", False),
        ("%d %B %H:%M %Y", False),
        ("%d %b %I:%M %p %Y", False),
        ("%d %B %I:%M %p %Y", False),
        # Date only
        ("%b %d %Y", True),
        ("%B %d %Y", True),
        ("%d %b %Y", True),
        ("%d %B %Y", True),
    ]

    for fmt, is_date_only in formats_with_year:
        try:
            parsed = datetime.strptime(raw_clean, fmt)
            if is_date_only:
                parsed = parsed.replace(hour=23, minute=59, second=59)
            target_dt = parsed.replace(tzinfo=DEFAULT_TIMEZONE)
            epoch = int(target_dt.timestamp())
            formatted = target_dt.strftime("%Y-%m-%d %H:%M ICT")
            return target_dt, epoch, formatted
        except ValueError:
            continue

    # 3. Formats where year is omitted (append current year at end)
    formats_without_year = [
        # Date + Time
        ("%b %d %H:%M %Y", False),
        ("%B %d %H:%M %Y", False),
        ("%b %d %I:%M %p %Y", False),
        ("%B %d %I:%M %p %Y", False),
        ("%d %b %H:%M %Y", False),
        ("%d %B %H:%M %Y", False),
        ("%d %b %I:%M %p %Y", False),
        ("%d %B %I:%M %p %Y", False),
        ("%m-%d %H:%M %Y", False),
        ("%m/%d %H:%M %Y", False),
        ("%d/%m %H:%M %Y", False),
        ("%d-%m %H:%M %Y", False),
        ("%m-%d %I:%M %p %Y", False),
        ("%m/%d %I:%M %p %Y", False),
        ("%d/%m %I:%M %p %Y", False),
        ("%d-%m %I:%M %p %Y", False),
        # Date only
        ("%b %d %Y", True),
        ("%B %d %Y", True),
        ("%d %b %Y", True),
        ("%d %B %Y", True),
        ("%m-%d %Y", True),
        ("%m/%d %Y", True),
    ]

    raw_with_year = f"{raw_clean} {now.year}"
    for fmt, is_date_only in formats_without_year:
        try:
            parsed = datetime.strptime(raw_with_year, fmt)
            # If already passed in current year, advance to next year
            target_dt_temp = parsed.replace(tzinfo=DEFAULT_TIMEZONE)
            if target_dt_temp < now:
                parsed = parsed.replace(year=now.year + 1)
            if is_date_only:
                parsed = parsed.replace(hour=23, minute=59, second=59)
            target_dt = parsed.replace(tzinfo=DEFAULT_TIMEZONE)
            epoch = int(target_dt.timestamp())
            formatted = target_dt.strftime("%Y-%m-%d %H:%M ICT")
            return target_dt, epoch, formatted
        except ValueError:
            continue

    raise ValueError(
        f"Could not parse deadline '{input_str}'.\n"
        "Supported formats (interpreted in Vietnam Time / ICT):\n"
        "• Relative: '3d', '7 days', '24h', '30m'\n"
        "• Date & Time: 'Dec 01 01:00', 'Dec 1 1:00 PM', '2026-12-10 20:00'\n"
        "• Date only: 'Dec 15', '2026-12-10' (defaults to end of day 23:59)"
    )



def format_discord_timestamp(epoch: int) -> str:
    """Format an epoch timestamp using Discord's dynamic local timestamp tags."""
    return f"<t:{epoch}:F> (<t:{epoch}:R>)"
