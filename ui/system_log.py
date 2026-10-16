# ui/system_log.py
# Live scrolling system log widget — Pure Holographic Orange

import random
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel
from PySide6.QtCore    import Qt, QTimer, QRectF
from PySide6.QtGui     import QPainter, QColor, QFont, QPen, QBrush, QPainterPath
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
        total_h = max(len(self._entries) * C.ROW_H_LOG + C.SP_2, 10)
        self.setMinimumHeight(total_h)
        self.update()

    def paintEvent(self, event):
        if not self._entries:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        ROW   = C.ROW_H_LOG
        font_ts  = QFont(C.FONT_MONO, C.FONT_SIZE_LABEL)
        font_lvl = QFont(C.FONT_MONO, C.FONT_SIZE_LABEL)
        font_lvl.setBold(True)
        font_msg = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)

        # Measure fixed columns once
        p.setFont(font_ts)
        fm_ts  = p.fontMetrics()
        TS_W   = fm_ts.horizontalAdvance("[00:00:00]") + 4   # timestamp column

        p.setFont(font_lvl)
        fm_lvl = p.fontMetrics()
        LVL_W  = fm_lvl.horizontalAdvance("ALERT") + 8      # widest badge

        MSG_X  = TS_W + LVL_W + C.SP_2

        # Clip culling
        clip_top = event.rect().top()
        clip_bot = event.rect().bottom()
        start_i  = max(0, clip_top // ROW - 1)
        end_i    = min(len(self._entries), clip_bot // ROW + 2)

        n_total = max(len(self._entries) - 1, 1)

        for i, entry in enumerate(self._entries[start_i:end_i], start=start_i):
            y_top  = i * ROW
            y_base = y_top + ROW - 3   # text baseline

            age = min(1.0, (i / n_total) + 0.4)

            # ── Timestamp ────────────────────────────────────
            tc = QColor(C.COLOR_TEXT_LO); tc.setAlpha(int(160 * age))
            p.setPen(tc)
            p.setFont(font_ts)
            p.drawText(2, y_base, f"[{entry.ts}]")

            # ── Level badge (filled pill) ─────────────────────
            lvl_col = QColor(entry.color())
            lvl_col.setAlpha(int(220 * age))

            # Pill background — very faint fill
            pill_x = TS_W
            pill_h = ROW - 4
            pill_y = y_top + 2
            pill_w = LVL_W
            bg_col = QColor(entry.color()); bg_col.setAlpha(int(30 * age))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(bg_col))
            p.drawRoundedRect(QRectF(pill_x, pill_y, pill_w, pill_h), 2, 2)

            # Badge text
            p.setPen(lvl_col)
            p.setFont(font_lvl)
            p.drawText(QRectF(pill_x, pill_y, pill_w, pill_h),
                       Qt.AlignmentFlag.AlignCenter, entry.level)

            # ── Message ───────────────────────────────────────
            mc = QColor(C.COLOR_TEXT_MID); mc.setAlpha(int(190 * age))
            p.setPen(mc)
            p.setFont(font_msg)
            p.drawText(MSG_X, y_base, entry.message)

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

        # Ongoing events — random pool fires only when no real event arrived
        import time as _time
        self._last_real_event_ts = _time.monotonic()
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
        """Fallback only — fires when no real event arrived in the last interval."""
        import time as _time
        now = _time.monotonic()
        if now - self._last_real_event_ts >= C.LOG_UPDATE_INTERVAL_MS / 1000.0:
            msg, lvl = random.choice(_EVENTS)
            self.add_entry(msg, lvl)

    def add_entry(self, message: str, level: str = "INFO"):
        import time as _time
        self._last_real_event_ts = _time.monotonic()
        entry = LogEntry(message, level)
        self._canvas.add_entry(entry)
        # Auto-scroll to bottom
        vsb = self._scroll.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def add_command_event(self, cmd: str):
        self.add_entry(f"CMD: {cmd.upper()}", "SYS")

    def add_response_event(self, line: str):
        self.add_entry(line, "OK")
