# ui/command_console.py
# Futuristic command console — Pure Holographic Orange

import math
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLineEdit, QScrollArea, QLabel, QSizePolicy,
)
from PySide6.QtCore    import Qt, Signal, QTimer, QRectF, QPointF
from PySide6.QtGui     import (
    QPainter, QPen, QColor, QFont, QBrush,
    QPainterPath, QLinearGradient, QKeyEvent,
)
import theme as C


# ---------------------------------------------------------------------------
# Output line widget
# ---------------------------------------------------------------------------
class _OutputLine(QWidget):
    def __init__(self, text: str, is_input: bool = False, parent=None):
        super().__init__(parent)
        self._text     = text
        self._is_input = is_input
        self.setFixedHeight(17)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        font = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        p.setFont(font)

        if self._is_input:
            # Prefix ">"
            pre_col = QColor(C.COLOR_GLOW)
            p.setPen(pre_col)
            p.drawText(0, 0, 14, h, Qt.AlignmentFlag.AlignVCenter, ">")
            txt_col = QColor(C.COLOR_BRIGHT)
            p.setPen(txt_col)
            p.drawText(16, 0, w - 16, h, Qt.AlignmentFlag.AlignVCenter, self._text)
        else:
            txt_col = QColor(C.COLOR_TEXT_MID)
            p.setPen(txt_col)
            p.drawText(4, 0, w - 4, h, Qt.AlignmentFlag.AlignVCenter, self._text)
        p.end()


# ---------------------------------------------------------------------------
# Output scroll area
# ---------------------------------------------------------------------------
class _OutputArea(QWidget):
    MAX_LINES = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: list[_OutputLine] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(1)
        self._layout.addStretch()
        self.setStyleSheet("background: transparent;")

    def add_line(self, text: str, is_input: bool = False):
        line = _OutputLine(text, is_input, self)
        self._layout.addWidget(line)
        self._lines.append(line)
        if len(self._lines) > self.MAX_LINES:
            old = self._lines.pop(0)
            self._layout.removeWidget(old)
            old.deleteLater()


# ---------------------------------------------------------------------------
# Blinking cursor input field
# ---------------------------------------------------------------------------
class _HUDInput(QWidget):
    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet("background: transparent;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._text       = ""
        self._cursor_vis = True
        self._history: list[str] = []
        self._hist_idx   = -1
        self._phase      = 0.0

        self._cur_timer = QTimer(self)
        self._cur_timer.timeout.connect(self._blink)
        self._cur_timer.start(530)

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_timer.start(C.ANIMATION_TICK_MS)

    def _blink(self):
        self._cursor_vis = not self._cursor_vis
        self.update()

    def _anim_tick(self):
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

        # Glow border
        glow_intensity = 0.6 + 0.4 * math.sin(self._phase)
        border_col = QColor(C.COLOR_PRIMARY)
        border_col.setAlpha(int(180 * glow_intensity))
        pen = QPen(border_col, 1.5)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        path = QPainterPath()
        path.addRoundedRect(0, 1, w, h - 2, 3, 3)
        p.drawPath(path)

        # Subtle fill
        fill_col = QColor(C.COLOR_FAINT); fill_col.setAlpha(80)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fill_col))
        p.fillPath(path, QBrush(fill_col))

        # Prompt ">"
        p.setPen(QPen(QColor(C.COLOR_GLOW), 1))
        font = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        font.setBold(True)
        p.setFont(font)
        p.drawText(8, 0, 16, h, Qt.AlignmentFlag.AlignVCenter, ">")

        # Input text
        txt_col = QColor(C.COLOR_TEXT_HI)
        p.setPen(txt_col)
        font2 = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        p.setFont(font2)
        p.drawText(26, 0, w - 32, h, Qt.AlignmentFlag.AlignVCenter, self._text)

        # Cursor
        if self._cursor_vis and self.hasFocus():
            fm     = p.fontMetrics()
            txt_w  = fm.horizontalAdvance(self._text)
            cur_x  = 26 + txt_w + 2
            cur_y  = h // 2 - 7
            cur_col = QColor(C.COLOR_GLOW); cur_col.setAlpha(220)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(cur_col))
            p.drawRect(cur_x, cur_y, 2, 14)

        p.end()


# ---------------------------------------------------------------------------
# Pulsing "THINKING..." indicator
# ---------------------------------------------------------------------------
class _ThinkingLine(QWidget):
    _FRAMES = ["THINKING.  ", "THINKING.. ", "THINKING..."]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(17)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._frame = 0
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(400)

    def _tick(self):
        self._frame = (self._frame + 1) % len(self._FRAMES)
        self._phase += 0.3
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        alpha = int(160 + 95 * math.sin(self._phase))
        col = QColor(C.COLOR_GLOW)
        col.setAlpha(alpha)
        p.setPen(col)

        font = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        font.setBold(True)
        p.setFont(font)
        p.drawText(4, 0, w - 4, h, Qt.AlignmentFlag.AlignVCenter,
                   self._FRAMES[self._frame])
        p.end()


# ---------------------------------------------------------------------------
# CommandConsole — full widget
# ---------------------------------------------------------------------------
class CommandConsole(QWidget):
    """
    Futuristic command console with scrolling output and HUD input.
    Signals: command_entered(str)
    """

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
            QScrollBar  { width: 0px; height: 0px; }
        """)

        self._output = _OutputArea(self)
        self._scroll.setWidget(self._output)
        outer.addWidget(self._scroll, 1)

        # Input
        self._input = _HUDInput(self)
        self._input.submitted.connect(self._on_submit)
        outer.addWidget(self._input)

        # Boot greeting
        self._add_boot_lines()

    def _add_boot_lines(self):
        lines = [
            "ULTRON COMMAND INTERFACE v2.0",
            "TYPE 'help' FOR AVAILABLE COMMANDS.",
            "─" * 38,
        ]
        for l in lines:
            self._output.add_line(l)
        self._scroll_to_bottom()

    def _on_submit(self, cmd: str):
        self._output.add_line(cmd, is_input=True)
        self.command_entered.emit(cmd)
        self._scroll_to_bottom()

    def add_response(self, line: str):
        self._output.add_line(line)
        self._scroll_to_bottom()

    def clear_output(self):
        for line in list(self._output._lines):
            self._output._layout.removeWidget(line)
            line.deleteLater()
        self._output._lines.clear()

    # ------------------------------------------------------------------
    # Thinking indicator
    # ------------------------------------------------------------------
    def set_thinking(self, active: bool):
        """Show or hide the pulsing THINKING... indicator."""
        if active:
            # Disable input while LLM is working
            self._input.setEnabled(False)
            if not hasattr(self, '_thinking_line') or self._thinking_line is None:
                self._thinking_line = _ThinkingLine(self._output)
                self._output._layout.addWidget(self._thinking_line)
            self._scroll_to_bottom()
        else:
            self._input.setEnabled(True)
            self._input.setFocus()
            if hasattr(self, '_thinking_line') and self._thinking_line is not None:
                self._output._layout.removeWidget(self._thinking_line)
                self._thinking_line.deleteLater()
                self._thinking_line = None
    def _scroll_to_bottom(self):
        QTimer.singleShot(30, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def give_focus(self):
        self._input.setFocus()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        bg_col = QColor(C.COLOR_BG_GLASS); bg_col.setAlpha(220)
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, C.PANEL_RADIUS, C.PANEL_RADIUS)
        p.fillPath(path, QBrush(bg_col))

        border_col = QColor(C.COLOR_PRIMARY); border_col.setAlpha(140)
        p.setPen(QPen(border_col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        p.end()
