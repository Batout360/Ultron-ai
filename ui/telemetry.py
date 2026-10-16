# ui/telemetry.py
# Telemetry widgets — JARVIS / Iron Man HUD aesthetic
#
# Colour language:
#   Cyan  — graph lines, borders, labels
#   Gold  — current value readouts, highlights
#   Muted — axis labels, secondary text

import math
from collections import deque
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PySide6.QtCore    import Qt, QRectF, QPointF
from PySide6.QtGui     import (
    QPainter, QPen, QBrush, QColor, QFont,
    QPainterPath, QLinearGradient,
)
import theme as C


# ─────────────────────────────────────────────────────────────────
# TelemetryGraph
# ─────────────────────────────────────────────────────────────────
class TelemetryGraph(QWidget):
    """
    Scrolling waveform graph.
    Feed data via set_history(deque_of_floats_0_to_100).
    """

    def __init__(self, label: str, color: str = None, parent=None):
        super().__init__(parent)
        self._label   = label.upper()
        self._color   = color or C.CYAN
        self._history: deque = deque([0.0] * 80, maxlen=80)
        self.setFixedHeight(64)      # was 54 — extra 10px goes to waveform area
        self.setMinimumWidth(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background: transparent;")

    def set_history(self, data: deque):
        self._history = data
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        LABEL_H = 16    # row for label + value text
        g_y = LABEL_H
        g_h = h - LABEL_H - 2

        last = list(self._history)[-1] if self._history else 0.0

        # Value column — measure actual pixel width for "100%" at bold body size
        font2 = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        font2.setBold(True)
        p.setFont(font2)
        fm2   = p.fontMetrics()
        VAL_W = fm2.horizontalAdvance("100%") + 4   # generous cap

        # ── Label — FONT_SIZE_SMALL, muted ─────────────────
        lc = QColor(C.COLOR_TEXT_MID)
        p.setPen(lc)
        font = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        p.setFont(font)
        p.drawText(0, 0, w - VAL_W, LABEL_H, Qt.AlignmentFlag.AlignVCenter, self._label)

        # Value — FONT_SIZE_BODY bold, gold, right-aligned in measured column
        vc = QColor(C.GOLD)
        p.setPen(vc)
        p.setFont(font2)
        p.drawText(w - VAL_W, 0, VAL_W, LABEL_H,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"{last:.0f}%")

        # ── Graph background ──────────────────────────────────
        bg_c = QColor(C.CYAN_FAINT); bg_c.setAlpha(80)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_c))
        p.drawRect(0, g_y, w, g_h)

        # Grid lines at 25 / 50 / 75 %
        gc = QColor(C.CYAN); gc.setAlpha(20)
        p.setPen(QPen(gc, 0.5, Qt.PenStyle.DashLine))
        for pct in (0.25, 0.5, 0.75):
            gy = g_y + int(g_h * (1 - pct))
            p.drawLine(0, gy, w, gy)

        data = list(self._history)
        n    = len(data)
        if n < 2:
            p.end()
            return

        step = w / (n - 1)

        # Build waveform path
        path = QPainterPath()
        first = True
        for i, v in enumerate(data):
            x = i * step
            y = g_y + g_h - (v / 100.0) * g_h
            y = max(g_y, min(g_y + g_h, y))
            if first:
                path.moveTo(x, y)
                first = False
            else:
                path.lineTo(x, y)

        # Fill under curve
        fill = QPainterPath(path)
        fill.lineTo((n - 1) * step, g_y + g_h)
        fill.lineTo(0, g_y + g_h)
        fill.closeSubpath()

        grad = QLinearGradient(0, g_y, 0, g_y + g_h)
        ft = QColor(self._color); ft.setAlpha(70)
        fb = QColor(self._color); fb.setAlpha(0)
        grad.setColorAt(0.0, ft)
        grad.setColorAt(1.0, fb)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(fill, QBrush(grad))

        # Stroke line
        lc2 = QColor(self._color); lc2.setAlpha(210)
        p.setPen(QPen(lc2, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # Peak dot — gold
        px2 = (n - 1) * step
        py2 = g_y + g_h - (last / 100.0) * g_h
        py2 = max(g_y, min(g_y + g_h, py2))
        dc  = QColor(C.GOLD); dc.setAlpha(230)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(dc))
        p.drawEllipse(QPointF(px2, py2), 3, 3)

        p.end()


# ─────────────────────────────────────────────────────────────────
# EnvironmentWidget
# ─────────────────────────────────────────────────────────────────
class EnvironmentWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._temp     = 23.5
        self._humidity = 45.0
        self._pressure = 1013.0
        self.setFixedHeight(56)
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
            ("TEMP",  f"{self._temp:.1f}°C"),
            ("HUMID", f"{self._humidity:.1f}%"),
            ("PRESS", f"{self._pressure:.0f} hPa"),
        ]
        col_w = w // 3
        for i, (lbl, val) in enumerate(items):
            x = i * col_w

            # Label — muted
            lc = QColor(C.COLOR_TEXT_MID); lc.setAlpha(160)
            p.setPen(lc)
            p.setFont(font)
            p.drawText(x, 0, col_w, 16, Qt.AlignmentFlag.AlignCenter, lbl)

            # Value — gold
            vc = QColor(C.GOLD)
            p.setPen(vc)
            font2 = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
            font2.setBold(True)
            p.setFont(font2)
            p.drawText(x, 18, col_w, 22, Qt.AlignmentFlag.AlignCenter, val)
            p.setFont(font)

            # Separator
            if i < 2:
                sc = QColor(C.CYAN); sc.setAlpha(25)
                p.setPen(QPen(sc, 1))
                p.drawLine(x + col_w - 1, 4, x + col_w - 1, h - 4)

        p.end()


# ─────────────────────────────────────────────────────────────────
# AIActivityWidget
# ─────────────────────────────────────────────────────────────────
class AIActivityWidget(QWidget):
    MAX_QUEUE = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: list[str] = ["IDLE"] * self.MAX_QUEUE
        self._current = "MONITORING"
        self._phase   = 0.0
        self.setFixedHeight(88)
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

        # Current task — gold
        hc = QColor(C.GOLD)
        p.setPen(hc)
        font_hdr = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        font_hdr.setBold(True)
        p.setFont(font_hdr)
        p.drawText(0, 0, w, 14, Qt.AlignmentFlag.AlignVCenter,
                   "▶  " + self._current)

        # Activity bar — cyan fill on dark rounded track
        bar_pct = 0.5 + 0.5 * math.sin(self._phase * 0.8)
        bx, by, bw, bh = 0, 16, w, 4
        bar_radius = bh / 2
        tc = QColor(C.CYAN_FAINT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(tc))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), bar_radius, bar_radius)
        fw = int(bw * bar_pct)
        if fw > 0:
            fc = QColor(C.CYAN); fc.setAlpha(200)
            p.setBrush(QBrush(fc))
            p.drawRoundedRect(QRectF(bx, by, fw, bh), bar_radius, bar_radius)

        # Queue items — muted
        font_q = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        row_h  = 13
        for i, item in enumerate(self._queue[1:4]):
            alpha = max(40, 150 - i * 40)
            qc = QColor(C.COLOR_TEXT_MID); qc.setAlpha(alpha)
            p.setPen(qc)
            p.setFont(font_q)
            p.drawText(10, 22 + i * row_h, w - 10, row_h,
                       Qt.AlignmentFlag.AlignVCenter, item)

        p.end()
