"""
ULTRON Event Bus
Lightweight async pub/sub system. All modules communicate through events
rather than direct references, keeping them decoupled.

Usage:
    bus = EventBus()
    bus.subscribe(EventType.STT_RESULT, my_handler)
    await bus.publish(Event(EventType.STT_RESULT, data={"text": "hello"}))
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    # Lifecycle
    APP_STARTED = auto()
    APP_STOPPING = auto()
    APP_ERROR = auto()

    # State changes
    STATE_CHANGED = auto()

    # Wake word
    WAKEWORD_DETECTED = auto()
    WAKEWORD_MISSED = auto()

    # Audio
    AUDIO_STARTED = auto()
    AUDIO_STOPPED = auto()
    AUDIO_CHUNK = auto()
    AUDIO_ERROR = auto()

    # VAD
    VAD_SPEECH_START = auto()
    VAD_SPEECH_END = auto()
    VAD_SILENCE = auto()

    # STT
    STT_PARTIAL = auto()       # Partial transcription (streaming)
    STT_RESULT = auto()        # Final transcription
    STT_ERROR = auto()
    STT_STARTED = auto()
    STT_STOPPED = auto()

    # LLM
    LLM_REQUEST_START = auto()
    LLM_TOKEN = auto()          # Single streaming token
    LLM_CHUNK = auto()          # Buffered chunk ready for TTS
    LLM_RESPONSE_COMPLETE = auto()
    LLM_ERROR = auto()
    LLM_TOOL_CALL = auto()      # Model wants to use a tool

    # TTS
    TTS_STARTED = auto()
    TTS_CHUNK_READY = auto()
    TTS_SPEAKING = auto()
    TTS_DONE = auto()
    TTS_ERROR = auto()
    TTS_INTERRUPT = auto()

    # Tools
    TOOL_CALL_STARTED = auto()
    TOOL_CALL_RESULT = auto()
    TOOL_CALL_ERROR = auto()
    TOOL_CONFIRMATION_NEEDED = auto()
    TOOL_CONFIRMATION_RESULT = auto()

    # Conversation
    USER_MESSAGE = auto()
    ASSISTANT_MESSAGE = auto()
    CONVERSATION_CLEARED = auto()
    MEMORY_UPDATED = auto()

    # UI
    UI_NOTIFICATION = auto()
    UI_UPDATE_STATUS = auto()
    UI_UPDATE_METRICS = auto()

    # Interruption
    USER_INTERRUPT = auto()


@dataclass
class Event:
    type: EventType
    data: Any = None
    source: str = ""
    timestamp: float = field(default_factory=time.monotonic)
    error: Optional[Exception] = None


# Handler type: sync or async callable accepting an Event
Handler = Callable[[Event], Any]


class EventBus:
    """
    Thread-safe async event bus.
    Handlers can be sync or async functions.
    Handlers are called in subscription order.
    Exceptions in handlers are logged but do not propagate.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Handler]] = {}
        self._lock = asyncio.Lock()
        self._history: list[Event] = []
        self._history_max = 100

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug("Subscribed %s to %s", handler.__name__, event_type.name)

    def unsubscribe(self, event_type: EventType, handler: Handler) -> None:
        """Remove a handler registration."""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    def subscribe_many(self, subscriptions: dict[EventType, Handler]) -> None:
        """Convenience method to register multiple handlers at once."""
        for event_type, handler in subscriptions.items():
            self.subscribe(event_type, handler)

    async def publish(self, event: Event) -> None:
        """
        Publish an event. All registered handlers are called.
        Async handlers are awaited. Sync handlers are called directly.
        """
        # Track history
        self._history.append(event)
        if len(self._history) > self._history_max:
            self._history.pop(0)

        handlers = self._handlers.get(event.type, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    "Handler %s raised error for event %s: %s",
                    getattr(handler, '__name__', str(handler)),
                    event.type.name,
                    e,
                    exc_info=True,
                )

    def publish_sync(self, event: Event) -> None:
        """
        Publish from a sync context (e.g., a Qt slot).
        Schedules the async publish on the running event loop.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.publish(event))
            else:
                loop.run_until_complete(self.publish(event))
        except RuntimeError:
            # No event loop - call sync handlers only
            for handler in self._handlers.get(event.type, []):
                try:
                    result = handler(event)
                    # Can't await if no loop, skip async handlers
                    if asyncio.iscoroutine(result):
                        result.close()
                except Exception as e:
                    logger.error("Sync handler error: %s", e)

    def clear_history(self) -> None:
        self._history.clear()

    @property
    def history(self) -> list[Event]:
        return list(self._history)


# Global singleton
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
