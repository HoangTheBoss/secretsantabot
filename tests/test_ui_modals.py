"""Unit tests for UI modals and view validation."""

import pytest
from src.database.db import init_db
from src.database.repo import SantaRepository
from src.ui.modals import CreatePollModal, DeadlineModal


@pytest.fixture
async def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_ui.db")
    await init_db(db_file)
    return SantaRepository(db_file)


def test_create_poll_modal_init():
    modal = CreatePollModal(target_channel_id=12345)
    assert modal.target_channel_id == 12345
    assert len(modal.children) == 2  # question_input, options_input


def test_build_poll_embed():
    from src.ui.embeds import build_poll_embed, POLL_NUMBER_EMOJIS

    options = ["$20 - $30", "$30 - $50", "$50+"]
    embed, emojis = build_poll_embed(question="What is the budget ceiling?", options=options)

    assert "What is the budget ceiling?" in embed.title
    assert emojis == ["1️⃣", "2️⃣", "3️⃣"]
    for emoji in emojis:
        assert emoji in embed.description
    for opt in options:
        assert opt in embed.description
    assert "React below to cast or change your vote!" in embed.footer.text


def test_build_poll_embed_up_to_10_options():
    from src.ui.embeds import build_poll_embed, POLL_NUMBER_EMOJIS

    options = [f"Option {i}" for i in range(1, 11)]
    embed, emojis = build_poll_embed(question="Vote for date", options=options)

    assert len(emojis) == 10
    assert emojis == POLL_NUMBER_EMOJIS
    assert "🔟" in embed.description


async def test_create_poll_modal_on_submit():
    from unittest.mock import AsyncMock, MagicMock
    import discord

    modal = CreatePollModal(target_channel_id=999)
    modal.question_input._value = "Party Date?"
    modal.options_input._value = "Dec 20\nDec 21\nDec 22"

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_poll_msg = MagicMock(spec=discord.Message)
    mock_poll_msg.add_reaction = AsyncMock()
    mock_channel.send = AsyncMock(return_value=mock_poll_msg)

    mock_client = MagicMock()
    mock_client.get_channel.return_value = mock_channel

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.client = mock_client
    mock_interaction.response = MagicMock()
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup = MagicMock()
    mock_interaction.followup.send = AsyncMock()

    await modal.on_submit(mock_interaction)

    mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
    mock_channel.send.assert_called_once()
    assert mock_poll_msg.add_reaction.call_count == 3
    reactions_added = [call[0][0] for call in mock_poll_msg.add_reaction.call_args_list]
    assert reactions_added == ["1️⃣", "2️⃣", "3️⃣"]
    mock_interaction.followup.send.assert_called_once()



async def test_deadline_modal_init(temp_repo):
    session_id = await temp_repo.create_session(guild_id=1, channel_id=2)
    modal = DeadlineModal(repo=temp_repo, session_id=session_id, existing_deadline="3d")
    assert modal.deadline_input.default == "3d"
    assert modal.auto_draw_input.default == "yes"
