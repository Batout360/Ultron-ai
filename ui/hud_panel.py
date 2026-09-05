# ui/hud_panel.py
# Base HUD Panel — glowing orange glass frame with title bar

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, Property, QRect
from PySide6.QtGui     import (
    QPainter, QPen, QColor, QFont, QBrush,
    QLinearGradient, QPainterPath,
)
import theme as C


class HUDPanel(QWidget):
    """
    Base class for all HUD panel widgets.

    Provides:
    - Orange glass background with gradient
    - Glowing border with corner notches
    - Title bar with section label
    - Content area via self.content_layout
    - Hover glow animation
    - Click-to-expand toggle
    """

    def __init__(self, title: str, parent=None, collapsible=False):
        super().__init__(parent)
        self._title       = title.upper()
        self._collapsible = collapsible
        self._glow        = 0.0     # 0.0 – 1.0
        self._hover       = False
        self._expanded    = True

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Main layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 28, 6, 6)
        outer.setSpacing(4)

        # Content widget (so we can hide it on collapse)
        self._content_widget = QWidget(self)
        self._content_widget.setStyleSheet("background: transparent;")
        self.content_layout  = QVBoxLayout(self._content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(3)

        outer.addWidget(self._content_widget)

    # ------------------------------------------------------------------
    def enterEvent(self, event):
        self._hover = True
        self._glow  = 1.0
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self._glow  = 0.0
        self.update()

    def mousePressEvent(self, event):
        if self._collapsible and event.pos().y() < 28:
            self._expanded = not self._expanded
            self._content_widget.setVisible(self._expanded)
            self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Glass background
        bg_path = QPainterPath()
        bg_path.addRoundedRect(0, 0, w, h, C.PANEL_RADIUS, C.PANEL_RADIUS)

        bg_grad = QLinearGradient(0, 0, 0, h)
        bg1 = QColor(C.COLOR_BG_GLASS); bg1.setAlpha(230)
        bg2 = QColor(C.COLOR_BG_PANEL); bg2.setAlpha(200)
        bg_grad.setColorAt(0.0, bg1)
        bg_grad.setColorAt(1.0, bg2)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(bg_path, QBrush(bg_grad))

        # Border glow
        border_alpha = int(120 + 120 * self._glow)
        border_col   = QColor(C.COLOR_PRIMARY if not self._hover else C.COLOR_BRIGHT)
        border_col.setAlpha(border_alpha)
        p.setPen(QPen(border_col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bg_path)

        # Extra outer glow when hovered
        if self._hover:
            glow_col = QColor(C.COLOR_PRIMARY); glow_col.setAlpha(40)
            p.setPen(QPen(glow_col, 4))
            glow_path = QPainterPath()
            glow_path.addRoundedRect(-2, -2, w + 4, h + 4, C.PANEL_RADIUS + 2, C.PANEL_RADIUS + 2)
            p.drawPath(glow_path)

        # Corner notches
        notch_col = QColor(C.COLOR_GLOW); notch_col.setAlpha(200)
        p.setPen(QPen(notch_col, 1.5))
        nc = 5  # notch length
        corners = [(0, 0), (w, 0), (0, h), (w, h)]
        for (cx, cy) in corners:
            sx = 1 if cx == 0 else -1
            sy = 1 if cy == 0 else -1
            p.drawLine(cx, cy, cx + sx * nc, cy)
            p.drawLine(cx, cy, cx, cy + sy * nc)

        # Title bar background
        title_grad = QLinearGradient(0, 0, w, 0)
        t1 = QColor(C.COLOR_PRIMARY); t1.setAlpha(60)
        t2 = QColor(C.COLOR_PRIMARY); t2.setAlpha(10)
        title_grad.setColorAt(0.0, t1)
        title_grad.setColorAt(1.0, t2)
        title_bg = QPainterPath()
        title_bg.addRoundedRect(1, 1, w - 2, 26, C.PANEL_RADIUS, C.PANEL_RADIUS)
        p.fillPath(title_bg, QBrush(title_grad))

        # Title text
        title_col = QColor(C.COLOR_BRIGHT)
        title_col.setAlpha(240)
        p.setPen(title_col)
        font = QFont(C.FONT_HUD, C.FONT_SIZE_TITLE)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(font)
        p.drawText(10, 18, self._title)

        # Collapse indicator
        if self._collapsible:
            ind_col = QColor(C.COLOR_DIM); ind_col.setAlpha(180)
            p.setPen(ind_col)
            font2 = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
            p.setFont(font2)
            p.drawText(w - 20, 18, "▾" if self._expanded else "▸")

        # Bottom accent line
        line_col = QColor(C.COLOR_PRIMARY); line_col.setAlpha(80)
        p.setPen(QPen(line_col, 1))
        p.drawLine(1, 26, w - 1, 26)

        p.end()


# ---------------------------------------------------------------------------
# Helper: a single labeled metric row
# ---------------------------------------------------------------------------
class MetricRow(QWidget):
    """Label + bar + value on one row."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self._label = label.upper()
        self._value = 0.0        # 0-100
        self._text  = "0%"
        self.setStyleSheet("background: transparent;")

    def set_value(self, v: float, text: str = None):
        self._value = max(0.0, min(100.0, v))
        self._text  = text or f"{self._value:.0f}%"
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Label
        lbl_col = QColor(C.COLOR_TEXT_MID)
        p.setPen(lbl_col)
        font = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        p.setFont(font)
        p.drawText(0, 0, 72, h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._label)

        # Bar track
        bar_x, bar_y = 76, h // 2 - 3
        bar_w, bar_h = w - 76 - 40, 6
        track_col = QColor(C.COLOR_FAINT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(track_col))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 2, 2)

        # Bar fill
        fill_w = int(bar_w * self._value / 100)
        if fill_w > 0:
            # Color shifts red when critical
            if self._value >= 90:
                fill_col = QColor(C.COLOR_CRITICAL)
            elif self._value >= 75:
                fill_col = QColor(C.COLOR_WARN)
            else:
                fill_col = QColor(C.COLOR_PRIMARY)
            fill_col.setAlpha(210)
            p.setBrush(QBrush(fill_col))
            p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 2, 2)

            # Glow cap
            glow_col = QColor(C.COLOR_GLOW); glow_col.setAlpha(200)
            p.setBrush(QBrush(glow_col))
            p.drawEllipse(bar_x + fill_w - 3, bar_y - 1, 5, 8)

        # Value text
        val_col = QColor(C.COLOR_TEXT_HI)
        p.setPen(val_col)
        p.drawText(w - 38, 0, 38, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   self._text)
        p.end()


# ---------------------------------------------------------------------------
# Helper: small status indicator dot
# ---------------------------------------------------------------------------
class StatusDot(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self._label = label
        self._ok    = True
        self.setStyleSheet("background: transparent;")

    def set_status(self, ok: bool):
        self._ok = ok
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        dot_col = QColor(C.COLOR_PRIMARY if self._ok else C.COLOR_CRITICAL)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(dot_col))
        p.drawEllipse(0, h // 2 - 4, 8, 8)
        txt_col = QColor(C.COLOR_TEXT_MID)
        p.setPen(txt_col)
        font = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        p.setFont(font)
        p.drawText(14, 0, self.width() - 14, h,
                   Qt.AlignmentFlag.AlignVCenter, self._label.upper())
        p.end()
