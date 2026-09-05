"""
services/llm_worker.py
QThread that owns an asyncio event loop and the ULTRON Assistant.
Exposes Qt signals so the rest of the UI stays on the main thread.

Signals (emitted on the Qt main thread via signal/slot):
  token_ready(str)      — a streaming token from the LLM
  response_done()       — full response finished
  llm_status(str)       — "online" | "offline"
  thinking_changed(bool) — True = THINKING, False = done
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from PySide6.QtCore import QThread, Signal, QObject

logger = logging.getLogger(__name__)


class LLMWorker(QObject):
    """
    Runs in a dedicated QThread.
    Owns an asyncio event loop for the async Assistant stack.
    Thread-safe: submit_command() is the only public entry point from
    the Qt main thread.
    """

    token_ready       = Signal(str)   # single streaming token
    response_done     = Signal()      # full response finished (last token sent)
    llm_status        = Signal(str)   # "online" | "offline"
    thinking_changed  = Signal(bool)  # True = started, False = finished

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._assistant = None
        self._ready = threading.Event()   # set when loop + assistant are initialised
        self._is_online = False

    # ------------------------------------------------------------------
    # Called from the QThread once it has started
    # ------------------------------------------------------------------
    def run_loop(self) -> None:
        """Entry point — called by the owning QThread's run()."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_main())
        finally:
            self._loop.close()

    async def _async_main(self) -> None:
        """Initialise the Assistant, then spin the event loop forever."""
        try:
            from core.assistant import Assistant
            self._assistant = Assistant()
            ok = await self._assistant.initialize()

            # Check if LLM actually came up
            self._is_online = (
                self._assistant.llm is not None
                and await self._assistant.llm.check_connection()
            )
        except Exception as e:
            logger.error("LLMWorker: Assistant init failed: %s", e, exc_info=True)
            self._is_online = False

        status = "online" if self._is_online else "offline"
        self.llm_status.emit(status)
        logger.info("LLMWorker: LLM status = %s", status)

        # Signal that we're ready to accept commands
        self._ready.set()

        # Keep the loop alive
        while True:
            await asyncio.sleep(3600)

    # ------------------------------------------------------------------
    # Public API (called from Qt main thread)
    # ------------------------------------------------------------------
    def submit_command(self, text: str) -> None:
        """
        Thread-safe: schedule processing of `text` on the asyncio loop.
        Returns immediately; results come back via signals.
        """
        if self._loop is None or not self._loop.is_running():
            logger.warning("LLMWorker: loop not running, ignoring command")
            return
        asyncio.run_coroutine_threadsafe(
            self._process(text),
            self._loop,
        )

    @property
    def is_online(self) -> bool:
        return self._is_online

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set()

    # ------------------------------------------------------------------
    # Async processing
    # ------------------------------------------------------------------
    async def _process(self, text: str) -> None:
        """
        Run one turn through the Assistant pipeline.
        Tokens are forwarded to Qt via signal (thread-safe).
        """
        if self._assistant is None:
            self.token_ready.emit("[LLM NOT INITIALISED]")
            self.response_done.emit()
            return

        self.thinking_changed.emit(True)

        # Subscribe to streaming tokens from the event bus
        from core.event_bus import EventType

        def _on_token(event) -> None:
            token = event.data.get("token", "")
            if token:
                self.token_ready.emit(token)

        self._assistant.bus.subscribe(EventType.LLM_TOKEN, _on_token)

        try:
            await self._assistant.process_text_input(text)
        except Exception as e:
            logger.error("LLMWorker: process error: %s", e, exc_info=True)
            self.token_ready.emit(f"\n[ERROR: {e}]")
        finally:
            self._assistant.bus.unsubscribe(EventType.LLM_TOKEN, _on_token)
            self.thinking_changed.emit(False)
            self.response_done.emit()


# ---------------------------------------------------------------------------
# The actual QThread wrapper
# ---------------------------------------------------------------------------
class LLMThread(QThread):
    """Thin QThread shell — runs LLMWorker.run_loop() in the thread."""

    def __init__(self, worker: LLMWorker, parent=None):
        super().__init__(parent)
        self._worker = worker

    def run(self) -> None:
        self._worker.run_loop()
