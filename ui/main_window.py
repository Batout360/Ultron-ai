# ui/main_window.py
# Full HUD Layout — Pure Holographic Orange Command Center

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QSizePolicy, QFrame,
)
from PySide6.QtCore    import Qt, QTimer
from PySide6.QtGui     import (
    QPainter, QPen, QColor, QFont, QBrush,
    QPainterPath, QLinearGradient, QRadialGradient,
)

import theme as C
from ui.ai_core         import AICoreWidget
from ui.hud_panel       import HUDPanel, MetricRow, StatusDot
from ui.system_log      import SystemLogWidget
from ui.telemetry       import TelemetryGraph, EnvironmentWidget, AIActivityWidget
from ui.command_console import CommandConsole
from services.system_monitor  import SystemMonitor
from services.ai_engine       import AIEngine
from services.telemetry_service import TelemetryService


# ---------------------------------------------------------------------------
# Background grid / scan-line canvas
# ---------------------------------------------------------------------------
class _Background(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(C.ANIMATION_TICK_MS)

    def _tick(self):
        self._phase += 0.012
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()

        # Base fill
        p.fillRect(0, 0, w, h, QColor(C.COLOR_BG))

        # Grid
        grid_col = QColor(C.COLOR_GRID)
        p.setPen(QPen(grid_col, 0.5))
        step = 32
        for x in range(0, w, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            p.drawLine(0, y, w, y)

        # Radial vignette
        vig = QRadialGradient(w / 2, h / 2, max(w, h) * 0.65)
        clear = QColor(0, 0, 0, 0)
        edge  = QColor(0, 0, 0, 160)
        vig.setColorAt(0.0, clear)
        vig.setColorAt(1.0, edge)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(0, 0, w, h, QBrush(vig))

        # Moving horizontal scan line
        import math
        sy = int((h * 0.5) + (h * 0.45) * math.sin(self._phase))
        scan_col = QColor(C.COLOR_PRIMARY); scan_col.setAlpha(12)
        p.setPen(QPen(scan_col, 2))
        p.drawLine(0, sy, w, sy)

        p.end()


# ---------------------------------------------------------------------------
# Thin divider line
# ---------------------------------------------------------------------------
class _Divider(QWidget):
    def __init__(self, orientation="h", parent=None):
        super().__init__(parent)
        self._ori = orientation
        if orientation == "h":
            self.setFixedHeight(2)
        else:
            self.setFixedWidth(2)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        p = QPainter(self)
        col = QColor(C.COLOR_PRIMARY); col.setAlpha(60)
        p.setPen(QPen(col, 1))
        if self._ori == "h":
            p.drawLine(0, 0, self.width(), 0)
        else:
            p.drawLine(0, 0, 0, self.height())
        p.end()


# ---------------------------------------------------------------------------
# Header bar
# ---------------------------------------------------------------------------
class _HeaderBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet("background: transparent;")
        self._llm_online = False   # updated by AIEngine signal

    def set_llm_status(self, status: str):
        self._llm_online = (status == "online")
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor(C.COLOR_BG_PANEL))
        bg.setColorAt(1, QColor(C.COLOR_BG))
        p.fillRect(0, 0, w, h, QBrush(bg))

        # Bottom border glow
        line_col = QColor(C.COLOR_PRIMARY); line_col.setAlpha(100)
        p.setPen(QPen(line_col, 1))
        p.drawLine(0, h - 1, w, h - 1)

        # ULTRON title
        title_col = QColor(C.COLOR_BRIGHT)
        p.setPen(title_col)
        font = QFont(C.FONT_HUD, 14)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 8)
        p.setFont(font)
        p.drawText(16, 0, 200, h, Qt.AlignmentFlag.AlignVCenter, "ULTRON")

        # Version
        ver_col = QColor(C.COLOR_DIM)
        p.setPen(ver_col)
        font2 = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        p.setFont(font2)
        p.drawText(16, 0, 260, h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"v{C.APP_VERSION}")

        # Corner indicators
        for i, label in enumerate(["AI CORE", "NET", "SYS", "MEM"]):
            x = w // 2 - 100 + i * 55
            dot_col = QColor(C.COLOR_PRIMARY)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(dot_col))
            p.drawEllipse(x, h // 2 - 3, 6, 6)
            lbl_col = QColor(C.COLOR_TEXT_MID)
            p.setPen(lbl_col)
            font3 = QFont(C.FONT_MONO, 7)
            p.setFont(font3)
            p.drawText(x + 10, 0, 44, h, Qt.AlignmentFlag.AlignVCenter, label)

        # Status right
        p.setPen(QColor(C.COLOR_PRIMARY))
        font4 = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        font4.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        p.setFont(font4)
        p.drawText(w - 180, 0, 168, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   "● SYSTEM ONLINE")

        # LLM status dot (far right, small)
        llm_col = QColor(C.COLOR_PRIMARY if self._llm_online else C.COLOR_WARN)
        llm_label = "LLM ●" if self._llm_online else "LLM ○"
        p.setPen(llm_col)
        font5 = QFont(C.FONT_MONO, 7)
        p.setFont(font5)
        p.drawText(w - 56, 0, 50, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   llm_label)
        p.end()


# ---------------------------------------------------------------------------
# Left Column
# ---------------------------------------------------------------------------
class _LeftColumn(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(C.LEFT_PANEL_W)
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── SYSTEM STATUS ──────────────────────────────────────
        self._sys_panel = HUDPanel("SYSTEM STATUS", self)
        layout.addWidget(self._sys_panel)

        self._cpu_row  = MetricRow("CPU")
        self._ram_row  = MetricRow("RAM")
        self._disk_row = MetricRow("DISK")
        self._net_row  = MetricRow("NET ↑")
        self._netd_row = MetricRow("NET ↓")
        self._temp_row = MetricRow("TEMP")
        for r in [self._cpu_row, self._ram_row, self._disk_row,
                  self._net_row, self._netd_row, self._temp_row]:
            self._sys_panel.content_layout.addWidget(r)

        # ── AI STATUS ──────────────────────────────────────────
        self._ai_panel = HUDPanel("AI STATUS", self)
        layout.addWidget(self._ai_panel)

        self._neural_row = MetricRow("NEURAL")
        self._proc_row   = MetricRow("PROC")
        self._conf_row   = MetricRow("CONF")
        self._task_dot   = StatusDot("MONITORING")
        for r in [self._neural_row, self._proc_row, self._conf_row, self._task_dot]:
            self._ai_panel.content_layout.addWidget(r)

        # ── SYSTEM LOG ────────────────────────────────────────
        log_panel = HUDPanel("SYSTEM LOG", self)
        log_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(log_panel, 1)

        self.log_widget = SystemLogWidget(log_panel)
        log_panel.content_layout.addWidget(self.log_widget)

    # ------------------------------------------------------------------
    def update_system(self, data: dict):
        self._cpu_row.set_value(data["cpu_pct"],  f"{data['cpu_pct']:.0f}%")
        self._ram_row.set_value(data["ram_pct"],  f"{data['ram_pct']:.0f}%")
        self._disk_row.set_value(data["disk_pct"],f"{data['disk_pct']:.0f}%")
        up_kb = data["net_up"] / 1024
        dn_kb = data["net_down"] / 1024
        self._net_row.set_value( min(up_kb / 10, 100), f"{up_kb:.0f}KB/s")
        self._netd_row.set_value(min(dn_kb / 10, 100), f"{dn_kb:.0f}KB/s")
        if data["cpu_temp"] > 0:
            self._temp_row.set_value(data["cpu_temp"] / 100 * 100,
                                     f"{data['cpu_temp']:.0f}°C")
        else:
            self._temp_row.set_value(38, "38°C")

    def update_ai(self, data: dict):
        self._neural_row.set_value(data["neural"])
        self._proc_row.set_value(data["processing"])
        self._conf_row.set_value(data["confidence"])
        self._task_dot._label = data["task"]
        self._task_dot.update()


# ---------------------------------------------------------------------------
# Right Column
# ---------------------------------------------------------------------------
class _RightColumn(QWidget):
    def __init__(self, telemetry: TelemetryService, parent=None):
        super().__init__(parent)
        self.setFixedWidth(C.RIGHT_PANEL_W)
        self.setStyleSheet("background: transparent;")
        self._tele = telemetry

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── TELEMETRY GRAPHS ──────────────────────────────────
        tele_panel = HUDPanel("TELEMETRY", self)
        layout.addWidget(tele_panel)

        self._cpu_graph = TelemetryGraph("CPU ACTIVITY", C.COLOR_PRIMARY)
        self._ram_graph = TelemetryGraph("MEMORY",       C.COLOR_ACCENT)
        self._net_graph = TelemetryGraph("NETWORK ↑",    C.COLOR_GLOW)
        self._ai_graph  = TelemetryGraph("AI PROCESSING",C.COLOR_BRIGHT)

        for g in [self._cpu_graph, self._ram_graph,
                  self._net_graph, self._ai_graph]:
            tele_panel.content_layout.addWidget(g)

        # ── ENVIRONMENT ───────────────────────────────────────
        env_panel = HUDPanel("ENVIRONMENT", self)
        layout.addWidget(env_panel)
        self._env_widget = EnvironmentWidget(env_panel)
        env_panel.content_layout.addWidget(self._env_widget)

        # ── AI ACTIVITY ───────────────────────────────────────
        act_panel = HUDPanel("AI ACTIVITY", self)
        layout.addWidget(act_panel)
        self._act_widget = AIActivityWidget(act_panel)
        act_panel.content_layout.addWidget(self._act_widget)

        layout.addStretch()

    # ------------------------------------------------------------------
    def refresh_graphs(self):
        self._cpu_graph.set_history(self._tele.cpu)
        self._ram_graph.set_history(self._tele.ram)
        self._net_graph.set_history(self._tele.net_up)
        self._ai_graph.set_history(self._tele.ai_proc)

    def update_ai(self, data: dict):
        self._act_widget.set_ai_state(data)

    def update_env(self):
        self._env_widget.set_env(self._tele.env)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ULTRON — AI Command Center")

        # ── Services ──────────────────────────────────────────
        self._monitor  = SystemMonitor(self)
        self._ai       = AIEngine(self)
        self._telemetry = TelemetryService(self)

        self._monitor.data_updated.connect(self._telemetry.on_system_data)
        self._ai.state_updated.connect(self._telemetry.on_ai_data)

        # ── Central transparent widget ─────────────────────────
        central = QWidget(self)
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Background (paint layer)
        self._bg = _Background(central)
        self._bg.setGeometry(0, 0, 1920, 1080)
        self._bg.lower()

        # Header
        self._header = _HeaderBar(central)
        root.addWidget(self._header)
        root.addWidget(_Divider("h"))

        # Middle: left + center + right
        middle = QWidget(central)
        middle.setStyleSheet("background: transparent;")
        mid_layout = QHBoxLayout(middle)
        mid_layout.setContentsMargins(4, 4, 4, 4)
        mid_layout.setSpacing(6)

        # Left
        self._left = _LeftColumn(middle)
        mid_layout.addWidget(self._left)

        mid_layout.addWidget(_Divider("v"))

        # Center — AI Core
        center_widget = QWidget(middle)
        center_widget.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(4, 4, 4, 4)
        center_layout.setSpacing(4)

        self._ai_core = AICoreWidget(center_widget)
        self._ai_core.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_layout.addWidget(self._ai_core, 1)

        # Uptime row under core
        self._uptime_label = QLabel("UPTIME: 00:00:00")
        self._uptime_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._uptime_label.setStyleSheet(
            f"color: {C.COLOR_DIM}; font-family: {C.FONT_MONO}; "
            f"font-size: {C.FONT_SIZE_SMALL}px; background: transparent; letter-spacing: 2px;")
        center_layout.addWidget(self._uptime_label)

        mid_layout.addWidget(center_widget, 1)

        mid_layout.addWidget(_Divider("v"))

        # Right
        self._right = _RightColumn(self._telemetry, middle)
        mid_layout.addWidget(self._right)

        root.addWidget(middle, 1)

        # Bottom console
        root.addWidget(_Divider("h"))
        bottom = QWidget(central)
        bottom.setFixedHeight(C.BOTTOM_H)
        bottom.setStyleSheet("background: transparent;")
        btm_layout = QHBoxLayout(bottom)
        btm_layout.setContentsMargins(8, 4, 8, 4)
        btm_layout.setSpacing(0)

        self._console = CommandConsole(bottom)
        btm_layout.addWidget(self._console)
        root.addWidget(bottom)

        # ── Wire signals ──────────────────────────────────────
        self._monitor.data_updated.connect(self._on_system_data)
        self._ai.state_updated.connect(self._on_ai_data)
        self._telemetry.history_updated.connect(self._on_telemetry)
        self._console.command_entered.connect(self._on_command)
        self._ai.response_ready.connect(self._on_ai_response)
        self._ai.llm_thinking.connect(self._on_llm_thinking)
        self._ai.llm_status.connect(self._on_llm_status)

        # ── Start services ────────────────────────────────────
        self._monitor.start()
        self._ai.start()

        # Env refresh timer
        self._env_timer = QTimer(self)
        self._env_timer.timeout.connect(self._right.update_env)
        self._env_timer.start(3500)

        # Ensure keyboard focus on console
        QTimer.singleShot(200, self._console.give_focus)

        # Show maximized only after all attributes (including _bg) are set
        self.showMaximized()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_system_data(self, data: dict):
        self._left.update_system(data)
        self._uptime_label.setText(f"UPTIME: {data['uptime']}")

    def _on_ai_data(self, data: dict):
        self._ai_core.update_ai_state(data)
        self._left.update_ai(data)
        self._right.update_ai(data)

    def _on_telemetry(self):
        self._right.refresh_graphs()

    def _on_command(self, cmd: str):
        # Log command
        self._left.log_widget.add_command_event(cmd)

        # Handle 'clear' locally
        if cmd.strip().lower() == "clear":
            self._console.clear_output()
            return

        # Delegate to AI engine
        self._ai.handle_command(cmd)

    def _on_ai_response(self, line: str):
        self._console.add_response(line)
        self._left.log_widget.add_response_event(line)

    def _on_llm_thinking(self, thinking: bool):
        """Show/hide a THINKING... indicator in the console."""
        if thinking:
            self._console.set_thinking(True)
        else:
            self._console.set_thinking(False)

    def _on_llm_status(self, status: str):
        """Update the header bar with LLM online/offline state."""
        self._header.set_llm_status(status)

    # ------------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_bg'):
            self._bg.setGeometry(0, 0, self.width(), self.height())
