"""Unit tests for pair and group exclusion parsing, repository operations, and UI view."""

import pytest
from unittest.mock import MagicMock
import discord

from src.database.db import init_db
from src.database.repo import SantaRepository
from src.utils.exclusion_parser import parse_bulk_exclusions, resolve_token_to_user_id
from src.ui.views import ExclusionManageView


@pytest.fixture
async def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_exclusions.db")
    await init_db(db_file)
    return SantaRepository(db_file)


def test_resolve_token_various_formats():
    p_map = {"alice": 101, "bob_builder": 102}

    # Mentions
    assert resolve_token_to_user_id("<@123456789012345678>") == 123456789012345678
    assert resolve_token_to_user_id("<@!987654321098765432>") == 987654321098765432

    # Raw ID
    assert resolve_token_to_user_id("123456789012345678") == 123456789012345678

    # Participant map
    assert resolve_token_to_user_id("@Alice", participant_map=p_map) == 101
    assert resolve_token_to_user_id("bob_builder", participant_map=p_map) == 102

    # Unknown
    assert resolve_token_to_user_id("charlie", participant_map=p_map) is None
    assert resolve_token_to_user_id("") is None


def test_parse_bulk_exclusions_multiple_pairs_and_delimiters():
    participants = [
        {"user_id": 1, "username": "alice", "display_name": "Alice Wonderland"},
        {"user_id": 2, "username": "bob", "display_name": "Bob Builder"},
        {"user_id": 3, "username": "charlie", "display_name": "Charlie Chaplin"},
        {"user_id": 4, "username": "dave", "display_name": "Dave Grohl"},
        {"user_id": 5, "username": "eve", "display_name": "Eve Polastri"},
    ]

    # Multiline text with various delimiters
    raw_text = """
    Alice & Bob
    Charlie and Dave
    <@555>, <@666>
    Alice, Charlie, Eve
    LoneWolf
    """

    pairs, unresolved = parse_bulk_exclusions(raw_text, participants=participants)

    # Pairs expected:
    # 1. (1, 2) from Alice & Bob
    # 2. (3, 4) from Charlie and Dave
    # 3. (555, 666) from mentions
    # 4. Group (1, 3, 5): (1, 3), (1, 5), (3, 5)
    assert (1, 2) in pairs
    assert (3, 4) in pairs
    assert (555, 666) in pairs
    assert (1, 3) in pairs
    assert (1, 5) in pairs
    assert (3, 5) in pairs

    assert len(unresolved) == 1
    assert "LoneWolf" in unresolved[0]


def test_parse_bulk_exclusions_semicolon_separated():
    participants = [
        {"user_id": 10, "username": "user10", "display_name": "Ten"},
        {"user_id": 20, "username": "user20", "display_name": "Twenty"},
        {"user_id": 30, "username": "user30", "display_name": "Thirty"},
        {"user_id": 40, "username": "user40", "display_name": "Forty"},
    ]

    raw_text = "Ten, Twenty; Thirty ⛔ Forty"
    pairs, unresolved = parse_bulk_exclusions(raw_text, participants=participants)

    assert len(unresolved) == 0
    assert (10, 20) in pairs
    assert (30, 40) in pairs
    assert len(pairs) == 2


async def test_repo_add_exclusions_bulk_and_clear(temp_repo):
    session_id = await temp_repo.create_session(guild_id=1, channel_id=2)

    # Add 4 pairs
    pairs_to_add = [
        (10, 20),
        (30, 40),
        (20, 10),  # Duplicate flipped, should be normalized and deduplicated
        (50, 60),
    ]

    added = await temp_repo.add_exclusions_bulk(session_id, pairs_to_add)
    assert added == 3

    stored = await temp_repo.get_exclusions(session_id)
    assert len(stored) == 3
    assert (10, 20) in stored
    assert (30, 40) in stored
    assert (50, 60) in stored

    # Clear all
    cleared = await temp_repo.clear_all_exclusions(session_id)
    assert cleared == 3
    assert len(await temp_repo.get_exclusions(session_id)) == 0


async def test_exclusion_manage_view_and_embed_chunking(temp_repo):
    session_id = await temp_repo.create_session(guild_id=1, channel_id=2)

    # Populate 30 exclusion pairs to test chunking
    bulk_pairs = [(i, i + 100) for i in range(1, 31)]
    await temp_repo.add_exclusions_bulk(session_id, bulk_pairs)

    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.get_member.return_value = None

    view = ExclusionManageView(temp_repo, session_id)
    await view.setup_components(mock_guild)

    # View components check
    assert hasattr(view, "user_select")
    assert hasattr(view, "remove_select")
    # Remove select should have max 25 options (Discord limit)
    assert len(view.remove_select.options) == 25

    # Embed check
    embed = await view.build_exclusions_embed(mock_guild)
    assert "Current Exclusions (30)" in str(embed.fields[0].name)
    # Since chunk_size is 15, 30 lines should split into 2 fields
    assert len(embed.fields) == 2
    assert "Exclusions (cont.)" in embed.fields[1].name


async def test_exclusion_manage_view_button_callbacks_signature(temp_repo):
    from unittest.mock import AsyncMock

    session_id = await temp_repo.create_session(guild_id=1, channel_id=2)
    await temp_repo.add_exclusion(session_id, 10, 20)

    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.get_member.return_value = None

    view = ExclusionManageView(temp_repo, session_id)
    await view.setup_components(mock_guild)

    # Mock interaction
    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.guild = mock_guild
    mock_interaction.response = MagicMock()
    mock_interaction.response.edit_message = AsyncMock()
    mock_interaction.response.send_modal = AsyncMock()

    # 1. Test _on_refresh_button called with single argument (as discord.py does)
    await view._on_refresh_button(mock_interaction)
    mock_interaction.response.edit_message.assert_called_once()
    mock_interaction.response.edit_message.reset_mock()

    # 2. Test _on_clear_button called with single argument
    await view._on_clear_button(mock_interaction)
    mock_interaction.response.edit_message.assert_called_once()
    assert "Cleared all 1 exclusion rules" in mock_interaction.response.edit_message.call_args[1]["content"]
    mock_interaction.response.edit_message.reset_mock()

    # 3. Test _on_bulk_button called with single argument
    await view._on_bulk_button(mock_interaction)
    mock_interaction.response.send_modal.assert_called_once()

