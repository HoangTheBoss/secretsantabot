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


async def test_deadline_modal_init(temp_repo):
    session_id = await temp_repo.create_session(guild_id=1, channel_id=2)
    modal = DeadlineModal(repo=temp_repo, session_id=session_id, existing_deadline="3d")
    assert modal.deadline_input.default == "3d"
    assert modal.auto_draw_input.default == "yes"
