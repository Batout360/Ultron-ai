# ui/system_log.py
# Live scrolling system log widget — Pure Holographic Orange

import random
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel
from PySide6.QtCore    import Qt, QTimer
from PySide6.QtGui     import QPainter, QColor, QFont, QPen
import theme as C


# ---------------------------------------------------------------------------
# Log entry model
# ---------------------------------------------------------------------------
class LogEntry:
    LEVEL_INFO    = "INFO"
    LEVEL_OK      = "OK"
    LEVEL_WARN    = "WARN"
    LEVEL_ALERT   = "ALERT"
    LEVEL_SYSTEM  = "SYS"

    def __init__(self, message: str, level: str = "INFO"):
        self.ts      = datetime.now().strftime("%H:%M:%S")
        self.message = message
        self.level   = level

    def color(self) -> str:
        return {
            "INFO":  C.COLOR_TEXT_MID,
            "OK":    C.COLOR_PRIMARY,
            "WARN":  C.COLOR_WARN,
            "ALERT": C.COLOR_CRITICAL,
            "SYS":   C.COLOR_ACCENT,
        }.get(self.level, C.COLOR_TEXT_MID)


# ---------------------------------------------------------------------------
# System event pool for simulation
# ---------------------------------------------------------------------------
_EVENTS = [
    ("MONITORING SYSTEM RESOURCES",    "SYS"),
    ("NEURAL ENGINE TICK PROCESSED",   "INFO"),
    ("TELEMETRY DATA UPDATED",         "INFO"),
    ("MEMORY SCAN — NO ANOMALIES",     "OK"),
    ("NETWORK HEARTBEAT RECEIVED",     "OK"),
    ("CPU LOAD WITHIN NORMAL RANGE",   "INFO"),
    ("AI CORE CYCLE COMPLETE",         "SYS"),
    ("ENTROPY CHECK PASSED",           "OK"),
    ("DEEP PACKET INSPECTION CLEAR",   "OK"),
    ("PROCESS TABLE VERIFIED",         "INFO"),
    ("THERMAL SENSOR READ",            "INFO"),
    ("UPLINK CHANNEL STABLE",          "OK"),
    ("FIREWALL RULES ACTIVE",          "OK"),
    ("WATCHDOG RESET TIMER",           "SYS"),
    ("MEMORY PRESSURE NOMINAL",        "INFO"),
    ("I/O SUBSYSTEM HEALTHY",          "OK"),
    ("LOG BUFFER FLUSH",               "SYS"),
    ("NEURAL PATH RECALIBRATED",       "OK"),
    ("TASK QUEUE EMPTY",               "INFO"),
    ("SECONDARY CORE SYNCHRONIZED",    "INFO"),
    ("ELEVATED CPU USAGE DETECTED",    "WARN"),
    ("DISK READ LATENCY SPIKE",        "WARN"),
    ("NETWORK PACKET RETRANSMIT",      "WARN"),
]

_BOOT_EVENTS = [
    ("ULTRON SYSTEM INITIALIZING",    "SYS"),
    ("HARDWARE ABSTRACTION LAYER READY", "SYS"),
    ("NEURAL ENGINE STARTING",        "SYS"),
    ("CORE MEMORY ALLOCATED",         "OK"),
    ("TELEMETRY SERVICE ONLINE",      "OK"),
    ("NETWORK INTERFACES DETECTED",   "OK"),
    ("AI CORE WARMING UP",            "SYS"),
    ("SYSTEM MONITOR ACTIVE",         "OK"),
    ("ALL SUBSYSTEMS NOMINAL",        "OK"),
    ("ULTRON ONLINE",                 "SYS"),
]


# ---------------------------------------------------------------------------
# Log Canvas — draws all entries
# ---------------------------------------------------------------------------
class _LogCanvas(QWidget):
    MAX_ENTRIES = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[LogEntry] = []
        self.setStyleSheet("background: transparent;")
        self.setMinimumWidth(10)

    def add_entry(self, entry: LogEntry):
        self._entries.append(entry)
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries = self._entries[-self.MAX_ENTRIES:]
        row_h  = 16
        total_h = max(len(self._entries) * row_h + 8, 10)
        self.setMinimumHeight(total_h)
        self.update()

    def paintEvent(self, event):
        if not self._entries:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        row_h = 16
        font_ts  = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        font_msg = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)

        # Only draw visible rows (simple culling)
        clip_top = event.rect().top()
        clip_bot = event.rect().bottom()
        start_i  = max(0, clip_top // row_h - 1)
        end_i    = min(len(self._entries), clip_bot // row_h + 2)

        for i, entry in enumerate(self._entries[start_i:end_i], start=start_i):
            y = i * row_h + row_h - 3

            # Fade older entries slightly
            age_factor = min(1.0, (i / max(len(self._entries) - 1, 1)) + 0.4)

            # Timestamp
            ts_col = QColor(C.COLOR_TEXT_LO)
            ts_col.setAlpha(int(180 * age_factor))
            p.setPen(ts_col)
            p.setFont(font_ts)
            p.drawText(2, y, f"[{entry.ts}]")

            # Level badge
            lvl_col = QColor(entry.color())
            lvl_col.setAlpha(int(220 * age_factor))
            p.setPen(lvl_col)
            p.setFont(font_ts)
            p.drawText(68, y, entry.level)

            # Message
            msg_col = QColor(C.COLOR_TEXT_MID)
            msg_col.setAlpha(int(200 * age_factor))
            p.setPen(msg_col)
            p.setFont(font_msg)
            p.drawText(104, y, entry.message)

        p.end()


# ---------------------------------------------------------------------------
# SystemLogWidget — scroll area + canvas
# ---------------------------------------------------------------------------
class SystemLogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar  { width: 0px; height: 0px; }
        """)

        self._canvas = _LogCanvas(self)
        self._scroll.setWidget(self._canvas)
        layout.addWidget(self._scroll)

        # Boot sequence
        self._boot_idx = 0
        self._boot_timer = QTimer(self)
        self._boot_timer.timeout.connect(self._boot_step)
        self._boot_timer.start(300)

        # Ongoing events
        self._event_timer = QTimer(self)
        self._event_timer.timeout.connect(self._add_random_event)
        self._event_timer.start(C.LOG_UPDATE_INTERVAL_MS)

    # ------------------------------------------------------------------
    def _boot_step(self):
        if self._boot_idx < len(_BOOT_EVENTS):
            msg, lvl = _BOOT_EVENTS[self._boot_idx]
            self.add_entry(msg, lvl)
            self._boot_idx += 1
        else:
            self._boot_timer.stop()

    def _add_random_event(self):
        msg, lvl = random.choice(_EVENTS)
        self.add_entry(msg, lvl)

    def add_entry(self, message: str, level: str = "INFO"):
        entry = LogEntry(message, level)
        self._canvas.add_entry(entry)
        # Auto-scroll to bottom
        vsb = self._scroll.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def add_command_event(self, cmd: str):
        self.add_entry(f"CMD: {cmd.upper()}", "SYS")

    def add_response_event(self, line: str):
        self.add_entry(line, "OK")
