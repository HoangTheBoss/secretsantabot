"""Unit tests for state persistence, WAL mode, backup service, and dynamic view recovery."""

import os
import sqlite3
import zipfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock
import discord

from src.database.db import init_db, checkpoint_db, get_connection
from src.database.repo import SantaRepository
from src.services.backup_service import (
    create_database_backup,
    create_migration_bundle,
    list_backups,
)
from src.ui.views import (
    RegistrationView,
    SantaDmView,
    BabyReplyView,
    HostControlPanel,
    MyStatusView,
)


@pytest.fixture
async def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_santa.db")
    await init_db(db_file)
    return SantaRepository(db_file)


async def test_init_db_wal_mode_and_checkpoint(tmp_path):
    db_file = str(tmp_path / "wal_test.db")
    await init_db(db_file)

    # Verify journal mode is WAL
    async with get_connection(db_file) as conn:
        cursor = await conn.execute("PRAGMA journal_mode;")
        row = await cursor.fetchone()
        assert row[0].lower() == "wal"

    # Verify checkpoint_db executes cleanly
    await checkpoint_db(db_file)
    assert Path(db_file).exists()


def test_backup_service_rotation(tmp_path):
    db_file = tmp_path / "source.db"
    # Create valid sqlite db
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE test (id INT);")
        conn.execute("INSERT INTO test VALUES (1);")

    # Create 5 backups with max_backups=3
    for _ in range(5):
        bck = create_database_backup(str(db_file), max_backups=3)
        assert bck is not None
        assert bck.exists()

    backups = list_backups(str(db_file))
    # Should only retain max 3 backups
    assert len(backups) <= 3


def test_create_migration_bundle(tmp_path):
    db_file = tmp_path / "source.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE game_sessions (id INT);")
        conn.execute("INSERT INTO game_sessions VALUES (1);")

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "logo.png").write_text("dummy image data")

    zip_path = create_migration_bundle(str(db_file), assets_dir=str(assets_dir))
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"

    # Verify zip contents
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "secretsanta.db" in namelist
        assert "migration_manifest.json" in namelist
        assert "assets/logo.png" in namelist

    zip_path.unlink()


async def test_persistent_views_dynamic_session_recovery(temp_repo):
    # Setup session & participant
    session_id = await temp_repo.create_session(guild_id=999, channel_id=888)
    await temp_repo.add_or_update_participant(
        session_id=session_id,
        user_id=123,
        username="santa_user",
        display_name="Santa",
    )
    await temp_repo.add_or_update_participant(
        session_id=session_id,
        user_id=456,
        username="baby_user",
        display_name="Baby",
    )
    await temp_repo.save_pairings(session_id, [(123, 456, "TAG-01")])
    await temp_repo.update_session_status(session_id, "IN_PROGRESS")

    # 1. RegistrationView initialized with session_id=0 (e.g. gateway re-attach on restart)
    reg_view = RegistrationView(temp_repo, session_id=0)
    mock_guild_interaction = MagicMock(spec=discord.Interaction)
    mock_guild_interaction.guild_id = 999
    resolved_session = await reg_view._resolve_session(mock_guild_interaction)
    assert resolved_session is not None
    assert resolved_session["id"] == session_id

    # 2. SantaDmView initialized with no IDs (persistent listener across restarts)
    santa_dm_view = SantaDmView(temp_repo)
    mock_santa_interaction = MagicMock(spec=discord.Interaction)
    mock_santa_interaction.user.id = 123
    mock_santa_interaction.guild_id = None
    resolved_pairing = await santa_dm_view._resolve_pairing(mock_santa_interaction)
    assert resolved_pairing is not None
    assert resolved_pairing[0] == session_id
    assert resolved_pairing[1] == 456

    # 3. BabyReplyView initialized with no IDs
    baby_reply_view = BabyReplyView(temp_repo)
    mock_baby_interaction = MagicMock(spec=discord.Interaction)
    mock_baby_interaction.user.id = 456
    mock_baby_interaction.guild_id = None
    resolved_baby_pairing = await baby_reply_view._resolve_pairing(mock_baby_interaction)
    assert resolved_baby_pairing is not None
    assert resolved_baby_pairing[0] == session_id
    assert resolved_baby_pairing[1] == 123

    # 4. HostControlPanel initialized with session_id=0
    panel_view = HostControlPanel(temp_repo, session_id=0)
    resolved_panel_session = await panel_view._resolve_session(mock_guild_interaction)
    assert resolved_panel_session is not None
    assert resolved_panel_session["id"] == session_id

    # 5. MyStatusView initialized with session_id=0
    status_view = MyStatusView(temp_repo, session_id=0)
    resolved_status_sid = await status_view._resolve_session_id(mock_santa_interaction)
    assert resolved_status_sid == session_id
