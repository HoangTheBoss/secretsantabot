"""Unit tests for SQLite repository operations."""

import pytest
import os
from src.database.db import init_db
from src.database.repo import SantaRepository


@pytest.fixture
async def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_santa.db")
    await init_db(db_file)
    return SantaRepository(db_file)


async def test_session_lifecycle(temp_repo):
    session_id = await temp_repo.create_session(
        guild_id=12345,
        channel_id=67890,
        budget="$30",
        party_date="2026-12-24 19:00",
        party_venue="Alice's Home",
    )
    assert session_id > 0

    session = await temp_repo.get_active_session(12345)
    assert session is not None
    assert session["id"] == session_id
    assert session["budget"] == "$30"
    assert session["status"] == "REGISTRATION"

    # Add participant
    await temp_repo.add_or_update_participant(
        session_id=session_id,
        user_id=101,
        username="alice_u",
        display_name="Alice",
        wishlist="Coffee beans",
        dislikes="Peanuts",
        offline_notes="Prefers hot chocolate",
        dm_verified=True,
    )

    participants = await temp_repo.get_all_participants(session_id)
    assert len(participants) == 1
    assert participants[0]["display_name"] == "Alice"
    assert participants[0]["wishlist"] == "Coffee beans"

    # Add exclusion
    await temp_repo.add_exclusion(session_id, 101, 102)
    exclusions = await temp_repo.get_exclusions(session_id)
    assert exclusions == [(101, 102)]

    # Remove exclusion
    removed = await temp_repo.remove_exclusion(session_id, 102, 101)
    assert removed is True
    assert len(await temp_repo.get_exclusions(session_id)) == 0


async def test_pairings_and_relay(temp_repo):
    session_id = await temp_repo.create_session(guild_id=999, channel_id=888)

    await temp_repo.add_or_update_participant(session_id, 1, "s_alice", "Alice")
    await temp_repo.add_or_update_participant(session_id, 2, "s_bob", "Bob")
    await temp_repo.add_or_update_participant(session_id, 3, "s_charlie", "Charlie")

    # Save pairings: 1 -> 2, 2 -> 3, 3 -> 1
    pairings = [(1, 2, "POLAR-1"), (2, 3, "RUDOLPH-2"), (3, 1, "FROSTY-3")]
    await temp_repo.save_pairings(session_id, pairings)

    # Fetch pairing for Santa 1 (target is 2 / Bob)
    pairing = await temp_repo.get_pairing_for_santa(session_id, 1)
    assert pairing is not None
    assert pairing["baby_id"] == 2
    assert pairing["baby_display_name"] == "Bob"
    assert pairing["gift_tag_code"] == "POLAR-1"

    # Test reverse lookup for relay: who is the Santa for Baby 2? (It's 1)
    for_baby = await temp_repo.get_pairing_for_baby(session_id, 2)
    assert for_baby is not None
    assert for_baby["santa_id"] == 1

    # Log relay message
    msg_id = await temp_repo.log_relay_message(
        session_id=session_id,
        santa_id=1,
        baby_id=2,
        direction="SANTA_TO_BABY",
        content="Do you drink coffee?",
    )
    assert msg_id > 0


async def test_auto_draw_deadline_repo(temp_repo):
    # Create session with past deadline (epoch 1000) but no registration card yet
    session_id = await temp_repo.create_session(
        guild_id=777,
        channel_id=888,
        signup_deadline="2026-12-01 20:00",
        signup_deadline_epoch=1000,
        auto_draw=True,
    )

    # Before registration_message_id is set, it must not be picked up
    due_uninitialized = await temp_repo.get_due_auto_draw_sessions(current_epoch=2000)
    assert len(due_uninitialized) == 0

    # Initialize registration message ID
    await temp_repo.update_registration_message_id(session_id, 987654321)

    # Current epoch is 2000 (after deadline)
    due = await temp_repo.get_due_auto_draw_sessions(current_epoch=2000)
    assert len(due) == 1
    assert due[0]["id"] == session_id

    # Current epoch is 500 (before deadline)
    due_early = await temp_repo.get_due_auto_draw_sessions(current_epoch=500)
    assert len(due_early) == 0

    # If auto_draw disabled, it should not appear
    await temp_repo.update_session_details(session_id, auto_draw=False)
    due_disabled = await temp_repo.get_due_auto_draw_sessions(current_epoch=2000)
    assert len(due_disabled) == 0

    # Check updated session info
    updated = await temp_repo.get_session_by_id(session_id)
    assert updated["registration_message_id"] == 987654321

    # Test clearing fields via update_session_details
    await temp_repo.update_session_details(
        session_id,
        signup_deadline=None,
        signup_deadline_epoch=None,
        auto_draw=False,
    )
    cleared = await temp_repo.get_session_by_id(session_id)
    assert cleared["signup_deadline"] is None
    assert cleared["signup_deadline_epoch"] is None
    assert cleared["auto_draw"] == 0

    await temp_repo.archive_or_cancel_session(session_id, status="CANCELLED")
    cancelled = await temp_repo.get_active_session(777)
    assert cancelled is None



