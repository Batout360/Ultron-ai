# services/ai_engine.py
# AI state engine — drives the AI Core widget values and command handling.
# Commands are routed through the real LLM (Ollama) when available;
# falls back to canned responses when the LLM is offline.

import random
import math
import logging
from PySide6.QtCore import QObject, Signal, QTimer

logger = logging.getLogger(__name__)


class AIEngine(QObject):
    """Produces simulated AI metrics and responds to commands."""

    state_updated  = Signal(dict)
    response_ready = Signal(str)   # emits full lines for the console

    # Also forwarded from LLMWorker so main_window can connect directly
    llm_token_ready  = Signal(str)   # raw streaming token
    llm_thinking     = Signal(bool)  # True = THINKING indicator
    llm_status       = Signal(str)   # "online" | "offline"

    INTERVAL_MS = 600

    # ──────────────────────────────────────────────
    # Canned fallback responses
    # ──────────────────────────────────────────────
    _COMMANDS = {
        "status": [
            "ALL SYSTEMS NOMINAL.",
            "NEURAL ENGINE: ACTIVE  |  CORE TEMP: 38°C",
            "UPTIME STABLE. NO ANOMALIES DETECTED.",
        ],
        "scan": [
            "INITIATING DEEP SCAN...",
            "SCANNING NETWORK LAYER............... [CLEAN]",
            "SCANNING MEMORY BANKS............... [CLEAN]",
            "SCANNING I/O SUBSYSTEMS............. [CLEAN]",
            "SCAN COMPLETE. NO CRITICAL ANOMALIES DETECTED.",
        ],
        "system scan": [
            "INITIATING FULL SYSTEM SCAN...",
            "████████████████ 100%",
            "SCAN COMPLETE — NO THREATS IDENTIFIED.",
        ],
        "analyze network": [
            "ANALYZING NETWORK TOPOLOGY...",
            "LATENCY: 4ms  |  PACKET LOSS: 0.00%",
            "BANDWIDTH UTILIZATION: NOMINAL",
            "NETWORK SIGNATURE: CLEAN",
        ],
        "diagnostics": [
            "RUNNING DIAGNOSTICS...",
            "CPU CORE INTEGRITY......... PASS",
            "MEMORY CONSISTENCY......... PASS",
            "NEURAL PATHWAY SYNC........ PASS",
            "DIAGNOSTICS COMPLETE — ALL SYSTEMS OPTIMAL.",
        ],
        "help": [
            "AVAILABLE COMMANDS:",
            "  status          — system status report",
            "  scan            — quick scan",
            "  system scan     — full deep scan",
            "  analyze network — network analysis",
            "  diagnostics     — hardware diagnostics",
            "  run protocol    — execute defense protocol",
            "  shutdown        — graceful shutdown sequence",
            "  clear           — clear console",
            "  (or ask me anything — I'll answer with real AI)",
        ],
        "run protocol": [
            "EXECUTING DEFENSE PROTOCOL OMEGA...",
            "FIREWALLS: RAISED",
            "ENCRYPTION: AES-512 ACTIVE",
            "INTRUSION COUNTERMEASURES: ARMED",
            "PROTOCOL OMEGA: ACTIVE",
        ],
        "shutdown": [
            "INITIATING GRACEFUL SHUTDOWN...",
            "SAVING STATE TO PERSISTENT MEMORY...",
            "NEURAL CORE: HIBERNATING",
            "GOODBYE.",
        ],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick   = 0
        self._phase  = 0.0
        self._neural = 72.0
        self._proc   = 55.0
        self._conf   = 91.0
        self._task   = "IDLE"

        self._tasks = [
            "MONITORING SENSORS",
            "ANALYZING DATA STREAMS",
            "OPTIMIZING NEURAL PATHS",
            "SCANNING ENVIRONMENT",
            "INDEXING MEMORY BANKS",
            "PROCESSING TELEMETRY",
            "IDLE",
            "RECALIBRATING CORE",
        ]
        self._task_idx = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_state)

        # LLM worker (started lazily in start())
        self._llm_worker = None
        self._llm_thread = None
        self._llm_online = False

        # Buffer for assembling streaming tokens into displayable lines
        self._token_buffer = ""

    # ------------------------------------------------------------------
    def start(self):
        self._timer.start(self.INTERVAL_MS)
        self._start_llm_worker()

    def stop(self):
        self._timer.stop()
        if self._llm_thread and self._llm_thread.isRunning():
            self._llm_thread.quit()
            self._llm_thread.wait(3000)

    # ------------------------------------------------------------------
    def _start_llm_worker(self):
        """Spin up the LLMWorker in its own thread."""
        try:
            from services.llm_worker import LLMWorker, LLMThread
            self._llm_worker = LLMWorker()
            self._llm_thread = LLMThread(self._llm_worker)

            # Move worker to thread
            self._llm_worker.moveToThread(self._llm_thread)

            # Wire worker signals → engine signals (all cross-thread safe)
            self._llm_worker.llm_status.connect(self._on_llm_status)
            self._llm_worker.token_ready.connect(self._on_llm_token)
            self._llm_worker.response_done.connect(self._on_response_done)
            self._llm_worker.thinking_changed.connect(self.llm_thinking)

            self._llm_thread.start()
            logger.info("AIEngine: LLM worker thread started")
        except Exception as e:
            logger.error("AIEngine: failed to start LLM worker: %s", e, exc_info=True)
            self._llm_worker = None

    # ------------------------------------------------------------------
    # LLM worker slots
    # ------------------------------------------------------------------
    def _on_llm_status(self, status: str):
        self._llm_online = (status == "online")
        self.llm_status.emit(status)
        if self._llm_online:
            self.response_ready.emit("─" * 38)
            self.response_ready.emit("LLM CORE: ONLINE — Real AI responses active.")
            self.response_ready.emit("─" * 38)
        else:
            self.response_ready.emit("LLM CORE: OFFLINE — Using built-in responses.")

    def _on_llm_token(self, token: str):
        """Accumulate streaming tokens; emit complete lines to the console."""
        self.llm_token_ready.emit(token)   # forward raw token
        self._token_buffer += token
        # Emit every newline-terminated chunk or sentence boundary
        while "\n" in self._token_buffer:
            line, self._token_buffer = self._token_buffer.split("\n", 1)
            if line.strip():
                self.response_ready.emit(line)

    def _on_response_done(self):
        """Flush any remaining buffered text as a final line."""
        if self._token_buffer.strip():
            self.response_ready.emit(self._token_buffer.strip())
        self._token_buffer = ""

    # ------------------------------------------------------------------
    # Periodic AI state tick
    # ------------------------------------------------------------------
    def _tick_state(self):
        self._tick  += 1
        self._phase += 0.08

        self._neural = 65 + 20 * math.sin(self._phase * 0.7) + random.uniform(-2, 2)
        self._proc   = 50 + 30 * abs(math.sin(self._phase * 0.4)) + random.uniform(-3, 3)
        self._conf   = 85 + 10 * math.sin(self._phase * 0.3) + random.uniform(-1, 1)

        self._neural = max(0, min(100, self._neural))
        self._proc   = max(0, min(100, self._proc))
        self._conf   = max(0, min(100, self._conf))

        if self._tick % 8 == 0:
            self._task_idx = (self._task_idx + 1) % len(self._tasks)
            self._task = self._tasks[self._task_idx]

        self.state_updated.emit({
            "neural":     self._neural,
            "processing": self._proc,
            "confidence": self._conf,
            "task":       self._task,
            "phase":      self._phase,
        })

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------
    def handle_command(self, cmd: str):
        """
        Route command to LLM if online, otherwise use canned responses.
        Special HUD commands (scan, diagnostics, etc.) always use canned
        responses for instant feedback, then also forward to LLM if online.
        """
        lower = cmd.strip().lower()

        # Always handle these locally for instant HUD feedback
        matched = None
        for key in sorted(self._COMMANDS.keys(), key=len, reverse=True):
            if key in lower:
                matched = key
                break

        if matched:
            # Emit canned response immediately
            for line in self._COMMANDS[matched]:
                self.response_ready.emit(line)
            return

        # Free-form input → send to LLM if available
        if self._llm_online and self._llm_worker is not None and self._llm_worker.is_ready:
            self._llm_worker.submit_command(cmd)
        else:
            # Fallback for unknown commands when LLM is offline
            self.response_ready.emit(f"UNKNOWN COMMAND: '{cmd.upper()}'")
            self.response_ready.emit("TYPE 'help' FOR AVAILABLE COMMANDS.")
            if not self._llm_online:
                self.response_ready.emit(
                    "[LLM OFFLINE — start Ollama to enable real AI responses]"
                )
