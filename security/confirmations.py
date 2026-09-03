"""
ULTRON Confirmation Manager
Manages confirmation dialogs for potentially dangerous tool operations.
Confirmation can come from the UI dialog or voice ("yes"/"no").
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from core.event_bus import EventBus, Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class ConfirmationRequest:
    """A pending confirmation for a tool operation."""
    id: str
    tool_name: str
    tool_arguments: dict
    message: str
    is_reversible: bool = True
    _future: asyncio.Future = field(default_factory=asyncio.Future, repr=False)

    def resolve(self, approved: bool) -> None:
        if not self._future.done():
            self._future.set_result(approved)

    async def wait(self, timeout: float = 30.0) -> bool:
        """Wait for the user's response. Times out as denial."""
        try:
            return await asyncio.wait_for(self._future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Confirmation timed out for %s - denying", self.tool_name)
            return False


class ConfirmationManager:
    """
    Central manager for tool confirmation workflow.

    Flow:
    1. Tool system calls request_confirmation()
    2. ConfirmationManager publishes TOOL_CONFIRMATION_NEEDED event
    3. UI shows dialog; user clicks Yes/No (or speaks yes/no)
    4. UI/voice handler calls resolve(id, approved)
    5. request_confirmation() returns with the user's decision
    """

    def __init__(self, bus: Optional[EventBus] = None) -> None:
        self._bus = bus or get_event_bus()
        self._pending: dict[str, ConfirmationRequest] = {}
        self._counter = 0

        self._bus.subscribe(EventType.TOOL_CONFIRMATION_RESULT, self._on_result)

    async def request_confirmation(
        self,
        tool_name: str,
        tool_arguments: dict,
        message: str,
        is_reversible: bool = True,
        timeout: float = 30.0,
    ) -> bool:
        """
        Request user confirmation. Blocks until user responds or timeout.
        Returns True if approved, False otherwise.
        """
        self._counter += 1
        req_id = f"confirm_{self._counter}"

        request = ConfirmationRequest(
            id=req_id,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            message=message,
            is_reversible=is_reversible,
        )
        self._pending[req_id] = request

        logger.info("Requesting confirmation: %s - %s", tool_name, message)

        await self._bus.publish(Event(
            type=EventType.TOOL_CONFIRMATION_NEEDED,
            data={
                "id": req_id,
                "tool": tool_name,
                "message": message,
                "is_reversible": is_reversible,
                "arguments": tool_arguments,
            },
        ))

        approved = await request.wait(timeout=timeout)

        self._pending.pop(req_id, None)
        logger.info("Confirmation for %s: %s", tool_name, "APPROVED" if approved else "DENIED")
        return approved

    async def _on_result(self, event: Event) -> None:
        """Handle a TOOL_CONFIRMATION_RESULT event from the UI."""
        req_id = event.data.get("id")
        approved = event.data.get("approved", False)

        if req_id in self._pending:
            self._pending[req_id].resolve(approved)
        else:
            logger.debug("No pending confirmation with id: %s", req_id)

    def resolve(self, req_id: str, approved: bool) -> None:
        """Programmatically resolve a pending confirmation (from UI callback)."""
        if req_id in self._pending:
            self._pending[req_id].resolve(approved)

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)

    @property
    def pending_count(self) -> int:
        return len(self._pending)
