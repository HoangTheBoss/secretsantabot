"""Unit tests for proactive draw feasibility checking and diagnostics."""

import discord
import pytest
from unittest.mock import MagicMock
from src.services.matcher import validate_draw_feasibility
from src.ui.embeds import build_host_control_panel_embed
from src.ui.views import ExclusionManageView
from src.database.db import init_db
from src.database.repo import SantaRepository


@pytest.fixture
async def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_santa.db")
    await init_db(db_file)
    return SantaRepository(db_file)


def test_feasibility_participant_count_thresholds():
    # 0 participants
    r0 = validate_draw_feasibility([])
    assert r0.is_feasible is False
    assert r0.status == "NOT_ENOUGH_PARTICIPANTS"
    assert "No participants" in r0.headline

    # 1 participant
    r1 = validate_draw_feasibility([101])
    assert r1.is_feasible is False
    assert r1.status == "NOT_ENOUGH_PARTICIPANTS"
    assert "currently 1" in r1.headline

    # 2 participants
    r2 = validate_draw_feasibility([101, 102])
    assert r2.is_feasible is False
    assert r2.status == "NOT_ENOUGH_PARTICIPANTS"
    assert "currently 2" in r2.headline

    # Duplicate participants
    r_dup = validate_draw_feasibility([101, 102, 101])
    assert r_dup.is_feasible is False
    assert r_dup.status == "IMPOSSIBLE"
    assert "Duplicate" in r_dup.headline


def test_feasibility_three_participants_rule():
    names = {1: "Alice", 2: "Bob", 3: "Charlie"}
    # N=3 with no exclusions is READY
    r_ok = validate_draw_feasibility([1, 2, 3], exclusions=[], names=names)
    assert r_ok.is_feasible is True
    assert r_ok.status == "READY"

    # N=3 with any exclusion is mathematically IMPOSSIBLE
    r_fail = validate_draw_feasibility([1, 2, 3], exclusions=[(1, 2)], names=names)
    assert r_fail.is_feasible is False
    assert r_fail.status == "IMPOSSIBLE"
    assert "Alice" in r_fail.headline and "Bob" in r_fail.headline


def test_feasibility_isolated_participant():
    names = {1: "Alice", 2: "Bob", 3: "Charlie", 4: "David"}
    # Alice is excluded from everyone else -> 0 valid recipients
    exclusions = [(1, 2), (1, 3), (1, 4)]
    r = validate_draw_feasibility([1, 2, 3, 4], exclusions=exclusions, names=names)

    assert r.is_feasible is False
    assert r.status == "IMPOSSIBLE"
    assert "no allowed recipients" in r.headline
    assert any("Alice" in d and "0 valid recipients" in d or "no valid recipients" in d for d in r.details)


def test_feasibility_disconnected_subgroups():
    names = {1: "DevA", 2: "DevB", 3: "DevC", 4: "SalesA", 5: "SalesB", 6: "SalesC"}
    # Group 1 = [1, 2, 3], Group 2 = [4, 5, 6]
    # No member of Dev can gift Sales and vice versa
    cross_exclusions = [(u, v) for u in [1, 2, 3] for v in [4, 5, 6]]
    r = validate_draw_feasibility([1, 2, 3, 4, 5, 6], exclusions=cross_exclusions, names=names)

    assert r.is_feasible is False
    assert r.status == "IMPOSSIBLE"
    assert "disconnected groups" in r.headline
    assert len(r.details) > 0


def test_feasibility_tight_constraint_warning():
    # 5 participants where node 1 is excluded from 2 and 3
    # 1 can only gift 4 or 5
    names = {1: "Alice", 2: "Bob", 3: "Charlie", 4: "David", 5: "Emma"}
    # Let 1 be excluded from 2, 3 (1 can gift 4 or 5)
    # Let 4 be excluded from 2, 3
    exclusions = [(1, 2), (1, 3)]
    r = validate_draw_feasibility([1, 2, 3, 4, 5], exclusions=exclusions, names=names)

    assert r.is_feasible is True
    assert r.status in ("READY", "WARNING")


def test_host_control_panel_embed_diagnostics():
    session = {
        "status": "REGISTRATION",
        "budget": "$25",
        "party_date": "Dec 25",
        "party_venue": "Buda HQ",
        "signup_deadline_epoch": 1790000000,
    }
    participants = [
        {"user_id": 1, "display_name": "Alice", "gift_status": "PENDING"},
        {"user_id": 2, "display_name": "Bob", "gift_status": "PENDING"},
        {"user_id": 3, "display_name": "Charlie", "gift_status": "PENDING"},
    ]
    # Impossible: N=3 with exclusion
    exclusions = [(1, 2)]

    embed = build_host_control_panel_embed(
        session=session,
        participants=participants,
        exclusions=exclusions,
    )

    # Embed color should be RED for impossible
    assert embed.color == discord.Color.red()

    # Find feasibility field
    feas_field = next(f for f in embed.fields if "Matching Feasibility" in f.name)
    assert "IMPOSSIBLE" in feas_field.name
    assert "Alice" in feas_field.value and "Bob" in feas_field.value


def test_host_control_panel_embed_ready_state():
    session = {
        "status": "REGISTRATION",
        "budget": "$30",
        "party_date": "Dec 25",
        "party_venue": "Office",
    }
    participants = [
        {"user_id": 1, "display_name": "Alice", "gift_status": "PENDING"},
        {"user_id": 2, "display_name": "Bob", "gift_status": "PENDING"},
        {"user_id": 3, "display_name": "Charlie", "gift_status": "PENDING"},
        {"user_id": 4, "display_name": "David", "gift_status": "PENDING"},
    ]
    exclusions = [(1, 2)]  # Valid 4-person derangement exists

    embed = build_host_control_panel_embed(
        session=session,
        participants=participants,
        exclusions=exclusions,
    )

    # Embed color should be GREEN for ready
    assert embed.color == discord.Color.green()
    feas_field = next(f for f in embed.fields if "Matching Feasibility" in f.name)
    assert "READY" in feas_field.name
    assert "guaranteed" in feas_field.value


async def test_exclusion_manage_view_with_impossible_state(temp_repo):
    session_id = await temp_repo.create_session(guild_id=1, channel_id=2)

    # Register 3 participants
    await temp_repo.add_or_update_participant(session_id, user_id=10, username="user10", display_name="Ten")
    await temp_repo.add_or_update_participant(session_id, user_id=20, username="user20", display_name="Twenty")
    await temp_repo.add_or_update_participant(session_id, user_id=30, username="user30", display_name="Thirty")

    # Add impossible exclusion rule
    await temp_repo.add_exclusion(session_id, 10, 20)

    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.get_member.return_value = None

    view = ExclusionManageView(temp_repo, session_id)
    embed = await view.build_exclusions_embed(mock_guild)

    assert embed.color == discord.Color.red()
    feas_field = next(f for f in embed.fields if "Matching Feasibility" in f.name)
    assert "IMPOSSIBLE" in feas_field.name
    assert "Ten" in feas_field.value or "10" in feas_field.value
