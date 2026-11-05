"""Repository for Santa database interactions."""

import aiosqlite
from typing import Any, Optional
from src.database.db import get_connection
from src.config import DATABASE_PATH


class SantaRepository:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path

    async def get_active_session(self, guild_id: int) -> Optional[dict[str, Any]]:
        """Fetch the current non-completed game session for this guild."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                """
                SELECT * FROM game_sessions
                WHERE guild_id = ? AND status NOT IN ('COMPLETED', 'CANCELLED')
                ORDER BY id DESC LIMIT 1
                """,
                (guild_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_session_by_id(self, session_id: int) -> Optional[dict[str, Any]]:
        """Fetch session by id."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM game_sessions WHERE id = ?",
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_session(
        self,
        guild_id: int,
        channel_id: int,
        budget: Optional[str] = None,
        party_date: Optional[str] = None,
        party_venue: Optional[str] = None,
        signup_deadline: Optional[str] = None,
        signup_deadline_epoch: Optional[int] = None,
        auto_draw: bool = True,
    ) -> int:
        """Create a new game session in REGISTRATION state."""
        async with get_connection(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO game_sessions (
                    guild_id, channel_id, status, budget, party_date,
                    party_venue, signup_deadline, signup_deadline_epoch, auto_draw
                )
                VALUES (?, ?, 'REGISTRATION', ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    channel_id,
                    budget,
                    party_date,
                    party_venue,
                    signup_deadline,
                    signup_deadline_epoch,
                    1 if auto_draw else 0,
                ),
            )
            await db.commit()
            return cursor.lastrowid

    async def update_session_status(self, session_id: int, status: str) -> None:
        """Update game session status."""
        async with get_connection(self.db_path) as db:
            await db.execute(
                "UPDATE game_sessions SET status = ? WHERE id = ?",
                (status, session_id),
            )
            await db.commit()

    async def update_session_details(
        self,
        session_id: int,
        budget: Optional[str] = None,
        party_date: Optional[str] = None,
        party_venue: Optional[str] = None,
        signup_deadline: Optional[str] = None,
        signup_deadline_epoch: Optional[int] = None,
        auto_draw: Optional[bool] = None,
        registration_message_id: Optional[int] = None,
    ) -> None:
        """Update event details."""
        updates: list[str] = []
        params: list[Any] = []

        if budget is not None:
            updates.append("budget = ?")
            params.append(budget)
        if party_date is not None:
            updates.append("party_date = ?")
            params.append(party_date)
        if party_venue is not None:
            updates.append("party_venue = ?")
            params.append(party_venue)
        if signup_deadline is not None:
            updates.append("signup_deadline = ?")
            params.append(signup_deadline)
        if signup_deadline_epoch is not None:
            updates.append("signup_deadline_epoch = ?")
            params.append(signup_deadline_epoch)
        if auto_draw is not None:
            updates.append("auto_draw = ?")
            params.append(1 if auto_draw else 0)
        if registration_message_id is not None:
            updates.append("registration_message_id = ?")
            params.append(registration_message_id)

        if not updates:
            return

        params.append(session_id)
        query = f"UPDATE game_sessions SET {', '.join(updates)} WHERE id = ?"
        async with get_connection(self.db_path) as db:
            await db.execute(query, tuple(params))
            await db.commit()

    async def update_registration_message_id(self, session_id: int, message_id: int) -> None:
        """Record the Discord message ID of the channel registration embed."""
        async with get_connection(self.db_path) as db:
            await db.execute(
                "UPDATE game_sessions SET registration_message_id = ? WHERE id = ?",
                (message_id, session_id),
            )
            await db.commit()

    async def archive_or_cancel_session(self, session_id: int, status: str = "CANCELLED") -> None:
        """Cancel or archive active session."""
        async with get_connection(self.db_path) as db:
            await db.execute(
                "UPDATE game_sessions SET status = ? WHERE id = ?",
                (status, session_id),
            )
            await db.commit()



    async def add_or_update_participant(
        self,
        session_id: int,
        user_id: int,
        username: str,
        display_name: str,
        wishlist: str = "",
        dislikes: str = "",
        offline_notes: str = "",
        dm_verified: bool = True,
    ) -> None:
        """Add or update participant information."""
        async with get_connection(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO participants (
                    session_id, user_id, username, display_name,
                    wishlist, dislikes, offline_notes, dm_verified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, user_id) DO UPDATE SET
                    username = excluded.username,
                    display_name = excluded.display_name,
                    wishlist = excluded.wishlist,
                    dislikes = excluded.dislikes,
                    offline_notes = excluded.offline_notes,
                    dm_verified = excluded.dm_verified
                """,
                (
                    session_id,
                    user_id,
                    username,
                    display_name,
                    wishlist,
                    dislikes,
                    offline_notes,
                    1 if dm_verified else 0,
                ),
            )
            await db.commit()

    async def remove_participant(self, session_id: int, user_id: int) -> bool:
        """Remove a participant from the active session."""
        async with get_connection(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM participants WHERE session_id = ? AND user_id = ?",
                (session_id, user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_participant(
        self, session_id: int, user_id: int
    ) -> Optional[dict[str, Any]]:
        """Fetch a single participant."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM participants WHERE session_id = ? AND user_id = ?",
                (session_id, user_id),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_participants(self, session_id: int) -> list[dict[str, Any]]:
        """Fetch all participants in a session."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM participants WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def add_exclusion(
        self, session_id: int, user_a_id: int, user_b_id: int
    ) -> None:
        """Add mutual exclusion between two users."""
        low, high = sorted([user_a_id, user_b_id])
        async with get_connection(self.db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO exclusions (session_id, user_a_id, user_b_id)
                VALUES (?, ?, ?)
                """,
                (session_id, low, high),
            )
            await db.commit()

    async def remove_exclusion(
        self, session_id: int, user_a_id: int, user_b_id: int
    ) -> bool:
        """Remove mutual exclusion between two users."""
        low, high = sorted([user_a_id, user_b_id])
        async with get_connection(self.db_path) as db:
            cursor = await db.execute(
                """
                DELETE FROM exclusions
                WHERE session_id = ? AND user_a_id = ? AND user_b_id = ?
                """,
                (session_id, low, high),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_exclusions(self, session_id: int) -> list[tuple[int, int]]:
        """Fetch all exclusion pairs for a session."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                "SELECT user_a_id, user_b_id FROM exclusions WHERE session_id = ?",
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [(r[0], r[1]) for r in rows]

    async def save_pairings(
        self, session_id: int, pairings: list[tuple[int, int, str]]
    ) -> None:
        """Save computed pairings: [(santa_id, baby_id, gift_tag_code), ...]"""
        async with get_connection(self.db_path) as db:
            await db.execute("DELETE FROM pairings WHERE session_id = ?", (session_id,))
            await db.executemany(
                """
                INSERT INTO pairings (session_id, santa_id, baby_id, gift_tag_code)
                VALUES (?, ?, ?, ?)
                """,
                [(session_id, s, b, code) for s, b, code in pairings],
            )
            await db.commit()

    async def get_pairing_for_santa(
        self, session_id: int, santa_id: int
    ) -> Optional[dict[str, Any]]:
        """Get target assignment for a given Santa."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                """
                SELECT p.*,
                       part.username as baby_username,
                       part.display_name as baby_display_name,
                       part.wishlist as baby_wishlist,
                       part.dislikes as baby_dislikes,
                       part.offline_notes as baby_offline_notes
                FROM pairings p
                JOIN participants part ON p.session_id = part.session_id AND p.baby_id = part.user_id
                WHERE p.session_id = ? AND p.santa_id = ?
                """,
                (session_id, santa_id),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_pairing_for_baby(
        self, session_id: int, baby_id: int
    ) -> Optional[dict[str, Any]]:
        """Get who is the Santa for a given Baby (used for relay routing)."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM pairings WHERE session_id = ? AND baby_id = ?",
                (session_id, baby_id),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_pairings(self, session_id: int) -> list[dict[str, Any]]:
        """Get all pairings in a session (with participant details)."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                """
                SELECT p.*,
                       s.display_name as santa_name,
                       s.username as santa_username,
                       b.display_name as baby_name,
                       b.username as baby_username
                FROM pairings p
                JOIN participants s ON p.session_id = s.session_id AND p.santa_id = s.user_id
                JOIN participants b ON p.session_id = b.session_id AND p.baby_id = b.user_id
                WHERE p.session_id = ?
                ORDER BY p.id ASC
                """,
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def update_gift_status(
        self, session_id: int, santa_id: int, status: str
    ) -> None:
        """Update gift status in pairings and participants tables."""
        async with get_connection(self.db_path) as db:
            await db.execute(
                "UPDATE pairings SET gift_status = ? WHERE session_id = ? AND santa_id = ?",
                (status, session_id, santa_id),
            )
            await db.execute(
                "UPDATE participants SET gift_status = ? WHERE session_id = ? AND user_id = ?",
                (status, session_id, santa_id),
            )
            await db.commit()

    async def log_relay_message(
        self,
        session_id: int,
        santa_id: int,
        baby_id: int,
        direction: str,
        content: str,
    ) -> int:
        """Log an anonymous relay message."""
        async with get_connection(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO relay_messages (session_id, santa_id, baby_id, direction, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, santa_id, baby_id, direction, content),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_all_active_sessions(self) -> list[dict[str, Any]]:
        """Fetch all active game sessions across guilds."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                """
                SELECT * FROM game_sessions
                WHERE status IN ('REGISTRATION', 'IN_PROGRESS')
                ORDER BY id ASC
                """
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_unwrapped_pairings(self, session_id: int) -> list[dict[str, Any]]:
        """Fetch pairings for Santas who haven't marked their gift as wrapped/ready."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                """
                SELECT p.*,
                       s.display_name as santa_name,
                       s.username as santa_username,
                       b.display_name as baby_name,
                       b.username as baby_username
                FROM pairings p
                JOIN participants s ON p.session_id = s.session_id AND p.santa_id = s.user_id
                JOIN participants b ON p.session_id = b.session_id AND p.baby_id = b.user_id
                WHERE p.session_id = ?
                  AND p.gift_status NOT IN ('WRAPPED', 'READY', 'AT_PARTY')
                ORDER BY p.id ASC
                """,
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def update_pairing_reminded(self, session_id: int, santa_id: int) -> None:
        """Record the timestamp when Santa was nudged via DM."""
        async with get_connection(self.db_path) as db:
            await db.execute(
                """
                UPDATE pairings
                SET last_reminded_at = CURRENT_TIMESTAMP
                WHERE session_id = ? AND santa_id = ?
                """,
                (session_id, santa_id),
            )
            await db.commit()

    async def update_session_reminded(self, session_id: int) -> None:
        """Record the timestamp when the public channel was nudged."""
        async with get_connection(self.db_path) as db:
            await db.execute(
                """
                UPDATE game_sessions
                SET last_reminded_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (session_id,),
            )
            await db.commit()

    async def get_due_auto_draw_sessions(self, current_epoch: int) -> list[dict[str, Any]]:
        """Fetch all sessions where registration is open and signup_deadline has passed for auto-draw."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                """
                SELECT * FROM game_sessions
                WHERE status = 'REGISTRATION'
                  AND auto_draw = 1
                  AND signup_deadline_epoch IS NOT NULL
                  AND signup_deadline_epoch <= ?
                ORDER BY id ASC
                """,
                (current_epoch,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def add_session_milestone(self, session_id: int, milestone: str) -> None:
        """Record a triggered milestone for a game session (e.g. '72h', '24h', '2h')."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                "SELECT triggered_milestones FROM game_sessions WHERE id = ?",
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
                existing = row[0] if row and row[0] else ""
                milestones = set(existing.split(",")) if existing else set()
                milestones.add(milestone)
                new_str = ",".join(sorted(milestones))
                await db.execute(
                    "UPDATE game_sessions SET triggered_milestones = ? WHERE id = ?",
                    (new_str, session_id),
                )
                await db.commit()

    async def add_pairing_milestone(self, session_id: int, santa_id: int, milestone: str) -> None:
        """Record a triggered milestone for an individual pairing."""
        async with get_connection(self.db_path) as db:
            async with db.execute(
                "SELECT triggered_milestones FROM pairings WHERE session_id = ? AND santa_id = ?",
                (session_id, santa_id),
            ) as cursor:
                row = await cursor.fetchone()
                existing = row[0] if row and row[0] else ""
                milestones = set(existing.split(",")) if existing else set()
                milestones.add(milestone)
                new_str = ",".join(sorted(milestones))
                await db.execute(
                    """
                    UPDATE pairings
                    SET triggered_milestones = ?, last_reminded_at = CURRENT_TIMESTAMP
                    WHERE session_id = ? AND santa_id = ?
                    """,
                    (new_str, session_id, santa_id),
                )
                await db.commit()



