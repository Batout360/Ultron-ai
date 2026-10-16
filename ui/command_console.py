# ui/command_console.py — ULTRON 3.0
# Command Console — JARVIS / Iron Man HUD aesthetic
#
# v3.0 changes:
#   • _clipped_path / glass fill now imported from ui.utils (single source)
#   • Long output lines elided with fm.elidedText (no overflow)
#   • rangeChanged autoscroll replaces singleShot hack
#   • Glass fill uses PANEL_GLASS tokens via panel_glass_fill()

import math
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QScrollArea, QSizePolicy,
)
from PySide6.QtCore    import Qt, Signal, QTimer, QRectF, QPointF
from PySide6.QtGui     import (
    QPainter, QPen, QColor, QFont, QBrush,
    QPainterPath, QLinearGradient, QKeyEvent,
)
import theme as C
from ui.utils import clipped_path, panel_glass_fill


# ─────────────────────────────────────────────────────────────────
# Output line
# ─────────────────────────────────────────────────────────────────
class _OutputLine(QWidget):
    def __init__(self, text: str, is_input: bool = False, parent=None):
        super().__init__(parent)
        self._text     = text
        self._is_input = is_input
        self.setFixedHeight(C.ROW_H_LOG)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        font = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        p.setFont(font)
        fm = p.fontMetrics()

        if self._is_input:
            # Prompt in cyan, command text in gold — elide if too long
            pc = QColor(C.CYAN); pc.setAlpha(200)
            p.setPen(pc)
            p.drawText(0, 0, 14, h, Qt.AlignmentFlag.AlignVCenter, ">")
            tc = QColor(C.GOLD)
            p.setPen(tc)
            avail_w = w - 16
            elided  = fm.elidedText(self._text, Qt.TextElideMode.ElideRight, avail_w)
            p.drawText(16, 0, avail_w, h, Qt.AlignmentFlag.AlignVCenter, elided)
        else:
            tc = QColor(C.COLOR_TEXT_MID)
            p.setPen(tc)
            avail_w = w - 4
            elided  = fm.elidedText(self._text, Qt.TextElideMode.ElideRight, avail_w)
            p.drawText(4, 0, avail_w, h, Qt.AlignmentFlag.AlignVCenter, elided)
        p.end()


# ─────────────────────────────────────────────────────────────────
# Output area
# ─────────────────────────────────────────────────────────────────
class _OutputArea(QWidget):
    MAX_LINES = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: list[_OutputLine] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)
        layout.addStretch()
        self._layout = layout
        self.setStyleSheet("background: transparent;")

    def add_line(self, text: str, is_input: bool = False):
        line = _OutputLine(text, is_input, self)
        self._layout.addWidget(line)
        self._lines.append(line)
        if len(self._lines) > self.MAX_LINES:
            old = self._lines.pop(0)
            self._layout.removeWidget(old)
            old.deleteLater()


# ─────────────────────────────────────────────────────────────────
# HUD input field
# ─────────────────────────────────────────────────────────────────
class _HUDInput(QWidget):
    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(C.INPUT_H)
        self.setStyleSheet("background: transparent;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._text       = ""
        self._cursor_vis = True
        self._history: list[str] = []
        self._hist_idx   = -1
        self._phase      = 0.0

        QTimer(self, timeout=self._blink, interval=530).start(530)
        QTimer(self, timeout=self._tick,  interval=C.ANIMATION_TICK_MS).start(C.ANIMATION_TICK_MS)

    def _blink(self):
        self._cursor_vis = not self._cursor_vis
        self.update()

    def _tick(self):
        self._phase += 0.05
        self.update()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._text.strip():
                self._history.insert(0, self._text)
                self._hist_idx = -1
                self.submitted.emit(self._text.strip())
                self._text = ""
        elif key == Qt.Key.Key_Backspace:
            self._text = self._text[:-1]
        elif key == Qt.Key.Key_Up:
            if self._history and self._hist_idx < len(self._history) - 1:
                self._hist_idx += 1
                self._text = self._history[self._hist_idx]
        elif key == Qt.Key.Key_Down:
            if self._hist_idx > 0:
                self._hist_idx -= 1
                self._text = self._history[self._hist_idx]
            elif self._hist_idx == 0:
                self._hist_idx = -1
                self._text = ""
        else:
            ch = event.text()
            if ch.isprintable():
                self._text += ch
        self.update()

    def mousePressEvent(self, event):
        self.setFocus()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Border pulsing with focus
        focused = self.hasFocus()
        pulse   = 0.6 + 0.4 * math.sin(self._phase) if focused else 0.25
        bc = QColor(C.CYAN); bc.setAlpha(int(255 * pulse))
        p.setPen(QPen(bc, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Clipped top-right input shape
        path = clipped_path(0, 0, w, h)
        p.drawPath(path)

        # Glass fill using PANEL_GLASS tokens
        panel_glass_fill(p, 0, 0, w, h)

        # Redraw border on top of fill
        p.setPen(QPen(bc, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # Prompt ">"
        p.setPen(QColor(C.CYAN))
        font = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        font.setBold(True)
        p.setFont(font)
        p.drawText(8, 0, 16, h, Qt.AlignmentFlag.AlignVCenter, ">")

        # Input text
        tc = QColor(C.COLOR_TEXT)
        p.setPen(tc)
        font2 = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        p.setFont(font2)
        fm = p.fontMetrics()
        avail_w = w - 32
        elided  = fm.elidedText(self._text, Qt.TextElideMode.ElideLeft, avail_w)
        p.drawText(26, 0, avail_w, h, Qt.AlignmentFlag.AlignVCenter, elided)

        # Cursor — always at end of displayed text
        if self._cursor_vis and focused:
            txt_w = fm.horizontalAdvance(elided)
            cur_x = 26 + txt_w + 2
            cur_c = QColor(C.CYAN); cur_c.setAlpha(200)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(cur_c))
            p.drawRect(cur_x, h // 2 - 6, 2, 12)

        p.end()


# ─────────────────────────────────────────────────────────────────
# Thinking indicator
# ─────────────────────────────────────────────────────────────────
class _ThinkingLine(QWidget):
    _FRAMES = ["PROCESSING .  ", "PROCESSING .. ", "PROCESSING ..."]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(C.ROW_H_LOG)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._frame = 0
        self._phase = 0.0
        QTimer(self, timeout=self._tick, interval=400).start(400)

    def _tick(self):
        self._frame = (self._frame + 1) % len(self._FRAMES)
        self._phase += 0.3
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        alpha = int(160 + 95 * math.sin(self._phase))
        col = QColor(C.CYAN); col.setAlpha(alpha)
        p.setPen(col)
        font = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        font.setBold(True)
        p.setFont(font)
        p.drawText(4, 0, w - 4, h, Qt.AlignmentFlag.AlignVCenter,
                   self._FRAMES[self._frame])
        p.end()


# ─────────────────────────────────────────────────────────────────
# CommandConsole
# ─────────────────────────────────────────────────────────────────
class CommandConsole(QWidget):
    """Futuristic command console.  Signal: command_entered(str)"""

    command_entered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # Output scroll area
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar  { width: 0; height: 0; }
        """)
        self._output = _OutputArea(self)
        self._scroll.setWidget(self._output)
        outer.addWidget(self._scroll, 1)

        # rangeChanged autoscroll — fires after layout recalculates content height
        self._scroll.verticalScrollBar().rangeChanged.connect(self._on_range_changed)

        # Input
        self._input = _HUDInput(self)
        self._input.submitted.connect(self._on_submit)
        outer.addWidget(self._input)

        self._thinking_line = None
        self._add_boot_lines()

    def _add_boot_lines(self):
        for line in [
            f"ULTRON COMMAND INTERFACE v{C.APP_VERSION}",
            "TYPE 'help' FOR AVAILABLE COMMANDS.",
            "─" * 40,
        ]:
            self._output.add_line(line)

    def _on_range_changed(self, _min: int, _max: int):
        """Scroll to bottom whenever the scroll-area content height changes."""
        self._scroll.verticalScrollBar().setValue(_max)

    def _on_submit(self, cmd: str):
        self._output.add_line(cmd, is_input=True)
        self.command_entered.emit(cmd)

    def add_response(self, line: str):
        self._output.add_line(line)

    def clear_output(self):
        for line in list(self._output._lines):
            self._output._layout.removeWidget(line)
            line.deleteLater()
        self._output._lines.clear()

    def set_thinking(self, active: bool):
        if active:
            self._input.setEnabled(False)
            if self._thinking_line is None:
                self._thinking_line = _ThinkingLine(self._output)
                self._output._layout.addWidget(self._thinking_line)
        else:
            self._input.setEnabled(True)
            self._input.setFocus()
            if self._thinking_line is not None:
                self._output._layout.removeWidget(self._thinking_line)
                self._thinking_line.deleteLater()
                self._thinking_line = None

    def give_focus(self):
        self._input.setFocus()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        body = clipped_path(0, 0, w, h)

        # Glass background — uses PANEL_GLASS tokens via panel_glass_fill
        panel_glass_fill(p, 0, 0, w, h)

        # Border
        bc = QColor(C.CYAN); bc.setAlpha(55)
        p.setPen(QPen(bc, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(body)

        # Clip corner fill
        tri = QPainterPath()
        tri.moveTo(w - C.PANEL_CLIP, 0)
        tri.lineTo(w, 0)
        tri.lineTo(w, C.PANEL_CLIP)
        tri.closeSubpath()
        tc = QColor(C.CYAN); tc.setAlpha(30)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(tri, QBrush(tc))

        p.end()
