"""Database backup and migration bundle management service."""

import datetime
import json
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any, Optional
import zipfile

from src.config import DATABASE_PATH, ASSETS_DIR

logger = logging.getLogger("secretsanta.backup")


def get_backups_dir(db_path: str = DATABASE_PATH) -> Path:
    """Return the directory path for automated database backups."""
    backup_dir = Path(db_path).parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_database_backup(db_path: str = DATABASE_PATH, max_backups: int = 10) -> Optional[Path]:
    """
    Create a hot, non-blocking backup of the SQLite database using the SQLite Online Backup API.
    Rotates old backups to retain only the latest `max_backups` files.
    """
    src_file = Path(db_path)
    if not src_file.exists() or src_file.stat().st_size == 0:
        return None

    backup_dir = get_backups_dir(db_path)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_file = backup_dir / f"secretsanta_backup_{ts}.db"

    try:
        with sqlite3.connect(src_file) as src, sqlite3.connect(dest_file) as dst:
            src.backup(dst)
        logger.info("Automated backup created successfully: %s (%d bytes)", dest_file.name, dest_file.stat().st_size)

        # Rotate older backups
        existing_backups = sorted(backup_dir.glob("secretsanta_backup_*.db"), key=os.path.getmtime)
        if len(existing_backups) > max_backups:
            to_remove = existing_backups[:-max_backups]
            for old_file in to_remove:
                try:
                    old_file.unlink()
                    logger.debug("Pruned old database backup: %s", old_file.name)
                except OSError:
                    pass

        return dest_file
    except Exception as e:
        logger.error("Failed to create database backup: %s", e)
        return None


def create_migration_bundle(
    db_path: str = DATABASE_PATH,
    assets_dir: Optional[str] = ASSETS_DIR,
) -> Path:
    """
    Package the live database and branding assets into a single zip archive for moving host.
    """
    backup_dir = get_backups_dir(db_path)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = backup_dir / f"secretsanta_migration_{ts}.zip"

    src_file = Path(db_path)
    temp_db = backup_dir / f"temp_snapshot_{ts}.db"

    # Step 1: Consistent live database snapshot
    with sqlite3.connect(src_file) as src, sqlite3.connect(temp_db) as dst:
        src.backup(dst)

    # Gather database statistics for manifest
    manifest_data: dict[str, Any] = {
        "created_at": datetime.datetime.now().isoformat(),
        "database_file": "secretsanta.db",
        "tables": {},
    }

    try:
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            for table in ("game_sessions", "participants", "pairings", "exclusions", "relay_messages"):
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    manifest_data["tables"][table] = cursor.fetchone()[0]
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Could not read table statistics for manifest: %s", e)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write DB snapshot as secretsanta.db
        zf.write(temp_db, arcname="secretsanta.db")

        # Write migration manifest
        zf.writestr("migration_manifest.json", json.dumps(manifest_data, indent=2))

        # Add assets if present
        if assets_dir:
            assets_path = Path(assets_dir)
            if assets_path.exists():
                for f in assets_path.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(assets_path)
                        zf.write(f, arcname=f"assets/{rel}")

    # Clean up temp db snapshot
    try:
        temp_db.unlink()
    except OSError:
        pass

    logger.info("Migration bundle created: %s (%d bytes)", zip_path.name, zip_path.stat().st_size)
    return zip_path


def list_backups(db_path: str = DATABASE_PATH) -> list[dict[str, Any]]:
    """Return a list of existing backup files and their sizes."""
    backup_dir = get_backups_dir(db_path)
    files = sorted(backup_dir.glob("secretsanta_backup_*.db"), key=os.path.getmtime, reverse=True)
    results = []
    for f in files:
        results.append({
            "name": f.name,
            "path": str(f),
            "size_kb": round(f.stat().st_size / 1024, 1),
            "created_at": datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return results
