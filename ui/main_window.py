"""
ULTRON Main Window
The primary UI window. Futuristic dark design with:
- Left panel: animated orb + status
- Center: conversation chat
- Right panel: performance metrics
- Bottom: input bar with PTT
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QColor, QFont, QIcon, QKeyEvent, QPalette, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QSplitter, QSystemTrayIcon,
    QMenu, QMessageBox, QSizePolicy
)

from core.state import AssistantState
from core.event_bus import Event, EventType, get_event_bus
from ui.animations import OrbWidget
from ui.components.chat_widget import ChatWidget
from ui.components.panels import StatusPanel, MetricsPanel

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Stylesheet
# ──────────────────────────────────────────

MAIN_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #050a0f;
    color: #c0d8e8;
}
QLabel {
    color: #c0d8e8;
}
QPushButton {
    background-color: #0d1f3c;
    color: #00d4ff;
    border: 1px solid #1a3a6e;
    border-radius: 6px;
    padding: 6px 14px;
    font-family: Consolas;
    font-size: 11px;
    letter-spacing: 1px;
}
QPushButton:hover {
    background-color: #142850;
    border-color: #00d4ff;
}
QPushButton:pressed {
    background-color: #001a33;
}
QPushButton:disabled {
    color: #446;
    border-color: #223;
}
QLineEdit {
    background-color: #070f1a;
    color: #c0d8f0;
    border: 1px solid #1a3a5e;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 13px;
    font-family: 'Segoe UI';
    selection-background-color: #1a4070;
}
QLineEdit:focus {
    border-color: #00d4ff;
}
QSplitter::handle {
    background-color: #0d2040;
}
QScrollBar:vertical {
    background: #050a0f;
    width: 6px;
}
"""


class AsyncBridge(QObject):
    """
    Bridge between the Qt main thread and the asyncio event loop.
    Allows async operations to update the Qt UI via signals.
    """
    state_changed = pyqtSignal(object)           # AssistantState
    status_updated = pyqtSignal(str, str)         # component, status
    user_message = pyqtSignal(str)
    assistant_token = pyqtSignal(str)
    assistant_message_start = pyqtSignal()
    assistant_message_complete = pyqtSignal(str)
    metrics_updated = pyqtSignal(dict)
    confirmation_needed = pyqtSignal(str, str, str)  # id, tool, message
    notification = pyqtSignal(str)


class MainWindow(QMainWindow):
    """ULTRON's main application window."""

    def __init__(self, assistant=None, settings=None) -> None:
        super().__init__()
        self._assistant = assistant
        self._settings = settings
        self._bridge = AsyncBridge()
        self._bus = get_event_bus()
        self._ptt_active = False

        self._setup_window()
        self._setup_ui()
        self._setup_shortcuts()
        self._connect_bridge()
        self._subscribe_events()

        # System metrics update timer
        self._metrics_timer = QTimer(self)
        self._metrics_timer.timeout.connect(self._update_system_metrics)
        self._metrics_timer.start(2000)

        logger.info("Main window initialized")

    def _setup_window(self) -> None:
        """Configure the main window."""
        cfg = self._settings.ui if self._settings else None
        title = "ULTRON"
        self.setWindowTitle(title)
        self.setMinimumSize(900, 600)

        w = cfg.window_width if cfg else 1200
        h = cfg.window_height if cfg else 800
        self.resize(w, h)

        # Center on screen
        screen = self.screen().availableGeometry()
        self.move(
            (screen.width() - w) // 2,
            (screen.height() - h) // 2,
        )

        self.setStyleSheet(MAIN_STYLESHEET)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

    def _setup_ui(self) -> None:
        """Build the UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header bar ──
        header = self._make_header()
        main_layout.addWidget(header)

        # ── Main content area ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left: orb + status
        left_panel = self._make_left_panel()
        splitter.addWidget(left_panel)

        # Center: chat
        self._chat = ChatWidget()
        self._chat.setMinimumWidth(400)
        splitter.addWidget(self._chat)

        # Right: metrics
        self._metrics_panel = MetricsPanel()
        self._metrics_panel.setFixedWidth(200)
        splitter.addWidget(self._metrics_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([280, 700, 200])

        main_layout.addWidget(splitter, stretch=1)

        # ── Input bar ──
        input_bar = self._make_input_bar()
        main_layout.addWidget(input_bar)

    def _make_header(self) -> QWidget:
        """Top header bar with logo, name, status."""
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet("""
            QFrame {
                background-color: #020810;
                border-bottom: 1px solid #0d2040;
            }
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)

        # Logo / name
        logo = QLabel("⬡ ULTRON")
        logo.setStyleSheet(
            "color: #00d4ff; font-size: 18px; font-family: Consolas; "
            "font-weight: bold; letter-spacing: 4px;"
        )
        layout.addWidget(logo)
        layout.addStretch()

        # Status chip
        self._header_status = QLabel("ONLINE")
        self._header_status.setStyleSheet(
            "color: #00ff88; font-size: 10px; font-family: Consolas; "
            "background: #001a0f; border: 1px solid #00ff8844; "
            "border-radius: 4px; padding: 2px 8px;"
        )
        layout.addWidget(self._header_status)

        # Settings/close buttons
        for text, slot in [("⚙", self._open_settings), ("✕", self.close)]:
            btn = QPushButton(text)
            btn.setFixedSize(32, 32)
            btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; color: #445; font-size: 14px; }
                QPushButton:hover { color: #00d4ff; }
            """)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        return header

    def _make_left_panel(self) -> QWidget:
        """Left panel: orb animation + status indicators."""
        panel = QWidget()
        panel.setFixedWidth(280)
        panel.setStyleSheet("background-color: #030810;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Orb
        self._orb = OrbWidget()
        self._orb.setFixedHeight(280)
        layout.addWidget(self._orb, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Status panel
        self._status_panel = StatusPanel()
        layout.addWidget(self._status_panel)

        layout.addStretch()

        # Voice mode toggle
        self._voice_btn = QPushButton("🎤  VOICE MODE: ON")
        self._voice_btn.setCheckable(True)
        self._voice_btn.setChecked(True)
        self._voice_btn.setStyleSheet("""
            QPushButton {
                background: #0a1e0a;
                border: 1px solid #1a5a1a;
                color: #00cc44;
                font-size: 10px;
                font-family: Consolas;
                padding: 6px;
                border-radius: 6px;
            }
            QPushButton:checked {
                background: #0a1e0a;
                border-color: #00cc44;
            }
            QPushButton:!checked {
                background: #0a0a0a;
                border-color: #333;
                color: #666;
            }
        """)
        self._voice_btn.toggled.connect(self._toggle_voice)
        layout.addWidget(self._voice_btn)

        return panel

    def _make_input_bar(self) -> QWidget:
        """Bottom input bar for text input."""
        bar = QFrame()
        bar.setFixedHeight(60)
        bar.setStyleSheet("""
            QFrame {
                background-color: #030810;
                border-top: 1px solid #0d2040;
            }
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # PTT button
        self._ptt_btn = QPushButton("⬤")
        self._ptt_btn.setFixedSize(40, 40)
        self._ptt_btn.setStyleSheet("""
            QPushButton {
                background: #0a1020;
                border: 2px solid #1a3a6e;
                border-radius: 20px;
                color: #335577;
                font-size: 16px;
            }
            QPushButton:pressed {
                background: #001530;
                border-color: #00d4ff;
                color: #00d4ff;
            }
        """)
        self._ptt_btn.pressed.connect(self._ptt_press)
        self._ptt_btn.released.connect(self._ptt_release)
        layout.addWidget(self._ptt_btn)

        # Text input
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message or press Ctrl+Space for voice...")
        self._input.returnPressed.connect(self._send_text)
        layout.addWidget(self._input)

        # Send button
        send_btn = QPushButton("SEND")
        send_btn.setFixedWidth(70)
        send_btn.clicked.connect(self._send_text)
        layout.addWidget(send_btn)

        # Clear button
        clear_btn = QPushButton("CLR")
        clear_btn.setFixedWidth(50)
        clear_btn.setStyleSheet("""
            QPushButton { color: #446; border-color: #223; }
            QPushButton:hover { color: #ff4444; border-color: #ff4444; }
        """)
        clear_btn.clicked.connect(self._clear_conversation)
        layout.addWidget(clear_btn)

        return bar

    def _setup_shortcuts(self) -> None:
        """Register keyboard shortcuts."""
        # Ctrl+Space: Push-to-talk
        ptt_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        ptt_shortcut.activated.connect(self._toggle_ptt)

    def _connect_bridge(self) -> None:
        """Connect the async bridge signals to Qt UI slots."""
        self._bridge.state_changed.connect(self._on_state_changed)
        self._bridge.status_updated.connect(self._on_status_updated)
        self._bridge.user_message.connect(self._on_user_message)
        self._bridge.assistant_message_start.connect(self._chat.begin_assistant_message)
        self._bridge.assistant_token.connect(self._chat.append_token)
        self._bridge.assistant_message_complete.connect(self._chat.finalize_assistant_message)
        self._bridge.metrics_updated.connect(self._on_metrics_updated)
        self._bridge.confirmation_needed.connect(self._on_confirmation_needed)
        self._bridge.notification.connect(self._show_notification)

    def _subscribe_events(self) -> None:
        """Subscribe to event bus events. These run in async context."""
        bus = self._bus
        bus.subscribe(EventType.STATE_CHANGED, self._ev_state_changed)
        bus.subscribe(EventType.UI_UPDATE_STATUS, self._ev_status_update)
        bus.subscribe(EventType.USER_MESSAGE, self._ev_user_message)
        bus.subscribe(EventType.LLM_REQUEST_START, self._ev_llm_start)
        bus.subscribe(EventType.LLM_TOKEN, self._ev_llm_token)
        bus.subscribe(EventType.LLM_RESPONSE_COMPLETE, self._ev_llm_complete)
        bus.subscribe(EventType.TOOL_CONFIRMATION_NEEDED, self._ev_confirmation_needed)
        bus.subscribe(EventType.UI_NOTIFICATION, self._ev_notification)
        bus.subscribe(EventType.UI_UPDATE_METRICS, self._ev_metrics_update)

    # ──── Event handlers (async, emit to bridge) ────

    def _ev_state_changed(self, event: Event) -> None:
        state = event.data.get("state")
        if state:
            self._bridge.state_changed.emit(state)

    def _ev_status_update(self, event: Event) -> None:
        comp = event.data.get("component", "")
        status = event.data.get("status", "")
        self._bridge.status_updated.emit(comp, status)

    def _ev_user_message(self, event: Event) -> None:
        text = event.data.get("text", "")
        self._bridge.user_message.emit(text)

    def _ev_llm_start(self, event: Event) -> None:
        self._bridge.assistant_message_start.emit()

    def _ev_llm_token(self, event: Event) -> None:
        token = event.data.get("token", "")
        if token:
            self._bridge.assistant_token.emit(token)

    def _ev_llm_complete(self, event: Event) -> None:
        text = event.data.get("text", "")
        self._bridge.assistant_message_complete.emit(text)

    def _ev_confirmation_needed(self, event: Event) -> None:
        req_id = event.data.get("id", "")
        tool = event.data.get("tool", "")
        message = event.data.get("message", "")
        self._bridge.confirmation_needed.emit(req_id, tool, message)

    def _ev_notification(self, event: Event) -> None:
        msg = event.data.get("message", "")
        self._bridge.notification.emit(msg)

    def _ev_metrics_update(self, event: Event) -> None:
        self._bridge.metrics_updated.emit(event.data)

    # ──── Qt UI slots ────

    def _on_state_changed(self, state: AssistantState) -> None:
        """Update UI to reflect new state."""
        self._orb.set_state(state)

        labels = {
            AssistantState.IDLE: ("ONLINE", "#00ff88"),
            AssistantState.LISTENING: ("LISTENING", "#00d4ff"),
            AssistantState.PROCESSING: ("PROCESSING", "#4488ff"),
            AssistantState.THINKING: ("THINKING", "#aa44ff"),
            AssistantState.SPEAKING: ("SPEAKING", "#00ff88"),
            AssistantState.TOOL_RUNNING: ("EXECUTING", "#ffaa00"),
            AssistantState.CONFIRMING: ("CONFIRM?", "#ffaa00"),
            AssistantState.ERROR: ("ERROR", "#ff4444"),
            AssistantState.OFFLINE: ("OFFLINE", "#666666"),
        }
        text, color = labels.get(state, ("...", "#888888"))
        self._header_status.setText(text)
        self._header_status.setStyleSheet(
            f"color: {color}; font-size: 10px; font-family: Consolas; "
            f"background: #000; border: 1px solid {color}55; "
            f"border-radius: 4px; padding: 2px 8px;"
        )

    def _on_status_updated(self, component: str, status: str) -> None:
        self._status_panel.update_component(component, status)

    def _on_user_message(self, text: str) -> None:
        self._chat.add_user_message(text)

    def _on_metrics_updated(self, data: dict) -> None:
        stt = data.get("stt_latency_ms", 0)
        llm = data.get("llm_latency_ms", 0)
        tts = data.get("tts_latency_ms", 0)
        tok = data.get("tokens_per_sec", 0)
        self._metrics_panel.update_latencies(stt, llm, tts, tok)

    def _on_confirmation_needed(self, req_id: str, tool: str, message: str) -> None:
        """Show a confirmation dialog for a tool operation."""
        box = QMessageBox(self)
        box.setWindowTitle("Confirm Action")
        box.setText(f"ULTRON wants to: {tool}")
        box.setInformativeText(message)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setStyleSheet("""
            QMessageBox { background: #0a1020; color: #c0d8e8; }
            QPushButton { min-width: 80px; }
        """)
        result = box.exec()
        approved = result == QMessageBox.StandardButton.Yes

        # Publish result back
        self._bus.publish_sync(Event(
            type=EventType.TOOL_CONFIRMATION_RESULT,
            data={"id": req_id, "approved": approved},
        ))

    def _show_notification(self, message: str) -> None:
        self._chat.add_system_message(message)

    # ──── Input handling ────

    def _send_text(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        if self._assistant:
            asyncio.ensure_future(self._assistant.process_text_input(text))

    def _ptt_press(self) -> None:
        """Push-to-talk: start listening."""
        self._ptt_active = True
        self._bus.publish_sync(Event(
            type=EventType.VAD_SPEECH_START,
            data={"source": "ptt"},
        ))

    def _ptt_release(self) -> None:
        """Push-to-talk: stop listening."""
        self._ptt_active = False
        self._bus.publish_sync(Event(
            type=EventType.VAD_SPEECH_END,
            data={"source": "ptt"},
        ))

    def _toggle_ptt(self) -> None:
        """Keyboard shortcut handler for push-to-talk."""
        if not self._ptt_active:
            self._ptt_press()
        else:
            self._ptt_release()

    def _toggle_voice(self, checked: bool) -> None:
        self._voice_btn.setText(
            "🎤  VOICE MODE: ON" if checked else "🔇  VOICE MODE: OFF"
        )

    def _clear_conversation(self) -> None:
        self._chat.clear()
        if self._assistant:
            self._assistant.conversation.clear()

    def _open_settings(self) -> None:
        from PyQt6.QtWidgets import QDialog
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Settings")
        dlg.setText(
            "Edit config.yaml in the config/ folder to change settings.\n"
            "Restart ULTRON for changes to take effect."
        )
        dlg.exec()

    def _update_system_metrics(self) -> None:
        """Update CPU/RAM/GPU display every 2 seconds."""
        try:
            import psutil
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent

            # GPU via nvidia-smi
            gpu = 0.0
            vram = 0.0
            try:
                import subprocess
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    parts = result.stdout.strip().split(",")
                    if len(parts) >= 3:
                        gpu = float(parts[0].strip())
                        vram_used = float(parts[1].strip())
                        vram_total = float(parts[2].strip())
                        vram = (vram_used / vram_total * 100) if vram_total > 0 else 0
            except Exception:
                pass

            self._metrics_panel.update_system(cpu, ram, gpu, vram)

            # Also update assistant metrics if available
            if self._assistant:
                m = self._assistant.metrics
                self._metrics_panel.update_latencies(
                    stt_ms=m.get("stt_latency_ms", 0),
                    llm_ms=m.get("llm_latency_ms", 0),
                    tts_ms=m.get("tts_latency_ms", 0),
                    tokens_sec=m.get("tokens_per_sec", 0),
                )
        except ImportError:
            pass

    def closeEvent(self, event) -> None:
        if self._assistant:
            asyncio.ensure_future(self._assistant.shutdown())
        super().closeEvent(event)
