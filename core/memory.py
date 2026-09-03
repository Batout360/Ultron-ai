"""
ULTRON Memory System
Manages long-term persistent memory using SQLite (via the storage layer).
Users can explicitly store facts and retrieve them across sessions.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    id: Optional[int]
    key: str
    value: str
    category: str
    created_at: float
    updated_at: float
    use_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "use_count": self.use_count,
        }


class MemoryManager:
    """
    Manages ULTRON's long-term memory.

    Memory is stored in SQLite and persists across sessions.
    Users can:
      - Remember: "Remember that I prefer dark mode"
      - Forget: "Forget what you know about dark mode"
      - List: "What do you remember about me?"
      - Clear all: (admin action, requires confirmation)

    The assistant proactively uses retrieved memories to personalize responses.
    """

    # Patterns for extracting remember/forget commands
    REMEMBER_PATTERNS = [
        r"remember (?:that |the |)(.+)",
        r"note that (.+)",
        r"keep in mind that (.+)",
        r"don't forget (?:that |)(.+)",
        r"save (?:that |this|)[:;]?\s*(.+)",
    ]

    FORGET_PATTERNS = [
        r"forget (?:what you (?:know|remember) about |that |)(.+)",
        r"delete (?:the |your |)memory (?:about |of |)(.+)",
        r"remove (?:the |)(?:memory|note) (?:about |)(.+)",
        r"clear (?:what you (?:know|remember) about |)(.+)",
    ]

    def __init__(self, db=None) -> None:
        """
        db: injected database instance (storage.Database).
        If None, memory operates in-memory only (for testing).
        """
        self._db = db
        self._cache: dict[str, MemoryEntry] = {}
        self._loaded = False

    async def initialize(self) -> None:
        """Load all memories from DB into cache."""
        if self._db is None:
            logger.warning("MemoryManager: no database, using in-memory storage only")
            self._loaded = True
            return
        try:
            entries = await self._db.get_all_memories()
            self._cache = {e.key: e for e in entries}
            self._loaded = True
            logger.info("Loaded %d long-term memories", len(self._cache))
        except Exception as e:
            logger.error("Failed to load memories: %s", e)
            self._loaded = True

    async def remember(
        self,
        key: str,
        value: str,
        category: str = "general",
    ) -> MemoryEntry:
        """
        Store a key/value memory.
        If key already exists, update it.
        """
        key = key.strip().lower()
        now = time.time()

        if key in self._cache:
            entry = self._cache[key]
            entry.value = value
            entry.updated_at = now
            entry.use_count += 1
            if self._db:
                await self._db.update_memory(entry)
            logger.info("Memory updated: %s = %s", key, value[:80])
        else:
            entry = MemoryEntry(
                id=None,
                key=key,
                value=value,
                category=category,
                created_at=now,
                updated_at=now,
                use_count=1,
            )
            if self._db:
                entry.id = await self._db.save_memory(entry)
            self._cache[key] = entry
            logger.info("Memory stored: %s = %s", key, value[:80])

        return entry

    async def forget(self, key: str) -> bool:
        """
        Remove a memory by key (or partial key match).
        Returns True if something was removed.
        """
        key = key.strip().lower()

        # Try exact match first
        if key in self._cache:
            entry = self._cache.pop(key)
            if self._db and entry.id:
                await self._db.delete_memory(entry.id)
            logger.info("Memory forgotten: %s", key)
            return True

        # Try partial match
        matches = [k for k in self._cache if key in k]
        if matches:
            for k in matches:
                entry = self._cache.pop(k)
                if self._db and entry.id:
                    await self._db.delete_memory(entry.id)
                logger.info("Memory forgotten (partial match): %s", k)
            return True

        return False

    async def forget_all(self) -> int:
        """Clear all memories. Returns count removed."""
        count = len(self._cache)
        self._cache.clear()
        if self._db:
            await self._db.clear_all_memories()
        logger.info("All %d memories cleared", count)
        return count

    def recall(self, key: str) -> Optional[MemoryEntry]:
        """Look up a specific memory by key."""
        return self._cache.get(key.strip().lower())

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search memories by key or value (simple substring match)."""
        query = query.lower()
        results = []
        for entry in self._cache.values():
            if query in entry.key or query in entry.value.lower():
                results.append(entry)
        results.sort(key=lambda e: e.use_count, reverse=True)
        return results[:limit]

    def get_all(self, category: Optional[str] = None) -> list[MemoryEntry]:
        """Return all stored memories, optionally filtered by category."""
        entries = list(self._cache.values())
        if category:
            entries = [e for e in entries if e.category == category]
        return sorted(entries, key=lambda e: e.updated_at, reverse=True)

    def format_for_prompt(self) -> str:
        """
        Format all memories as a compact string for injection into the LLM prompt.
        Keeps the most relevant/recent memories.
        """
        if not self._cache:
            return ""

        lines = []
        entries = sorted(self._cache.values(), key=lambda e: e.use_count, reverse=True)
        for entry in entries[:20]:  # Limit to avoid filling context
            lines.append(f"- {entry.key}: {entry.value}")

        return "\n".join(lines)

    @property
    def count(self) -> int:
        return len(self._cache)

    # -------- Command parsing helpers --------

    def parse_remember_command(self, text: str) -> Optional[tuple[str, str]]:
        """
        Parse natural language remember commands.
        Returns (key, value) or None if not a remember command.

        Examples:
          "Remember that I prefer dark mode" -> ("i prefer dark mode", "dark mode preference: enabled")
          "Note that my timezone is UTC+5:30" -> ("my timezone is utc+5:30", ...)
        """
        text = text.strip()
        for pattern in self.REMEMBER_PATTERNS:
            m = re.match(pattern, text, re.IGNORECASE)
            if m:
                content = m.group(1).strip().rstrip(".")
                # Use the content as both key and value, key shortened
                key = content[:60].lower()
                return key, content
        return None

    def parse_forget_command(self, text: str) -> Optional[str]:
        """
        Parse natural language forget commands.
        Returns the search key or None if not a forget command.
        """
        text = text.strip()
        for pattern in self.FORGET_PATTERNS:
            m = re.match(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip().rstrip(".").lower()
        return None
