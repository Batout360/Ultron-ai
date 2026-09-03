"""
ULTRON Database
SQLite database using aiosqlite for async operation.
Stores: conversation history, long-term memories, user preferences.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from core.memory import MemoryEntry

logger = logging.getLogger(__name__)


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL UNIQUE,
    value       TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'general',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    use_count   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    timestamp   REAL NOT NULL,
    tokens      INTEGER DEFAULT 0,
    tool_name   TEXT
);

CREATE TABLE IF NOT EXISTS preferences (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id, timestamp);
"""


class Database:
    """
    Async SQLite database for ULTRON's persistent storage.
    Uses aiosqlite for non-blocking I/O.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = None

    async def initialize(self) -> None:
        """Create/open the database and run migrations."""
        try:
            import aiosqlite
        except ImportError:
            logger.error("aiosqlite not installed: pip install aiosqlite")
            raise

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._db_path))
        self._conn.row_factory = aiosqlite.Row

        # Performance tuning
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA cache_size=10000")

        # Create tables
        await self._conn.executescript(CREATE_TABLES_SQL)
        await self._conn.commit()

        logger.info("Database initialized: %s", self._db_path)

    # -------- Memory operations --------

    async def save_memory(self, entry: MemoryEntry) -> int:
        """Insert a new memory. Returns the new row ID."""
        async with self._conn.execute(
            """INSERT INTO memories (key, value, category, created_at, updated_at, use_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entry.key, entry.value, entry.category, entry.created_at, entry.updated_at, entry.use_count),
        ) as cursor:
            await self._conn.commit()
            return cursor.lastrowid

    async def update_memory(self, entry: MemoryEntry) -> None:
        """Update an existing memory by key."""
        await self._conn.execute(
            """UPDATE memories SET value=?, updated_at=?, use_count=?
               WHERE key=?""",
            (entry.value, entry.updated_at, entry.use_count, entry.key),
        )
        await self._conn.commit()

    async def delete_memory(self, memory_id: int) -> None:
        """Delete a memory by ID."""
        await self._conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        await self._conn.commit()

    async def get_all_memories(self) -> list[MemoryEntry]:
        """Load all memories from the database."""
        async with self._conn.execute(
            "SELECT * FROM memories ORDER BY updated_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                MemoryEntry(
                    id=row["id"],
                    key=row["key"],
                    value=row["value"],
                    category=row["category"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    use_count=row["use_count"],
                )
                for row in rows
            ]

    async def clear_all_memories(self) -> None:
        """Remove all memories."""
        await self._conn.execute("DELETE FROM memories")
        await self._conn.commit()

    # -------- Conversation history --------

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        timestamp: float,
        tokens: int = 0,
        tool_name: Optional[str] = None,
    ) -> int:
        async with self._conn.execute(
            """INSERT INTO conversations (session_id, role, content, timestamp, tokens, tool_name)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, role, content, timestamp, tokens, tool_name),
        ) as cursor:
            await self._conn.commit()
            return cursor.lastrowid

    async def get_session_messages(self, session_id: str, limit: int = 100) -> list[dict]:
        async with self._conn.execute(
            """SELECT * FROM conversations WHERE session_id=?
               ORDER BY timestamp DESC LIMIT ?""",
            (session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    async def get_recent_sessions(self, limit: int = 10) -> list[str]:
        async with self._conn.execute(
            """SELECT DISTINCT session_id FROM conversations
               ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    # -------- Preferences --------

    async def set_preference(self, key: str, value: str) -> None:
        import time
        await self._conn.execute(
            """INSERT OR REPLACE INTO preferences (key, value, updated_at)
               VALUES (?, ?, ?)""",
            (key, value, time.time()),
        )
        await self._conn.commit()

    async def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        async with self._conn.execute(
            "SELECT value FROM preferences WHERE key=?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database closed")
