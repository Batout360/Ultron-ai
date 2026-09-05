# ui/telemetry.py
# Real-time animated telemetry graph widgets — Pure Holographic Orange

import math
from collections import deque
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore    import Qt, QRectF, QPointF
from PySide6.QtGui     import (
    QPainter, QPen, QBrush, QColor, QFont,
    QPainterPath, QLinearGradient,
)
import theme as C


# ---------------------------------------------------------------------------
# Single graph channel
# ---------------------------------------------------------------------------
class TelemetryGraph(QWidget):
    """
    Draws a single scrolling waveform graph.
    Feed data via set_history(deque_of_floats_0_to_100).
    """

    def __init__(self, label: str, color: str = None, parent=None):
        super().__init__(parent)
        self._label   = label.upper()
        self._color   = color or C.COLOR_PRIMARY
        self._history: deque = deque([0.0] * 80, maxlen=80)
        self._peak    = 0.0
        self.setFixedHeight(56)
        self.setMinimumWidth(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background: transparent;")

    def set_history(self, data: deque):
        self._history = data
        if data:
            self._peak = max(data)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        label_h = 14
        graph_y = label_h
        graph_h = h - label_h - 2

        # Label row
        lbl_col = QColor(C.COLOR_TEXT_MID)
        p.setPen(lbl_col)
        font = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        p.setFont(font)
        p.drawText(0, 0, w - 36, label_h, Qt.AlignmentFlag.AlignVCenter, self._label)

        # Current value (last sample)
        val_col = QColor(self._color)
        p.setPen(val_col)
        font2 = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        font2.setBold(True)
        p.setFont(font2)
        last = list(self._history)[-1] if self._history else 0.0
        p.drawText(w - 35, 0, 35, label_h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"{last:.0f}%")

        # Graph background
        bg_col = QColor(C.COLOR_FAINT); bg_col.setAlpha(60)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_col))
        p.drawRect(0, graph_y, w, graph_h)

        # Horizontal grid lines at 25 / 50 / 75%
        grid_col = QColor(C.COLOR_FAINT); grid_col.setAlpha(80)
        p.setPen(QPen(grid_col, 0.5, Qt.PenStyle.DashLine))
        for pct in (0.25, 0.5, 0.75):
            gy = graph_y + int(graph_h * (1 - pct))
            p.drawLine(0, gy, w, gy)

        if not self._history:
            p.end()
            return

        data = list(self._history)
        n    = len(data)
        if n < 2:
            p.end()
            return

        step = w / (n - 1)

        # Build path
        path = QPainterPath()
        first = True
        for i, v in enumerate(data):
            x = i * step
            y = graph_y + graph_h - (v / 100.0) * graph_h
            y = max(graph_y, min(graph_y + graph_h, y))
            if first:
                path.moveTo(x, y)
                first = False
            else:
                path.lineTo(x, y)

        # Fill gradient under curve
        fill_path = QPainterPath(path)
        fill_path.lineTo((n - 1) * step, graph_y + graph_h)
        fill_path.lineTo(0, graph_y + graph_h)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, graph_y, 0, graph_y + graph_h)
        fill_top = QColor(self._color); fill_top.setAlpha(100)
        fill_bot = QColor(self._color); fill_bot.setAlpha(0)
        grad.setColorAt(0.0, fill_top)
        grad.setColorAt(1.0, fill_bot)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(fill_path, QBrush(grad))

        # Stroke
        line_col = QColor(self._color); line_col.setAlpha(220)
        p.setPen(QPen(line_col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # Peak dot
        peak_x = (n - 1) * step
        peak_y = graph_y + graph_h - (last / 100.0) * graph_h
        peak_y = max(graph_y, min(graph_y + graph_h, peak_y))
        dot_col = QColor(C.COLOR_GLOW); dot_col.setAlpha(240)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(dot_col))
        p.drawEllipse(QPointF(peak_x, peak_y), 3, 3)

        p.end()


# ---------------------------------------------------------------------------
# Environment display (temp / humidity / pressure)
# ---------------------------------------------------------------------------
class EnvironmentWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._temp     = 23.5
        self._humidity = 45.0
        self._pressure = 1013.0
        self.setFixedHeight(52)
        self.setStyleSheet("background: transparent;")

    def set_env(self, env: dict):
        self._temp     = env.get("temp",     self._temp)
        self._humidity = env.get("humidity", self._humidity)
        self._pressure = env.get("pressure", self._pressure)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        font = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        p.setFont(font)

        items = [
            ("TEMP",  f"{self._temp:.1f} °C"),
            ("HUMID", f"{self._humidity:.1f} %"),
            ("PRESS", f"{self._pressure:.1f} hPa"),
        ]

        col_w = w // 3
        for i, (lbl, val) in enumerate(items):
            x = i * col_w

            # Label
            lbl_col = QColor(C.COLOR_TEXT_LO); lbl_col.setAlpha(180)
            p.setPen(lbl_col)
            p.drawText(x, 0, col_w, 16, Qt.AlignmentFlag.AlignCenter, lbl)

            # Value
            val_col = QColor(C.COLOR_ACCENT)
            p.setPen(val_col)
            font2 = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
            font2.setBold(True)
            p.setFont(font2)
            p.drawText(x, 18, col_w, 22, Qt.AlignmentFlag.AlignCenter, val)
            p.setFont(font)

            # Separator
            if i < 2:
                sep_col = QColor(C.COLOR_FAINT)
                p.setPen(QPen(sep_col, 1))
                p.drawLine(x + col_w - 1, 4, x + col_w - 1, h - 4)

        p.end()


# ---------------------------------------------------------------------------
# AI Activity Queue display
# ---------------------------------------------------------------------------
class AIActivityWidget(QWidget):
    MAX_QUEUE = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: list[str] = ["IDLE"] * self.MAX_QUEUE
        self._current = "MONITORING"
        self._phase   = 0.0
        self.setFixedHeight(90)
        self.setStyleSheet("background: transparent;")

    def set_ai_state(self, data: dict):
        task = data.get("task", self._current)
        if task != self._current:
            self._queue = ([task] + self._queue)[:self.MAX_QUEUE]
            self._current = task
        self._phase = data.get("phase", self._phase)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Current operation header
        hdr_col = QColor(C.COLOR_BRIGHT)
        p.setPen(hdr_col)
        font_hdr = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        font_hdr.setBold(True)
        p.setFont(font_hdr)
        p.drawText(0, 0, w, 14, Qt.AlignmentFlag.AlignVCenter, "▶ " + self._current)

        # Activity bar
        bar_pct = 0.5 + 0.5 * math.sin(self._phase * 0.8)
        bar_x, bar_y = 0, 16
        bar_w, bar_h = w, 5
        track_col = QColor(C.COLOR_FAINT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(track_col))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 2, 2)
        fill_w = int(bar_w * bar_pct)
        if fill_w > 0:
            fill_col = QColor(C.COLOR_PRIMARY); fill_col.setAlpha(200)
            p.setBrush(QBrush(fill_col))
            p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 2, 2)

        # Queue
        font_q = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        row_h  = 13
        for i, item in enumerate(self._queue[1:4]):
            alpha = int(160 - i * 40)
            q_col = QColor(C.COLOR_TEXT_LO); q_col.setAlpha(alpha)
            p.setPen(q_col)
            p.setFont(font_q)
            p.drawText(8, 24 + i * row_h, w - 8, row_h,
                       Qt.AlignmentFlag.AlignVCenter, f"  {item}")

        p.end()
