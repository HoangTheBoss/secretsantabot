"""Unit tests for reminder queries and embeds."""

import pytest
from src.database.db import init_db
from src.database.repo import SantaRepository
from src.ui.embeds import (
    build_public_reminder_embed,
    build_dm_reminder_embed,
    build_milestone_reminder_embed,
)



@pytest.fixture
async def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_reminders.db")
    await init_db(db_file)
    return SantaRepository(db_file)


async def test_unwrapped_pairings_query(temp_repo):
    session_id = await temp_repo.create_session(guild_id=111, channel_id=222)
    await temp_repo.update_session_status(session_id, "IN_PROGRESS")

    # Add 3 participants
    await temp_repo.add_or_update_participant(session_id, 1, "alice", "Alice")
    await temp_repo.add_or_update_participant(session_id, 2, "bob", "Bob")
    await temp_repo.add_or_update_participant(session_id, 3, "charlie", "Charlie")

    # Pairings: 1 -> 2, 2 -> 3, 3 -> 1
    await temp_repo.save_pairings(session_id, [
        (1, 2, "TAG-1"),
        (2, 3, "TAG-2"),
        (3, 1, "TAG-3"),
    ])

    # Initially, all 3 are unwrapped
    unwrapped = await temp_repo.get_unwrapped_pairings(session_id)
    assert len(unwrapped) == 3

    # Santa 1 marks as WRAPPED
    await temp_repo.update_gift_status(session_id, 1, "WRAPPED")

    # Now only 2 and 3 should be in unwrapped list
    unwrapped_after = await temp_repo.get_unwrapped_pairings(session_id)
    assert len(unwrapped_after) == 2
    santa_ids = [p["santa_id"] for p in unwrapped_after]
    assert 1 not in santa_ids
    assert 2 in santa_ids
    assert 3 in santa_ids

    # Update reminder timestamp
    await temp_repo.update_pairing_reminded(session_id, 2)
    await temp_repo.update_session_reminded(session_id)


def test_public_reminder_embeds():
    session = {
        "status": "REGISTRATION",
        "party_date": "Dec 24, 2026",
        "party_venue": "Alice's House",
        "signup_deadline": "Dec 10",
    }
    participants = [{"display_name": "Alice"}, {"display_name": "Bob"}]

    embed_reg = build_public_reminder_embed(session, participants, custom_note="Don't forget to join!")
    assert "Registration Reminder" in embed_reg.title
    assert "Don't forget to join!" in str(embed_reg.fields)

    # In progress status
    session["status"] = "IN_PROGRESS"
    embed_prog = build_public_reminder_embed(session, participants)
    assert "Party Countdown" in embed_prog.title


def test_dm_reminder_embed():
    embed = build_dm_reminder_embed(
        baby_name="Bob",
        gift_tag_code="POLAR-99",
        party_date="Dec 24, 2026",
        party_venue="Alice's Place",
        custom_note="Wrap tightly!",
    )
    assert "Bob" in embed.description
    assert "POLAR-99" in str(embed.fields)
    assert "Wrap tightly!" in str(embed.fields)


async def test_milestone_tracking_and_embed(temp_repo):
    import discord

    session_id = await temp_repo.create_session(
        guild_id=123,
        channel_id=456,
        signup_deadline="2026-12-10 20:00 ICT",
        signup_deadline_epoch=1765371600,
    )

    # Add milestone '24h'
    await temp_repo.add_session_milestone(session_id, "24h")
    session = await temp_repo.get_session_by_id(session_id)
    assert "24h" in session["triggered_milestones"]

    # Add milestone '2h'
    await temp_repo.add_session_milestone(session_id, "2h")
    session2 = await temp_repo.get_session_by_id(session_id)
    assert "24h" in session2["triggered_milestones"]
    assert "2h" in session2["triggered_milestones"]

    embed = build_milestone_reminder_embed(
        session=session2,
        participants=[{"display_name": "Alice"}],
        milestone_title="🚨 Urgent: 2 Hours Left!",
        color=discord.Color.red(),
    )
    assert "Urgent: 2 Hours Left!" in embed.title
    assert "1765371600" in embed.description


async def test_unsetup_sessions_omitted_from_active_sessions(temp_repo):
    # Session 1: DRAFT without card
    s1 = await temp_repo.create_session(guild_id=1, channel_id=10, status="DRAFT")

    # Session 2: REGISTRATION but registration_message_id is NULL (not finished setup)
    s2 = await temp_repo.create_session(guild_id=2, channel_id=20, status="REGISTRATION")

    # Session 3: REGISTRATION and fully set up with card
    s3 = await temp_repo.create_session(guild_id=3, channel_id=30, status="REGISTRATION")
    await temp_repo.update_registration_message_id(s3, 999001)

    # Session 4: COMPLETED
    s4 = await temp_repo.create_session(guild_id=4, channel_id=40, status="COMPLETED")
    await temp_repo.update_registration_message_id(s4, 999002)

    active = await temp_repo.get_all_active_sessions()
    active_ids = [s["id"] for s in active]
    assert s1 not in active_ids
    assert s2 not in active_ids
    assert s4 not in active_ids
    assert s3 in active_ids
    assert len(active) == 1


def test_parse_sqlite_timestamp():
    from src.cogs.reminder_cog import parse_sqlite_timestamp
    from datetime import datetime, timezone

    assert parse_sqlite_timestamp(None) is None
    assert parse_sqlite_timestamp("") is None

    # SQLite standard CURRENT_TIMESTAMP string format
    ts_str = "2026-11-05 15:30:45"
    dt = parse_sqlite_timestamp(ts_str)
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 11
    assert dt.day == 5
    assert dt.hour == 15
    assert dt.minute == 30
    assert dt.second == 45
    assert dt.tzinfo == timezone.utc

    # ISO string format
    iso_str = "2026-12-25T10:00:00.123456"
    dt_iso = parse_sqlite_timestamp(iso_str)
    assert dt_iso is not None
    assert dt_iso.year == 2026
    assert dt_iso.month == 12
    assert dt_iso.day == 25
    assert dt_iso.hour == 10

    # datetime object
    dt_obj = datetime(2026, 1, 1, 12, 0, 0)
    assert parse_sqlite_timestamp(dt_obj).tzinfo == timezone.utc


async def test_process_session_routine_update_timing(temp_repo):
    from unittest.mock import AsyncMock, MagicMock
    from datetime import datetime, timezone, timedelta
    from src.cogs.reminder_cog import ReminderCog

    import discord

    mock_bot = MagicMock()
    mock_bot.wait_until_ready = AsyncMock()
    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.send = AsyncMock()
    mock_channel.name = "santa-channel"
    mock_bot.get_channel.return_value = mock_channel

    cog = ReminderCog(bot=mock_bot, repo=temp_repo)

    # 1. Session with registration_message_id is None -> MUST be skipped
    unsetup_session = {
        "id": 100,
        "channel_id": 999,
        "status": "REGISTRATION",
        "registration_message_id": None,
    }
    await cog._process_session_routine_update(unsetup_session)
    mock_channel.send.assert_not_called()

    # 2. Session reminded 1 hour ago (within 24h interval) -> MUST be skipped
    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    recent_session = {
        "id": 101,
        "channel_id": 999,
        "status": "REGISTRATION",
        "registration_message_id": 12345,
        "last_reminded_at": recent_ts,
        "created_at": recent_ts,
    }
    await cog._process_session_routine_update(recent_session)
    mock_channel.send.assert_not_called()

    # 3. Session created/reminded 25 hours ago -> SHOULD send reminder!
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
    old_session = {
        "id": 102,
        "channel_id": 999,
        "status": "REGISTRATION",
        "registration_message_id": 12345,
        "last_reminded_at": old_ts,
        "created_at": old_ts,
    }
    await cog._process_session_routine_update(old_session)
    assert mock_channel.send.called
    cog.cog_unload()


