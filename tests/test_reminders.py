"""Unit tests for reminder queries and embeds."""

import pytest
from src.database.db import init_db
from src.database.repo import SantaRepository
from src.ui.embeds import build_public_reminder_embed, build_dm_reminder_embed


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
