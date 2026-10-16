# ui/main_window.py
# JARVIS / Iron Man HUD Layout
#
# Layout (top→bottom, left→right):
#   ┌─────────────────────────────────────────────────────┐  ← corner brackets
#   │  [✳] ULTRON  NEURAL INTERFACE      ● SYSTEM ONLINE  │  ← slim top bar (36px)
#   ├──────────┬──────────────────────────┬───────────────┤
#   │ LEFT     │                          │ RIGHT         │
#   │ panels   │    AI CORE (particle)    │ panels        │
#   │ (260px)  │    gold/orange swarm     │ (244px)       │
#   ├──────────┴──────────────────────────┴───────────────┤
#   │  > COMMAND INPUT                                     │  ← console (120px)
#   ├─────────────────────────────────────────────────────┤
#   │  CPU 71%  MEM 55%  NET ↑ 0KB/s  UPTIME 00:00:00     │  ← slim telemetry bar
#   └─────────────────────────────────────────────────────┘  ← corner brackets

import math
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui  import (
    QPainter, QPen, QColor, QFont, QBrush,
    QLinearGradient, QRadialGradient,
)

import theme as C
from ui.utils            import clipped_path, panel_glass_fill
from ui.web_ai_core      import AICoreWidget   # Three.js WebGL swarm
from ui.hud_panel        import HUDPanel, MetricRow, StatusDot
from ui.system_log       import SystemLogWidget
from ui.telemetry        import TelemetryGraph, EnvironmentWidget, AIActivityWidget
from ui.command_console  import CommandConsole
from services.system_monitor    import SystemMonitor
from services.ai_engine         import AIEngine
from services.telemetry_service import TelemetryService


# ─────────────────────────────────────────────────────────────────
# Background canvas — grid + moving scan line + corner brackets
# ─────────────────────────────────────────────────────────────────
class _Background(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase   = 0.0
        self._counter = 0       # frame counter for the counter-line
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(C.ANIMATION_TICK_MS)

    def _tick(self):
        self._phase   += 0.012
        self._counter  = (self._counter + 1) % 1000
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()

        # Base fill
        p.fillRect(0, 0, w, h, QColor(C.COLOR_BG))

        # DPI-aware grid — scale GRID_STEP by device pixel ratio
        dpr  = self.devicePixelRatioF()
        step = max(8, int(C.GRID_STEP * dpr))
        gc   = QColor(C.COLOR_GRID)
        p.setPen(QPen(gc, 0.5))
        for x in range(0, w, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            p.drawLine(0, y, w, y)

        # Radial vignette
        vig = QRadialGradient(w / 2, h / 2, max(w, h) * 0.65)
        vig.setColorAt(0.0, QColor(0, 0, 0, 0))
        vig.setColorAt(1.0, QColor(0, 0, 0, 180))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(0, 0, w, h, QBrush(vig))

        # Gradient scan line — fades out at both edges
        sy   = int((h * 0.5) + (h * 0.45) * math.sin(self._phase))
        scan = QLinearGradient(0, sy - 4, 0, sy + 4)
        sc   = QColor(C.CYAN)
        sc.setAlpha(0);  scan.setColorAt(0.0, sc)
        sc.setAlpha(18); scan.setColorAt(0.5, sc)
        sc.setAlpha(0);  scan.setColorAt(1.0, sc)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(0, sy - 4, w, 8, QBrush(scan))
        # Hard-edge stroke on top of gradient
        edge_c = QColor(C.CYAN); edge_c.setAlpha(8)
        p.setPen(QPen(edge_c, 1))
        p.drawLine(0, sy, w, sy)

        # Counter line — advances top→bottom, wraps every 1000 frames
        cy_pos = int((self._counter / 1000.0) * h)
        cl = QLinearGradient(0, cy_pos - 2, 0, cy_pos + 2)
        cc = QColor(C.GOLD)
        cc.setAlpha(0);  cl.setColorAt(0.0, cc)
        cc.setAlpha(12); cl.setColorAt(0.5, cc)
        cc.setAlpha(0);  cl.setColorAt(1.0, cc)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(0, cy_pos - 2, w, 4, QBrush(cl))

        # Corner brackets — 4 corners, C.BRACKET_INSET inset
        off = C.BRACKET_INSET
        B   = C.BRACKET_ARM
        bc  = QColor(C.CYAN); bc.setAlpha(160)
        p.setPen(QPen(bc, 1))
        corners = [
            (off,     off,     +1, +1),   # TL
            (w - off, off,     -1, +1),   # TR
            (off,     h - off, +1, -1),   # BL
            (w - off, h - off, -1, -1),   # BR
        ]
        for (cx, cy, sx, sy_) in corners:
            p.drawLine(cx, cy, cx + sx * B, cy)
            p.drawLine(cx, cy, cx, cy + sy_ * B)

        p.end()


# ─────────────────────────────────────────────────────────────────
# Slim top bar (36 px)  — brand icon + name + eyebrow + live dot
# ─────────────────────────────────────────────────────────────────
class _TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet("background: transparent;")
        self._llm_online = False
        self._phase      = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(C.ANIMATION_TICK_MS)

    def set_llm_status(self, status: str):
        self._llm_online = (status == "online")
        self.update()

    def _tick(self):
        self._phase += 0.04
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor("#040c14"))
        bg.setColorAt(1.0, QColor("#02070d"))
        p.fillRect(0, 0, w, h, QBrush(bg))

        # Bottom border
        bc = QColor(C.CYAN); bc.setAlpha(50)
        p.setPen(QPen(bc, 1))
        p.drawLine(0, h - 1, w, h - 1)

        # ── Reactor icon (left, 30px inset) ─────────────────
        icon_cx, icon_cy, icon_r = 20, h // 2, C.ICON_R
        ic = QColor(C.CYAN); ic.setAlpha(200)
        p.setPen(QPen(ic, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(icon_cx, icon_cy), icon_r, icon_r)
        ig = QColor(C.CYAN); ig.setAlpha(25)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(ig))
        p.drawEllipse(QPointF(icon_cx, icon_cy), icon_r - 1, icon_r - 1)
        sc = QColor(C.CYAN); sc.setAlpha(220)
        p.setPen(sc)
        p.setFont(QFont(C.FONT_HUD, 8))
        p.drawText(QRectF(icon_cx - icon_r, icon_cy - icon_r,
                          icon_r * 2, icon_r * 2),
                   Qt.AlignmentFlag.AlignCenter, "✳")

        # ── Brand block: ULTRON + eyebrow ───────────────────
        brand_x = icon_cx + icon_r + C.SP_2

        font_brand = QFont(C.FONT_HUD, 12)
        font_brand.setBold(True)
        font_brand.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5)
        p.setFont(font_brand)
        fm = p.fontMetrics()
        brand_w = fm.horizontalAdvance("ULTRON") + 8   # +8 for letter-spacing tail

        nc = QColor(C.COLOR_TEXT)
        p.setPen(nc)
        p.drawText(QRectF(brand_x, 0, brand_w, h), Qt.AlignmentFlag.AlignVCenter, "ULTRON")

        # Eyebrow sits immediately right of brand name, vertically centred
        eyebrow_x = brand_x + brand_w + C.SP_3
        ec = QColor(C.COLOR_TEXT_MID)
        p.setPen(ec)
        font_eye = QFont(C.FONT_MONO, C.FONT_SIZE_LABEL)
        font_eye.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        p.setFont(font_eye)
        p.drawText(QRectF(eyebrow_x, 0, 240, h),
                   Qt.AlignmentFlag.AlignVCenter,
                   f"NEURAL INTERFACE  /  v{C.APP_VERSION}")

        # ── Right side: LLM indicator | separator | live dot | status ──
        # Layout right-to-left from w-16 so nothing clips

        # LLM status (far right)
        font_llm = QFont(C.FONT_MONO, C.FONT_SIZE_LABEL)
        p.setFont(font_llm)
        llm_text = "LLM ●" if self._llm_online else "LLM ○"
        llm_col  = QColor(C.CYAN if self._llm_online else C.COLOR_WARN)
        p.setPen(llm_col)
        fm2      = p.fontMetrics()
        llm_w    = fm2.horizontalAdvance(llm_text) + 4
        llm_x    = w - 16 - llm_w
        p.drawText(QRectF(llm_x, 0, llm_w, h), Qt.AlignmentFlag.AlignVCenter, llm_text)

        # Separator before LLM
        sep_x = llm_x - C.SP_3
        sc2 = QColor(C.CYAN); sc2.setAlpha(30)
        p.setPen(QPen(sc2, 1))
        p.drawLine(sep_x, 8, sep_x, h - 8)

        # "SYSTEM ONLINE" + live dot — measure text first, lay out right-to-left
        font_st = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        font_st.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        p.setFont(font_st)
        fm3     = p.fontMetrics()
        st_text = "SYSTEM ONLINE"
        st_w    = fm3.horizontalAdvance(st_text)

        # Dot sits just left of the separator; text sits left of the dot
        dot_x = sep_x - C.SP_3 - 4
        st_x  = dot_x - C.SP_2 - st_w      # text ends at dot, with small gap

        blink_a = int(255 * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(self._phase * 1.57))))
        glow_c  = QColor(C.CYAN); glow_c.setAlpha(blink_a // 5)
        dot_c   = QColor(C.CYAN); dot_c.setAlpha(blink_a)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow_c))
        p.drawEllipse(QPointF(dot_x, h / 2), 5, 5)
        p.setBrush(QBrush(dot_c))
        p.drawEllipse(QPointF(dot_x, h / 2), 3, 3)

        # Draw text to the left of the dot
        p.setPen(QColor(C.CYAN))
        p.drawText(QRectF(st_x, 0, st_w + 2, h),
                   Qt.AlignmentFlag.AlignVCenter, st_text)

        p.end()


# ─────────────────────────────────────────────────────────────────
# Slim bottom telemetry bar (22 px)
# ─────────────────────────────────────────────────────────────────
class _BottomBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setStyleSheet("background: transparent;")
        self._cpu    = 0.0
        self._ram    = 0.0
        self._net_up = 0.0
        self._uptime = "00:00:00"

    def update_data(self, cpu: float, ram: float, net_up: float, uptime: str):
        self._cpu    = cpu
        self._ram    = ram
        self._net_up = net_up
        self._uptime = uptime
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor("#020810"))

        # Top border
        bc = QColor(C.CYAN); bc.setAlpha(35)
        p.setPen(QPen(bc, 1))
        p.drawLine(0, 0, w, 0)

        metrics = [
            ("CPU",    f"{self._cpu:.0f}%"),
            ("MEM",    f"{self._ram:.0f}%"),
            ("NET ↑",  f"{self._net_up / 1024:.0f} KB/s"),
            ("UPTIME", self._uptime),
            ("RENDER", "HOLOGRAPHIC"),
            ("MODE",   "NEURAL ENGINE"),
        ]

        font_lbl = QFont(C.FONT_MONO, C.FONT_SIZE_LABEL)
        font_val = QFont(C.FONT_MONO, C.FONT_SIZE_LABEL)
        font_val.setBold(True)

        # First pass: measure total width to check if we'll fit
        p.setFont(font_lbl)
        fm_lbl = p.fontMetrics()
        p.setFont(font_val)
        fm_val = p.fontMetrics()

        GAP_INNER = 4     # label → value
        GAP_OUTER = 20    # after value (before separator)

        x = 20
        for idx, (lbl, val) in enumerate(metrics):
            lw = fm_lbl.horizontalAdvance(lbl)
            vw = fm_val.horizontalAdvance(val)

            # Label
            lc = QColor(C.COLOR_TEXT_MID)
            p.setPen(lc)
            p.setFont(font_lbl)
            p.drawText(x, 0, lw, h, Qt.AlignmentFlag.AlignVCenter, lbl)
            x += lw + GAP_INNER

            # Value
            vc = QColor(C.CYAN)
            p.setPen(vc)
            p.setFont(font_val)
            p.drawText(x, 0, vw, h, Qt.AlignmentFlag.AlignVCenter, val)
            x += vw + GAP_OUTER

            # Separator — only if there's space and not last item
            if idx < len(metrics) - 1 and x + 60 < w:
                sc = QColor(C.CYAN); sc.setAlpha(22)
                p.setPen(QPen(sc, 1))
                sep_x = x - GAP_OUTER // 2
                p.drawLine(sep_x, 5, sep_x, h - 5)

        p.end()


# ─────────────────────────────────────────────────────────────────
# Left Column
# ─────────────────────────────────────────────────────────────────
class _LeftColumn(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(C.LEFT_PANEL_W)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(C.SP_1, C.SP_1, C.SP_1, C.SP_1)
        layout.setSpacing(C.SP_2)

        # System Status
        self._sys_panel = HUDPanel("SYSTEM STATUS", self)
        layout.addWidget(self._sys_panel)
        self._cpu_row   = MetricRow("CPU")
        self._ram_row   = MetricRow("RAM")
        self._disk_row  = MetricRow("DISK")
        self._net_row   = MetricRow("NET ↑")
        self._netd_row  = MetricRow("NET ↓")
        self._temp_row  = MetricRow("TEMP")
        for r in [self._cpu_row, self._ram_row, self._disk_row,
                  self._net_row, self._netd_row, self._temp_row]:
            self._sys_panel.content_layout.addWidget(r)

        # AI Status
        self._ai_panel   = HUDPanel("AI STATUS", self)
        layout.addWidget(self._ai_panel)
        self._neural_row = MetricRow("NEURAL")
        self._proc_row   = MetricRow("PROC")
        self._conf_row   = MetricRow("CONF")
        self._task_dot   = StatusDot("MONITORING")
        for r in [self._neural_row, self._proc_row,
                  self._conf_row, self._task_dot]:
            self._ai_panel.content_layout.addWidget(r)

        # System Log
        log_panel = HUDPanel("SYSTEM LOG", self)
        log_panel.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Expanding)
        layout.addWidget(log_panel, 1)
        self.log_widget = SystemLogWidget(log_panel)
        log_panel.content_layout.addWidget(self.log_widget)

    def update_system(self, data: dict):
        self._cpu_row.set_value(data["cpu_pct"],   f"{data['cpu_pct']:.0f}%")
        self._ram_row.set_value(data["ram_pct"],   f"{data['ram_pct']:.0f}%")
        self._disk_row.set_value(data["disk_pct"], f"{data['disk_pct']:.0f}%")
        up_kb = data["net_up"]   / 1024
        dn_kb = data["net_down"] / 1024
        self._net_row.set_value(min(up_kb / 10, 100), f"{up_kb:.0f}KB/s")
        self._netd_row.set_value(min(dn_kb / 10, 100),f"{dn_kb:.0f}KB/s")
        temp = data.get("cpu_temp", 38)
        self._temp_row.set_value(temp / 100 * 100 if temp > 0 else 38,
                                 f"{temp:.0f}°C" if temp > 0 else "38°C")

    def update_ai(self, data: dict):
        self._neural_row.set_value(data["neural"])
        self._proc_row.set_value(data["processing"])
        self._conf_row.set_value(data["confidence"])
        self._task_dot.set_label(data["task"])


# ─────────────────────────────────────────────────────────────────
# Right Column
# ─────────────────────────────────────────────────────────────────
class _RightColumn(QWidget):
    def __init__(self, telemetry: TelemetryService, parent=None):
        super().__init__(parent)
        self.setFixedWidth(C.RIGHT_PANEL_W)
        self.setStyleSheet("background: transparent;")
        self._tele = telemetry

        layout = QVBoxLayout(self)
        layout.setContentsMargins(C.SP_1, C.SP_1, C.SP_1, C.SP_1)
        layout.setSpacing(C.SP_2)

        # Telemetry graphs
        tele_panel = HUDPanel("TELEMETRY", self)
        layout.addWidget(tele_panel)
        self._cpu_graph = TelemetryGraph("CPU ACTIVITY", C.CYAN)
        self._ram_graph = TelemetryGraph("MEMORY",       C.GOLD)
        self._net_graph = TelemetryGraph("NETWORK ↑",    C.COLOR_GLOW)
        self._ai_graph  = TelemetryGraph("AI PROCESSING", C.GOLD_BRIGHT)
        for g in [self._cpu_graph, self._ram_graph,
                  self._net_graph, self._ai_graph]:
            tele_panel.content_layout.addWidget(g)

        # Environment
        env_panel = HUDPanel("ENVIRONMENT", self)
        layout.addWidget(env_panel)
        self._env_widget = EnvironmentWidget(env_panel)
        env_panel.content_layout.addWidget(self._env_widget)

        # AI Activity
        act_panel = HUDPanel("AI ACTIVITY", self)
        layout.addWidget(act_panel)
        self._act_widget = AIActivityWidget(act_panel)
        act_panel.content_layout.addWidget(self._act_widget)

        layout.addStretch()

    def refresh_graphs(self):
        self._cpu_graph.set_history(self._tele.cpu)
        self._ram_graph.set_history(self._tele.ram)
        self._net_graph.set_history(self._tele.net_up)
        self._ai_graph.set_history(self._tele.ai_proc)

    def update_ai(self, data: dict):
        self._act_widget.set_ai_state(data)

    def update_env(self):
        self._env_widget.set_env(self._tele.env)


# ─────────────────────────────────────────────────────────────────
# Thin divider
# ─────────────────────────────────────────────────────────────────
class _Divider(QWidget):
    def __init__(self, orientation="h", parent=None):
        super().__init__(parent)
        self._ori = orientation
        if orientation == "h":
            self.setFixedHeight(1)
        else:
            self.setFixedWidth(1)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        p = QPainter(self)
        c = QColor(C.CYAN); c.setAlpha(30)
        p.setPen(QPen(c, 1))
        if self._ori == "h":
            p.drawLine(0, 0, self.width(), 0)
        else:
            p.drawLine(0, 0, 0, self.height())
        p.end()


# ─────────────────────────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ULTRON — AI Command Center")

        # Services
        self._monitor   = SystemMonitor(self)
        self._ai        = AIEngine(self)
        self._telemetry = TelemetryService(self)
        self._monitor.data_updated.connect(self._telemetry.on_system_data)
        self._ai.state_updated.connect(self._telemetry.on_ai_data)

        # Central widget
        central = QWidget(self)
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Background layer
        self._bg = _Background(central)
        self._bg.setGeometry(0, 0, 1920, 1080)
        self._bg.lower()

        # ── Top bar ───────────────────────────────────────────
        self._topbar = _TopBar(central)
        root.addWidget(self._topbar)

        # ── Middle row ────────────────────────────────────────
        middle = QWidget(central)
        middle.setStyleSheet("background: transparent;")
        mid_layout = QHBoxLayout(middle)
        mid_layout.setContentsMargins(C.SP_2, C.SP_1, C.SP_2, C.SP_1)
        mid_layout.setSpacing(C.SP_2)

        self._left = _LeftColumn(middle)
        mid_layout.addWidget(self._left)

        mid_layout.addWidget(_Divider("v"))

        # Centre: AI Core widget (the particle swarm)
        center_w = QWidget(middle)
        center_w.setStyleSheet("background: transparent;")
        center_l = QVBoxLayout(center_w)
        center_l.setContentsMargins(0, 0, 0, 0)
        center_l.setSpacing(0)
        self._ai_core = AICoreWidget(center_w)
        self._ai_core.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Expanding)
        center_l.addWidget(self._ai_core, 1)
        mid_layout.addWidget(center_w, 1)

        mid_layout.addWidget(_Divider("v"))

        self._right = _RightColumn(self._telemetry, middle)
        mid_layout.addWidget(self._right)

        root.addWidget(middle, 1)

        # ── Console ───────────────────────────────────────────
        root.addWidget(_Divider("h"))
        bottom_w = QWidget(central)
        bottom_w.setFixedHeight(C.BOTTOM_H)
        bottom_w.setStyleSheet("background: transparent;")
        btm_l = QHBoxLayout(bottom_w)
        btm_l.setContentsMargins(8, 4, 8, 4)
        self._console = CommandConsole(bottom_w)
        btm_l.addWidget(self._console)
        root.addWidget(bottom_w)

        # ── Slim telemetry bar ────────────────────────────────
        self._bottom_bar = _BottomBar(central)
        root.addWidget(self._bottom_bar)

        # ── Wire signals ──────────────────────────────────────
        self._monitor.data_updated.connect(self._on_system_data)
        self._ai.state_updated.connect(self._on_ai_data)
        self._telemetry.history_updated.connect(self._on_telemetry)
        self._console.command_entered.connect(self._on_command)
        self._ai.response_ready.connect(self._on_ai_response)
        self._ai.llm_thinking.connect(self._on_llm_thinking)
        self._ai.llm_status.connect(self._on_llm_status)
        self._monitor.threshold_crossed.connect(self._on_threshold_crossed)

        # Start services
        self._monitor.start()
        self._ai.start()

        self._env_timer = QTimer(self)
        self._env_timer.timeout.connect(self._right.update_env)
        self._env_timer.start(3500)

        QTimer.singleShot(200, self._console.give_focus)
        self.showMaximized()

    # ── Slots ─────────────────────────────────────────────────────
    def _on_system_data(self, data: dict):
        self._left.update_system(data)
        self._bottom_bar.update_data(
            data["cpu_pct"], data["ram_pct"],
            data["net_up"],  data["uptime"],
        )

    def _on_ai_data(self, data: dict):
        self._ai_core.update_ai_state(data)
        self._left.update_ai(data)
        self._right.update_ai(data)

    def _on_telemetry(self):
        self._right.refresh_graphs()

    def _on_command(self, cmd: str):
        self._left.log_widget.add_command_event(cmd)
        if cmd.strip().lower() == "clear":
            self._console.clear_output()
            return
        self._ai.handle_command(cmd)

    def _on_ai_response(self, line: str):
        self._console.add_response(line)
        self._left.log_widget.add_response_event(line)

    def _on_llm_thinking(self, thinking: bool):
        self._console.set_thinking(thinking)

    def _on_llm_status(self, status: str):
        self._topbar.set_llm_status(status)

    def _on_threshold_crossed(self, metric: str, state: str, value: float):
        """Forward SystemMonitor threshold events to the system log."""
        label  = metric.upper()
        pct    = f"{value:.0f}%"
        if state == "crit":
            msg   = f"{label} CRITICAL: {pct}"
            level = "ALERT"
        else:
            msg   = f"{label} HIGH: {pct}"
            level = "WARN"
        self._left.log_widget.add_entry(msg, level)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_bg"):
            self._bg.setGeometry(0, 0, self.width(), self.height())
