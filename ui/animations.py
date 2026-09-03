"""
ULTRON Animations
Core animations for the AI orb visualization.
Uses QPainter for hardware-accelerated rendering.
Each assistant state has a distinct visual appearance.
"""

from __future__ import annotations

import math
import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal, QObject
from PyQt6.QtGui import (
    QColor, QPainter, QRadialGradient, QConicalGradient, QPen,
    QLinearGradient, QPainterPath, QFont
)
from PyQt6.QtWidgets import QWidget

from core.state import AssistantState


# Color palette
COLOR_IDLE = QColor(0, 100, 200, 200)           # Deep blue
COLOR_LISTENING = QColor(0, 212, 255, 230)       # Bright cyan
COLOR_PROCESSING = QColor(0, 150, 255, 200)      # Mid blue
COLOR_THINKING = QColor(100, 50, 255, 220)       # Purple
COLOR_SPEAKING = QColor(0, 255, 150, 220)        # Green-cyan
COLOR_TOOL = QColor(255, 165, 0, 220)            # Orange
COLOR_ERROR = QColor(255, 50, 50, 220)           # Red
COLOR_OFFLINE = QColor(80, 80, 80, 180)          # Grey
COLOR_BG = QColor(5, 10, 15)                     # Near-black


def lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    """Linear interpolate between two colors."""
    t = max(0.0, min(1.0, t))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


STATE_COLORS: dict[AssistantState, QColor] = {
    AssistantState.INITIALIZING: COLOR_IDLE,
    AssistantState.IDLE: COLOR_IDLE,
    AssistantState.LISTENING: COLOR_LISTENING,
    AssistantState.PROCESSING: COLOR_PROCESSING,
    AssistantState.THINKING: COLOR_THINKING,
    AssistantState.SPEAKING: COLOR_SPEAKING,
    AssistantState.TOOL_RUNNING: COLOR_TOOL,
    AssistantState.CONFIRMING: COLOR_TOOL,
    AssistantState.ERROR: COLOR_ERROR,
    AssistantState.PAUSED: COLOR_OFFLINE,
    AssistantState.OFFLINE: COLOR_OFFLINE,
}

STATE_LABELS: dict[AssistantState, str] = {
    AssistantState.INITIALIZING: "INITIALIZING",
    AssistantState.IDLE: "ONLINE",
    AssistantState.LISTENING: "LISTENING",
    AssistantState.PROCESSING: "PROCESSING",
    AssistantState.THINKING: "THINKING",
    AssistantState.SPEAKING: "SPEAKING",
    AssistantState.TOOL_RUNNING: "EXECUTING",
    AssistantState.CONFIRMING: "CONFIRM",
    AssistantState.ERROR: "ERROR",
    AssistantState.PAUSED: "PAUSED",
    AssistantState.OFFLINE: "OFFLINE",
}


class OrbWidget(QWidget):
    """
    The central ULTRON orb visualization.
    Animates based on assistant state.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._state = AssistantState.IDLE
        self._current_color = STATE_COLORS[self._state]
        self._target_color = self._current_color

        # Animation time
        self._t = 0.0
        self._t_start = time.monotonic()

        # Pulse / wave parameters
        self._pulse_freq = 1.0
        self._ring_count = 5
        self._rotation = 0.0

        # Audio level (0.0 - 1.0) for waveform visualization
        self._audio_level = 0.0
        self._audio_history: list[float] = [0.0] * 64

        # Color transition
        self._color_t = 1.0  # 1.0 = fully at target

        # Timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60fps

    def set_state(self, state: AssistantState) -> None:
        """Transition to a new state with color animation."""
        if state == self._state:
            return
        self._state = state
        self._target_color = STATE_COLORS.get(state, COLOR_IDLE)
        self._color_t = 0.0

        # Adjust animation parameters per state
        if state == AssistantState.LISTENING:
            self._pulse_freq = 2.0
        elif state == AssistantState.THINKING:
            self._pulse_freq = 1.5
        elif state == AssistantState.SPEAKING:
            self._pulse_freq = 3.0
        elif state == AssistantState.IDLE:
            self._pulse_freq = 0.5
        elif state in (AssistantState.ERROR, AssistantState.OFFLINE):
            self._pulse_freq = 0.3
        else:
            self._pulse_freq = 1.0

    def set_audio_level(self, level: float) -> None:
        """Update the audio input level visualization."""
        self._audio_level = max(0.0, min(1.0, level))
        self._audio_history.pop(0)
        self._audio_history.append(self._audio_level)

    def _tick(self) -> None:
        """Animation tick - update time and color transition."""
        self._t = time.monotonic() - self._t_start
        self._rotation = (self._rotation + 0.8) % 360

        # Interpolate color
        if self._color_t < 1.0:
            self._color_t = min(1.0, self._color_t + 0.05)
            self._current_color = lerp_color(self._current_color, self._target_color, self._color_t)

        self.update()  # Trigger repaint

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) * 0.38

        # Background
        painter.fillRect(0, 0, w, h, COLOR_BG)

        # Draw based on state
        self._draw_outer_rings(painter, cx, cy, radius)
        self._draw_core_orb(painter, cx, cy, radius)

        if self._state == AssistantState.LISTENING:
            self._draw_waveform(painter, cx, cy, radius)
        elif self._state == AssistantState.THINKING:
            self._draw_thinking_rings(painter, cx, cy, radius)
        elif self._state == AssistantState.SPEAKING:
            self._draw_speaking_bars(painter, cx, cy, radius)

        self._draw_state_label(painter, cx, cy, radius)

        painter.end()

    def _draw_outer_rings(self, p: QPainter, cx, cy, radius) -> None:
        """Animated concentric rings that pulse outward."""
        color = self._current_color
        t = self._t * self._pulse_freq

        for i in range(self._ring_count):
            phase = (t + i / self._ring_count) % 1.0
            ring_r = radius * (1.0 + phase * 0.6)
            alpha = int(color.alpha() * (1.0 - phase) * 0.4)
            ring_color = QColor(color.red(), color.green(), color.blue(), alpha)

            pen = QPen(ring_color)
            pen.setWidth(max(1, int((1.0 - phase) * 3)))
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)

            p.drawEllipse(
                QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            )

    def _draw_core_orb(self, p: QPainter, cx, cy, radius) -> None:
        """The main glowing orb."""
        color = self._current_color
        t = self._t * self._pulse_freq

        # Outer glow
        glow_r = radius * (1.05 + 0.05 * math.sin(t * 2 * math.pi))
        glow = QRadialGradient(cx, cy, glow_r)
        glow.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 60))
        glow.setColorAt(0.4, QColor(color.red(), color.green(), color.blue(), 30))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # Core
        core_r = radius * (0.9 + 0.04 * math.sin(t * 2 * math.pi))
        core_grad = QRadialGradient(cx - radius * 0.15, cy - radius * 0.15, core_r)
        bright = QColor(
            min(255, color.red() + 80),
            min(255, color.green() + 80),
            min(255, color.blue() + 80),
            220,
        )
        core_grad.setColorAt(0.0, bright)
        core_grad.setColorAt(0.4, color)
        core_grad.setColorAt(1.0, QColor(color.red() // 3, color.green() // 3, color.blue() // 3, 180))

        p.setBrush(core_grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))

        # Inner highlight
        highlight_r = core_r * 0.35
        highlight = QRadialGradient(cx - core_r * 0.25, cy - core_r * 0.3, highlight_r)
        highlight.setColorAt(0.0, QColor(255, 255, 255, 100))
        highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(highlight)
        p.drawEllipse(
            QRectF(cx - core_r * 0.6, cy - core_r * 0.65, highlight_r * 2, highlight_r * 2)
        )

    def _draw_waveform(self, p: QPainter, cx, cy, radius) -> None:
        """Audio waveform ring for LISTENING state."""
        n = len(self._audio_history)
        color = self._current_color
        pen = QPen(QColor(color.red(), color.green(), color.blue(), 180))
        pen.setWidth(2)
        p.setPen(pen)

        for i in range(n):
            angle = (i / n) * 2 * math.pi - math.pi / 2
            level = self._audio_history[i]
            inner_r = radius * 1.05
            outer_r = radius * (1.05 + 0.25 * level)
            x1 = cx + inner_r * math.cos(angle)
            y1 = cy + inner_r * math.sin(angle)
            x2 = cx + outer_r * math.cos(angle)
            y2 = cy + outer_r * math.sin(angle)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_thinking_rings(self, p: QPainter, cx, cy, radius) -> None:
        """Rotating arc segments for THINKING state."""
        color = self._current_color
        t = self._t

        for i in range(3):
            phase = t * (1.0 + i * 0.3)
            start_angle = int((self._rotation * (1 + i * 0.5)) % 360) * 16
            span = (120 + 30 * math.sin(phase)) * 16
            r = radius * (1.1 + i * 0.08)

            alpha = 150 - i * 30
            pen = QPen(QColor(color.red(), color.green(), color.blue(), alpha))
            pen.setWidth(3 - i)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), start_angle, int(span))

    def _draw_speaking_bars(self, p: QPainter, cx, cy, radius) -> None:
        """Frequency bars for SPEAKING state."""
        color = self._current_color
        n_bars = 16
        t = self._t * 3

        for i in range(n_bars):
            angle = (i / n_bars) * 2 * math.pi - math.pi / 2
            freq = 1.0 + i * 0.5
            amplitude = 0.15 * abs(math.sin(t * freq + i))
            inner_r = radius * 1.05
            outer_r = radius * (1.05 + amplitude)

            alpha = int(200 * amplitude / 0.15)
            pen = QPen(QColor(color.red(), color.green(), color.blue(), min(255, alpha)))
            pen.setWidth(4)
            p.setPen(pen)

            x1 = cx + inner_r * math.cos(angle)
            y1 = cy + inner_r * math.sin(angle)
            x2 = cx + outer_r * math.cos(angle)
            y2 = cy + outer_r * math.sin(angle)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_state_label(self, p: QPainter, cx, cy, radius) -> None:
        """State label below the orb."""
        label = STATE_LABELS.get(self._state, "")
        color = self._current_color

        font = QFont("Consolas", 11, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor(color.red(), color.green(), color.blue(), 200))

        label_y = cy + radius * 1.45
        p.drawText(
            QRectF(cx - 100, label_y, 200, 30),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            label,
        )
