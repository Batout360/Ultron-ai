"""
ULTRON State Machine
Manages the overall assistant state and state transitions.
The UI subscribes to state changes to drive animations.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Callable

from core.event_bus import EventBus, Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


class AssistantState(Enum):
    """ULTRON's operational states."""
    INITIALIZING = auto()   # Startup in progress
    IDLE = auto()            # Waiting for wake word or push-to-talk
    LISTENING = auto()       # Capturing user speech
    PROCESSING = auto()      # STT transcription in progress
    THINKING = auto()        # LLM is generating response
    SPEAKING = auto()        # TTS is playing audio
    TOOL_RUNNING = auto()    # Executing a tool
    CONFIRMING = auto()      # Waiting for user confirmation
    ERROR = auto()           # Non-fatal error state
    PAUSED = auto()          # User-paused
    OFFLINE = auto()         # LLM not reachable


# Valid state transitions: current -> allowed_next_states
STATE_TRANSITIONS: dict[AssistantState, set[AssistantState]] = {
    AssistantState.INITIALIZING: {
        AssistantState.IDLE,
        AssistantState.OFFLINE,
        AssistantState.ERROR,
    },
    AssistantState.IDLE: {
        AssistantState.LISTENING,
        AssistantState.THINKING,        # Direct text input (no voice pipeline)
        AssistantState.PAUSED,
        AssistantState.OFFLINE,
        AssistantState.ERROR,
        AssistantState.INITIALIZING,
    },
    AssistantState.LISTENING: {
        AssistantState.PROCESSING,
        AssistantState.IDLE,
        AssistantState.ERROR,
    },
    AssistantState.PROCESSING: {
        AssistantState.THINKING,
        AssistantState.IDLE,
        AssistantState.ERROR,
    },
    AssistantState.THINKING: {
        AssistantState.SPEAKING,
        AssistantState.TOOL_RUNNING,
        AssistantState.IDLE,
        AssistantState.ERROR,
        AssistantState.OFFLINE,
    },
    AssistantState.SPEAKING: {
        AssistantState.IDLE,
        AssistantState.LISTENING,
        AssistantState.THINKING,
        AssistantState.ERROR,
    },
    AssistantState.TOOL_RUNNING: {
        AssistantState.THINKING,
        AssistantState.SPEAKING,
        AssistantState.CONFIRMING,
        AssistantState.IDLE,
        AssistantState.ERROR,
    },
    AssistantState.CONFIRMING: {
        AssistantState.TOOL_RUNNING,
        AssistantState.IDLE,
        AssistantState.ERROR,
    },
    AssistantState.ERROR: {
        AssistantState.IDLE,
        AssistantState.OFFLINE,
        AssistantState.INITIALIZING,
    },
    AssistantState.PAUSED: {
        AssistantState.IDLE,
        AssistantState.OFFLINE,
    },
    AssistantState.OFFLINE: {
        AssistantState.IDLE,
        AssistantState.INITIALIZING,
        AssistantState.ERROR,
    },
}


@dataclass
class StateSnapshot:
    """Immutable snapshot of assistant state at a point in time."""
    state: AssistantState
    previous_state: Optional[AssistantState]
    timestamp: float
    message: str = ""
    error: Optional[str] = None


class StateManager:
    """
    Manages ULTRON's current state.
    All state changes go through transition(), which validates the transition
    and publishes a STATE_CHANGED event.
    """

    def __init__(self, bus: Optional[EventBus] = None) -> None:
        self._state = AssistantState.INITIALIZING
        self._previous_state: Optional[AssistantState] = None
        self._state_entered: float = time.monotonic()
        self._history: list[StateSnapshot] = []
        self._bus = bus or get_event_bus()
        self._lock = asyncio.Lock()
        self._on_state_change_callbacks: list[Callable[[AssistantState, AssistantState], None]] = []

        # Metrics
        self._state_durations: dict[AssistantState, float] = {s: 0.0 for s in AssistantState}

    @property
    def state(self) -> AssistantState:
        return self._state

    @property
    def previous_state(self) -> Optional[AssistantState]:
        return self._previous_state

    @property
    def is_busy(self) -> bool:
        """True when the assistant is actively processing (not idle/paused/offline)."""
        return self._state not in (
            AssistantState.IDLE,
            AssistantState.PAUSED,
            AssistantState.OFFLINE,
            AssistantState.INITIALIZING,
        )

    @property
    def can_listen(self) -> bool:
        return self._state in (AssistantState.IDLE,)

    @property
    def time_in_current_state(self) -> float:
        return time.monotonic() - self._state_entered

    async def transition(
        self,
        new_state: AssistantState,
        message: str = "",
        error: Optional[Exception] = None,
        force: bool = False,
    ) -> bool:
        """
        Transition to a new state.
        Returns True if transition was allowed and applied.
        If force=True, bypass transition validation (use sparingly).
        """
        async with self._lock:
            if new_state == self._state:
                return True  # Already in this state, no-op

            allowed = STATE_TRANSITIONS.get(self._state, set())
            if new_state not in allowed and not force:
                logger.warning(
                    "Invalid state transition: %s -> %s (allowed: %s)",
                    self._state.name,
                    new_state.name,
                    [s.name for s in allowed],
                )
                return False

            # Record duration in old state
            duration = time.monotonic() - self._state_entered
            self._state_durations[self._state] += duration

            old_state = self._state
            self._previous_state = old_state
            self._state = new_state
            self._state_entered = time.monotonic()

            snapshot = StateSnapshot(
                state=new_state,
                previous_state=old_state,
                timestamp=time.monotonic(),
                message=message,
                error=str(error) if error else None,
            )
            self._history.append(snapshot)
            if len(self._history) > 50:
                self._history.pop(0)

            logger.info(
                "State: %s -> %s%s",
                old_state.name,
                new_state.name,
                f" ({message})" if message else "",
            )

            # Notify callbacks (sync, for Qt slots)
            for cb in self._on_state_change_callbacks:
                try:
                    cb(old_state, new_state)
                except Exception as e:
                    logger.error("State change callback error: %s", e)

        # Publish event (outside lock)
        await self._bus.publish(Event(
            type=EventType.STATE_CHANGED,
            data={
                "state": new_state,
                "previous": old_state,
                "message": message,
                "error": str(error) if error else None,
            },
            source="StateManager",
        ))

        return True

    def transition_sync(
        self,
        new_state: AssistantState,
        message: str = "",
        error: Optional[Exception] = None,
        force: bool = False,
    ) -> None:
        """Non-async version for use in sync contexts (e.g. init)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.transition(new_state, message, error, force))
            else:
                loop.run_until_complete(self.transition(new_state, message, error, force))
        except RuntimeError:
            # If no event loop, just update state directly
            self._previous_state = self._state
            self._state = new_state
            logger.info("State (sync): %s -> %s", self._previous_state.name if self._previous_state else "?", new_state.name)

    def on_change(self, callback: Callable[[AssistantState, AssistantState], None]) -> None:
        """Register a sync callback for state changes (called from Qt thread)."""
        self._on_state_change_callbacks.append(callback)

    def get_metrics(self) -> dict[str, float]:
        """Return time spent in each state (seconds)."""
        return {s.name: round(d, 3) for s, d in self._state_durations.items()}

    @property
    def history(self) -> list[StateSnapshot]:
        return list(self._history)
