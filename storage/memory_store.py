"""
ULTRON Memory Store
Higher-level interface combining short-term (in-memory) and long-term (SQLite) storage.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Unified interface to both short-term (session) and long-term (DB) memory.
    Provides search across both stores.
    """

    def __init__(self, db=None) -> None:
        self._db = db
        # Short-term: simple dict for session-scoped data
        self._session_data: dict[str, str] = {}
        self._session_id = f"session_{int(time.time())}"

    @property
    def session_id(self) -> str:
        return self._session_id

    def set_session(self, key: str, value: str) -> None:
        """Store a short-lived session value."""
        self._session_data[key] = value

    def get_session(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a session value."""
        return self._session_data.get(key, default)

    def clear_session(self) -> None:
        """Clear all session data."""
        self._session_data.clear()

    async def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a user preference from DB."""
        if self._db:
            return await self._db.get_preference(key, default)
        return self._session_data.get(f"pref:{key}", default)

    async def set_preference(self, key: str, value: str) -> None:
        """Persist a user preference."""
        if self._db:
            await self._db.set_preference(key, value)
        self._session_data[f"pref:{key}"] = value
