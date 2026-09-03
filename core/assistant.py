"""
ULTRON Assistant - Main Orchestrator
Coordinates all subsystems: voice input → LLM → voice output → tools.
This is the central brain of ULTRON.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, TYPE_CHECKING

from config.settings import Settings, get_settings
from core.event_bus import EventBus, Event, EventType, get_event_bus
from core.state import StateManager, AssistantState
from core.conversation import ConversationManager
from core.memory import MemoryManager

if TYPE_CHECKING:
    from ai.llm_provider import LLMProvider
    from voice.stt import STTEngine
    from voice.tts import TTSEngine
    from voice.audio import AudioManager
    from voice.vad import VADDetector
    from voice.wakeword import WakeWordDetector
    from tools.registry import ToolRegistry
    from storage.database import Database
    from security.permissions import PermissionManager

logger = logging.getLogger(__name__)


class Assistant:
    """
    ULTRON's main orchestrator.

    Lifecycle:
      1. initialize() - starts all subsystems
      2. run() - enters the main event loop
      3. shutdown() - gracefully stops everything

    Pipeline per interaction:
      wake word / PTT
        → VAD captures audio
        → STT transcribes
        → intent detection + memory recall
        → LLM streaming (tool calls interleaved)
        → TTS chunks sent to speaker
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bus = bus or get_event_bus()

        # Core components (injected during initialize())
        self.state = StateManager(bus=self.bus)
        self.conversation = ConversationManager()
        self.memory: Optional[MemoryManager] = None
        self.db: Optional["Database"] = None

        # Service components (set by initialize())
        self.llm: Optional["LLMProvider"] = None
        self.stt: Optional["STTEngine"] = None
        self.tts: Optional["TTSEngine"] = None
        self.audio: Optional["AudioManager"] = None
        self.vad: Optional["VADDetector"] = None
        self.wakeword: Optional["WakeWordDetector"] = None
        self.tools: Optional["ToolRegistry"] = None
        self.permissions: Optional["PermissionManager"] = None

        # Runtime state
        self._running = False
        self._interrupt_requested = False
        self._current_response_tokens: list[str] = []
        self._initialization_errors: list[str] = []
        self._startup_status: dict[str, str] = {}

        # Performance tracking
        self._metrics: dict[str, float] = {
            "stt_latency_ms": 0,
            "llm_latency_ms": 0,
            "tts_latency_ms": 0,
            "tokens_per_sec": 0,
            "total_latency_ms": 0,
        }

        self._register_events()

    def _register_events(self) -> None:
        """Subscribe to events that the assistant needs to handle."""
        self.bus.subscribe(EventType.STT_RESULT, self._on_stt_result)
        self.bus.subscribe(EventType.USER_INTERRUPT, self._on_user_interrupt)
        self.bus.subscribe(EventType.TOOL_CONFIRMATION_RESULT, self._on_tool_confirmation)
        self.bus.subscribe(EventType.LLM_TOOL_CALL, self._on_tool_call)
        self.bus.subscribe(EventType.TTS_DONE, self._on_tts_done)

    async def initialize(self) -> bool:
        """
        Initialize all subsystems in the correct order.
        Returns True if initialization succeeded (partial ok, falls back gracefully).
        """
        logger.info("=" * 60)
        logger.info("ULTRON starting up...")
        logger.info("=" * 60)

        await self.state.transition(AssistantState.INITIALIZING, "Starting up")

        # 1. Database
        await self._init_database()

        # 2. Memory
        await self._init_memory()

        # 3. Audio
        await self._init_audio()

        # 4. STT
        await self._init_stt()

        # 5. TTS
        await self._init_tts()

        # 6. LLM
        llm_ok = await self._init_llm()

        # 7. Tools
        await self._init_tools()

        # 8. Wake word
        await self._init_wakeword()

        # Determine initial state
        if llm_ok:
            await self.state.transition(AssistantState.IDLE, "Ready")
            logger.info("ULTRON is ONLINE and ready.")
        else:
            await self.state.transition(AssistantState.OFFLINE, "GPT-OSS not reachable")
            logger.warning("ULTRON started in OFFLINE mode - LLM not available")

        # Publish startup complete
        await self.bus.publish(Event(
            type=EventType.APP_STARTED,
            data={
                "status": self._startup_status,
                "errors": self._initialization_errors,
                "state": self.state.state,
            },
        ))

        return True

    async def _init_database(self) -> None:
        self._update_status("database", "initializing")
        try:
            from storage.database import Database
            self.db = Database(db_path=self.settings.db_path)
            await self.db.initialize()
            self._update_status("database", "ready")
        except Exception as e:
            self._init_error("database", e)

    async def _init_memory(self) -> None:
        self._update_status("memory", "initializing")
        try:
            self.memory = MemoryManager(db=self.db)
            await self.memory.initialize()
            # Inject system info into conversation
            self.conversation.set_system_info(
                "Windows 11, NVIDIA RTX 4060 Ti 16GB, 31GB RAM"
            )
            self._update_status("memory", "ready")
        except Exception as e:
            self._init_error("memory", e)
            self.memory = MemoryManager(db=None)

    async def _init_audio(self) -> None:
        self._update_status("audio", "initializing")
        try:
            from voice.audio import AudioManager
            self.audio = AudioManager(settings=self.settings)
            await self.audio.initialize()
            self._update_status("audio", "ready")
        except Exception as e:
            self._init_error("audio", e)

    async def _init_stt(self) -> None:
        self._update_status("stt", "initializing")
        try:
            from voice.stt import create_stt_engine
            self.stt = create_stt_engine(self.settings, self.bus)
            await self.stt.initialize()
            self._update_status("stt", "ready")
        except Exception as e:
            self._init_error("stt", e)
            self.stt = None   # Ensure it's None so pipeline degrades gracefully

    async def _init_tts(self) -> None:
        self._update_status("tts", "initializing")
        # Try preferred provider, then fall back through options
        providers = [self.settings.tts.provider, "pyttsx3"]
        for provider in providers:
            try:
                import copy
                s = copy.deepcopy(self.settings)
                s.tts.provider = provider
                from voice.tts import create_tts_engine
                engine = create_tts_engine(s, self.bus)
                await engine.initialize()
                self.tts = engine
                if provider != self.settings.tts.provider:
                    self._update_status("tts", f"ready (fallback: {provider})")
                else:
                    self._update_status("tts", f"ready ({provider})")
                return
            except Exception as e:
                if provider == providers[-1]:
                    self._init_error("tts", e)
                    self.tts = None
                else:
                    logger.warning("TTS provider '%s' failed, trying fallback: %s", provider, e)

    async def _init_llm(self) -> bool:
        self._update_status("llm", "connecting")
        try:
            from ai.llm_provider import create_llm_provider
            self.llm = create_llm_provider(self.settings)
            connected = await self.llm.check_connection()
            if connected:
                self._update_status("llm", "connected")
                logger.info("GPT-OSS connected at %s", self.settings.llm.endpoint)
                return True
            else:
                self._update_status("llm", "offline")
                logger.warning("GPT-OSS not reachable at %s", self.settings.llm.endpoint)
                return False
        except Exception as e:
            self._init_error("llm", e)
            return False

    async def _init_tools(self) -> None:
        self._update_status("tools", "initializing")
        try:
            from tools.registry import ToolRegistry
            from security.permissions import PermissionManager
            self.permissions = PermissionManager(settings=self.settings)
            self.tools = ToolRegistry(
                settings=self.settings,
                bus=self.bus,
                permissions=self.permissions,
            )
            self.tools.register_all()
            self._update_status("tools", f"ready ({self.tools.tool_count} tools)")
        except Exception as e:
            self._init_error("tools", e)

    async def _init_wakeword(self) -> None:
        if not self.settings.assistant.wake_word_enabled:
            self._update_status("wakeword", "disabled")
            return

        self._update_status("wakeword", "initializing")
        try:
            from voice.wakeword import create_wakeword_detector
            self.wakeword = create_wakeword_detector(self.settings, self.bus)
            await self.wakeword.initialize()
            self._update_status("wakeword", "active")
        except Exception as e:
            self._init_error("wakeword", e)

    def _update_status(self, component: str, status: str) -> None:
        self._startup_status[component] = status
        logger.info("[%s] %s", component.upper(), status)
        self.bus.publish_sync(Event(
            type=EventType.UI_UPDATE_STATUS,
            data={"component": component, "status": status},
        ))

    def _init_error(self, component: str, error: Exception) -> None:
        msg = f"{component}: {error}"
        self._initialization_errors.append(msg)
        self._startup_status[component] = f"error: {error}"
        logger.error("Failed to initialize %s: %s", component, error, exc_info=True)

    # -------- Main processing pipeline --------

    async def process_text_input(self, text: str) -> Optional[str]:
        """
        Process a text input directly (bypasses voice pipeline).
        Used for text-mode interaction and testing.
        """
        if not text.strip():
            return None

        logger.info("Processing: %s", text[:100])
        start_time = time.monotonic()

        # Check for memory commands first
        if self.memory:
            if remember := self.memory.parse_remember_command(text):
                key, value = remember
                await self.memory.remember(key, value)
                response = f"Got it. I'll remember: {value}"
                await self._deliver_response(response)
                return response

            if forget_key := self.memory.parse_forget_command(text):
                removed = await self.memory.forget(forget_key)
                if removed:
                    response = f"Done. I've forgotten what I knew about '{forget_key}'."
                else:
                    response = f"I don't have any memory about '{forget_key}'."
                await self._deliver_response(response)
                return response

        # Add to conversation
        self.conversation.add_user_message(text)

        # Publish user message event
        await self.bus.publish(Event(
            type=EventType.USER_MESSAGE,
            data={"text": text},
        ))

        # Transition to THINKING
        await self.state.transition(AssistantState.THINKING)

        if self.llm is None:
            error_msg = "GPT-OSS is currently unavailable. Please ensure your local model server is running."
            await self._deliver_response(error_msg)
            await self.state.transition(AssistantState.OFFLINE)
            return error_msg

        # Build the prompt
        memories = self.memory.format_for_prompt() if self.memory else ""
        messages = self.conversation.build_prompt(include_memories=memories)

        # Get tool definitions if tools available
        tool_defs = self.tools.get_tool_definitions() if self.tools else []

        # Stream the response
        response_text = await self._stream_llm_response(
            messages=messages,
            tool_defs=tool_defs,
            start_time=start_time,
        )

        return response_text

    async def _stream_llm_response(
        self,
        messages: list[dict],
        tool_defs: list[dict],
        start_time: float,
    ) -> str:
        """
        Stream a response from the LLM.
        Tokens go to UI immediately.
        Sentence chunks go to TTS as soon as they're complete.
        """
        self._current_response_tokens = []
        self._interrupt_requested = False
        full_response = ""
        first_token_time: Optional[float] = None
        token_count = 0
        tts_buffer = ""
        llm_start = time.monotonic()

        try:
            await self.bus.publish(Event(type=EventType.LLM_REQUEST_START))

            async for chunk in self.llm.stream(
                messages=messages,
                tools=tool_defs,
            ):
                if self._interrupt_requested:
                    logger.info("LLM generation interrupted by user")
                    break

                if chunk.get("type") == "tool_call":
                    # Handle tool call from model
                    await self.bus.publish(Event(
                        type=EventType.LLM_TOOL_CALL,
                        data=chunk,
                    ))
                    continue

                token = chunk.get("content", "")
                if not token:
                    continue

                if first_token_time is None:
                    first_token_time = time.monotonic()
                    latency_ms = (first_token_time - llm_start) * 1000
                    self._metrics["llm_latency_ms"] = latency_ms
                    logger.info("First token received (%.0f ms)", latency_ms)

                token_count += 1
                full_response += token
                tts_buffer += token
                self._current_response_tokens.append(token)

                # Stream to UI
                await self.bus.publish(Event(
                    type=EventType.LLM_TOKEN,
                    data={"token": token, "accumulated": full_response},
                ))

                # Send complete sentences to TTS
                if self.tts and self._has_sentence_boundary(tts_buffer):
                    sentence, tts_buffer = self._split_at_sentence(tts_buffer)
                    if sentence.strip():
                        await self._send_to_tts(sentence)

            # Send remaining buffer
            if tts_buffer.strip() and self.tts and not self._interrupt_requested:
                await self._send_to_tts(tts_buffer)

        except Exception as e:
            logger.error("LLM streaming error: %s", e, exc_info=True)
            error_msg = "I encountered an error while generating a response. Please try again."
            full_response = error_msg
            await self.bus.publish(Event(
                type=EventType.LLM_ERROR,
                data={"error": str(e)},
                error=e,
            ))

        finally:
            duration_ms = (time.monotonic() - llm_start) * 1000
            if first_token_time and token_count > 0:
                duration_s = time.monotonic() - llm_start
                self._metrics["tokens_per_sec"] = token_count / max(duration_s, 0.001)

            await self.bus.publish(Event(
                type=EventType.LLM_RESPONSE_COMPLETE,
                data={
                    "text": full_response,
                    "tokens": token_count,
                    "duration_ms": duration_ms,
                },
            ))

        # Store in conversation
        total_latency = (time.monotonic() - start_time) * 1000
        self._metrics["total_latency_ms"] = total_latency
        self.conversation.add_assistant_message(
            full_response,
            latency_ms=total_latency,
            tokens=token_count,
        )

        await self.bus.publish(Event(
            type=EventType.ASSISTANT_MESSAGE,
            data={"text": full_response},
        ))

        # Return to IDLE if TTS is not going to handle it
        if self.tts is None and self.state.state == AssistantState.THINKING:
            await self.state.transition(AssistantState.IDLE)

        return full_response

    async def _send_to_tts(self, text: str) -> None:
        """Send a text chunk to TTS for immediate audio synthesis."""
        if self.tts is None or not text.strip():
            return
        try:
            await self.state.transition(AssistantState.SPEAKING)
            await self.tts.speak(text)
        except Exception as e:
            logger.error("TTS error: %s", e)

    async def _deliver_response(self, text: str) -> None:
        """Publish a response text and optionally speak it."""
        await self.bus.publish(Event(
            type=EventType.ASSISTANT_MESSAGE,
            data={"text": text},
        ))
        if self.tts:
            await self._send_to_tts(text)

    def _has_sentence_boundary(self, text: str) -> bool:
        """Check if text contains a complete sentence boundary."""
        import re
        return bool(re.search(r'[.!?]\s', text))

    def _split_at_sentence(self, text: str) -> tuple[str, str]:
        """
        Split text at the last sentence boundary.
        Returns (complete_sentences, remainder).
        """
        import re
        matches = list(re.finditer(r'[.!?]\s+', text))
        if not matches:
            return text, ""
        last = matches[-1]
        return text[:last.end()], text[last.end():]

    # -------- Event handlers --------

    async def _on_stt_result(self, event: Event) -> None:
        """Handle completed speech-to-text transcription."""
        text = event.data.get("text", "").strip()
        if not text:
            await self.state.transition(AssistantState.IDLE)
            return

        logger.info("Transcription: %s", text)
        await self.state.transition(AssistantState.PROCESSING)
        await self.process_text_input(text)

    async def _on_user_interrupt(self, event: Event) -> None:
        """User interrupted - stop current speech and reset."""
        self._interrupt_requested = True
        if self.tts:
            await self.tts.stop()
        logger.info("Interrupted by user")

    async def _on_tool_call(self, event: Event) -> None:
        """Execute a tool call requested by the LLM."""
        if self.tools is None:
            return

        tool_data = event.data
        tool_name = tool_data.get("name", "")
        tool_args = tool_data.get("arguments", {})

        await self.state.transition(AssistantState.TOOL_RUNNING)

        try:
            result = await self.tools.execute(tool_name, tool_args)
            self.conversation.add_tool_result(tool_name, str(result))
            await self.bus.publish(Event(
                type=EventType.TOOL_CALL_RESULT,
                data={"tool": tool_name, "result": result},
            ))
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            self.conversation.add_tool_result(tool_name, f"Error: {e}")
            await self.bus.publish(Event(
                type=EventType.TOOL_CALL_ERROR,
                data={"tool": tool_name, "error": str(e)},
            ))
        finally:
            await self.state.transition(AssistantState.THINKING)

    async def _on_tool_confirmation(self, event: Event) -> None:
        """Handle user's response to a tool confirmation dialog."""
        approved = event.data.get("approved", False)
        if not approved:
            await self._deliver_response("Understood. I've cancelled that action.")
            await self.state.transition(AssistantState.IDLE)

    async def _on_tts_done(self, event: Event) -> None:
        """TTS finished speaking - return to idle."""
        if self.state.state == AssistantState.SPEAKING:
            await self.state.transition(AssistantState.IDLE)

    # -------- Lifecycle --------

    async def run(self) -> None:
        """Enter the main run loop (driven by events, not polling)."""
        self._running = True
        logger.info("ULTRON main loop started")

        # Start wake word detection
        if self.wakeword:
            asyncio.create_task(self.wakeword.run())

        try:
            while self._running:
                await asyncio.sleep(0.1)  # Heartbeat; actual work is event-driven
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully stop all subsystems."""
        logger.info("ULTRON shutting down...")
        self._running = False

        if self.tts:
            await self.tts.stop()
        if self.wakeword:
            await self.wakeword.stop()
        if self.audio:
            await self.audio.stop()
        if self.db:
            await self.db.close()

        await self.bus.publish(Event(type=EventType.APP_STOPPING))
        logger.info("ULTRON shutdown complete.")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def startup_status(self) -> dict[str, str]:
        return dict(self._startup_status)

    @property
    def metrics(self) -> dict[str, float]:
        return dict(self._metrics)
