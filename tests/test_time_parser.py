"""Unit tests for date & deadline parsing."""

import pytest
from datetime import datetime, timezone
from src.utils.time_parser import parse_deadline, format_discord_timestamp


def test_relative_days():
    dt, epoch, formatted = parse_deadline("3d")
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    # 3 days = 3 * 86400 = 259200 seconds
    diff = epoch - now_epoch
    assert 259100 <= diff <= 259300
    assert "ICT" in formatted


def test_relative_hours():
    dt, epoch, formatted = parse_deadline("12h")
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    diff = epoch - now_epoch
    assert 43100 <= diff <= 43300
    assert "ICT" in formatted


def test_vietnam_timezone_conversion():
    dt, epoch, formatted = parse_deadline("2026-12-25 18:00")
    assert "ICT" in formatted
    # 18:00 in UTC+7 is 11:00 in UTC
    utc_dt = dt.astimezone(timezone.utc)
    assert utc_dt.hour == 11
    assert utc_dt.day == 25



def test_relative_minutes():
    dt, epoch, formatted = parse_deadline("30m")
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    diff = epoch - now_epoch
    assert 1700 <= diff <= 1900


def test_absolute_date_and_time():
    dt, epoch, formatted = parse_deadline("2026-12-25 18:00")
    assert dt.year == 2026
    assert dt.month == 12
    assert dt.day == 25
    assert dt.hour == 18
    assert dt.minute == 0


def test_absolute_date_only_defaults_to_end_of_day():
    dt, epoch, formatted = parse_deadline("2026-12-25")
    assert dt.year == 2026
    assert dt.month == 12
    assert dt.day == 25
    assert dt.hour == 23
    assert dt.minute == 59


def test_month_day_time_formats():
    # User's exact case: Dec 01 01:00
    dt, epoch, formatted = parse_deadline("Dec 01 01:00")
    assert dt.month == 12
    assert dt.day == 1
    assert dt.hour == 1
    assert dt.minute == 0

    # With commas: Dec 1, 01:00
    dt2, _, _ = parse_deadline("Dec 1, 01:00")
    assert dt2.month == 12
    assert dt2.day == 1
    assert dt2.hour == 1

    # Day month time: 15 Dec 14:30
    dt3, _, _ = parse_deadline("15 Dec 14:30")
    assert dt3.month == 12
    assert dt3.day == 15
    assert dt3.hour == 14
    assert dt3.minute == 30

    # AM/PM format: Dec 1 1:00 PM
    dt4, _, _ = parse_deadline("Dec 1 1:00 PM")
    assert dt4.hour == 13

    # Shorthand AM/PM: Dec 1 1pm
    dt5, _, _ = parse_deadline("Dec 1 1pm")
    assert dt5.hour == 13


def test_invalid_deadline_raises_value_error():
    with pytest.raises(ValueError, match="Could not parse deadline"):
        parse_deadline("invalid-gibberish-string")


def test_discord_timestamp_format():
    tag = format_discord_timestamp(1766685600)
    assert "<t:1766685600:F>" in tag
    assert "<t:1766685600:R>" in tag
