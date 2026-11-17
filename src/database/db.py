"""Async SQLite database initialization and connection management."""

import aiosqlite
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from src.config import DATABASE_PATH

logger = logging.getLogger("secretsanta.database")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    budget TEXT,
    party_date TEXT,
    party_venue TEXT,
    signup_deadline TEXT,
    signup_deadline_epoch INTEGER,
    auto_draw BOOLEAN DEFAULT 1,
    triggered_milestones TEXT DEFAULT '',
    registration_message_id INTEGER,
    last_reminded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);





CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    display_name TEXT NOT NULL,
    wishlist TEXT DEFAULT '',
    dislikes TEXT DEFAULT '',
    offline_notes TEXT DEFAULT '',
    gift_status TEXT DEFAULT 'NOT_STARTED',
    dm_verified BOOLEAN DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE,
    UNIQUE (session_id, user_id)
);

CREATE TABLE IF NOT EXISTS pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    santa_id INTEGER NOT NULL,
    baby_id INTEGER NOT NULL,
    gift_tag_code TEXT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    gift_status TEXT DEFAULT 'NOT_STARTED',
    triggered_milestones TEXT DEFAULT '',
    last_reminded_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE,

    UNIQUE (session_id, santa_id),
    UNIQUE (session_id, baby_id)
);

CREATE TABLE IF NOT EXISTS exclusions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_a_id INTEGER NOT NULL,
    user_b_id INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE,
    UNIQUE (session_id, user_a_id, user_b_id)
);

CREATE TABLE IF NOT EXISTS relay_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    santa_id INTEGER NOT NULL,
    baby_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    content TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_participants_session ON participants(session_id);
CREATE INDEX IF NOT EXISTS idx_pairings_session ON pairings(session_id);
CREATE INDEX IF NOT EXISTS idx_exclusions_session ON exclusions(session_id);
CREATE INDEX IF NOT EXISTS idx_relay_session ON relay_messages(session_id);
"""


async def init_db(db_path: str = DATABASE_PATH) -> None:
    """Initialize database tables, columns, and indexes with WAL mode and hot backup on startup."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Automatic pre-startup backup if db exists and has content (dev in prod safety net)
    if path.exists() and path.stat().st_size > 0:
        from src.services.backup_service import create_database_backup
        create_database_backup(db_path)

    logger.info("Initializing database schema at %s", db_path)

    async with aiosqlite.connect(db_path) as db:
        # WAL mode & concurrency pragmas
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA busy_timeout = 10000;")
        await db.execute("PRAGMA synchronous = NORMAL;")
        await db.execute("PRAGMA foreign_keys = ON;")

        await db.executescript(SCHEMA_SQL)

        # Check and add columns if upgrading existing db
        try:
            await db.execute("ALTER TABLE game_sessions ADD COLUMN last_reminded_at TIMESTAMP;")
        except Exception:
            pass  # Already exists

        try:
            await db.execute("ALTER TABLE game_sessions ADD COLUMN signup_deadline_epoch INTEGER;")
        except Exception:
            pass  # Already exists

        try:
            await db.execute("ALTER TABLE game_sessions ADD COLUMN auto_draw BOOLEAN DEFAULT 1;")
        except Exception:
            pass  # Already exists

        try:
            await db.execute("ALTER TABLE game_sessions ADD COLUMN triggered_milestones TEXT DEFAULT '';")
        except Exception:
            pass  # Already exists

        try:
            await db.execute("ALTER TABLE game_sessions ADD COLUMN registration_message_id INTEGER;")
        except Exception:
            pass  # Already exists

        try:
            await db.execute("ALTER TABLE pairings ADD COLUMN triggered_milestones TEXT DEFAULT '';")
        except Exception:
            pass  # Already exists

        try:
            await db.execute("ALTER TABLE pairings ADD COLUMN last_reminded_at TIMESTAMP;")
        except Exception:
            pass  # Already exists

        await db.commit()
    logger.info("Database schema initialized successfully with WAL journal mode.")


async def checkpoint_db(db_path: str = DATABASE_PATH) -> None:
    """Flush and truncate WAL pages to make the main sqlite file 100% self-contained on shutdown."""
    path = Path(db_path)
    if not path.exists():
        return
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            logger.info("Database WAL successfully checkpointed and truncated.")
    except Exception as e:
        logger.warning("Could not checkpoint database WAL: %s", e)


@asynccontextmanager
async def get_connection(db_path: str = DATABASE_PATH) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager returning an active connection with Row factory enabled."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA busy_timeout = 10000;")
        yield db
