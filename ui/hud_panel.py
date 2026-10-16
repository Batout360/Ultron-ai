# ui/hud_panel.py — ULTRON 3.0
# HUD Panel — JARVIS / Iron Man aesthetic
#
# v3.0 changes:
#   • _clipped_path / glass fill now imported from ui.utils (single source)
#   • StatusDot is 3-state: OK / WARN / CRIT  (set_status(state: str))
#   • Collapsible panels animate via QPropertyAnimation (180 ms)
#   • paintEvent uses C.PANEL_GLASS_TOP / PANEL_GLASS_BOT tokens

import math
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PySide6.QtCore    import (
    Qt, QRectF, QPointF,
    QPropertyAnimation, QEasingCurve, QByteArray,
)
from PySide6.QtGui     import (
    QPainter, QPen, QColor, QFont, QBrush,
    QLinearGradient, QPainterPath,
)
import theme as C
from ui.utils import clipped_path, panel_glass_fill


# ─────────────────────────────────────────────────────────────────
# HUDPanel
# ─────────────────────────────────────────────────────────────────
class HUDPanel(QWidget):
    """
    Base panel.  Public: self.content_layout (QVBoxLayout).

    If collapsible=True, clicking the heading band toggles the body
    via a 180 ms height animation.
    """

    def __init__(self, title: str, parent=None, collapsible: bool = False):
        super().__init__(parent)
        self._title       = title.upper()
        self._collapsible = collapsible
        self._expanded    = True
        self._hover       = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        H = C.PANEL_HEAD_H   # heading band height in px

        outer = QVBoxLayout(self)
        outer.setContentsMargins(C.SP_2, H + C.SP_1, C.SP_2, C.SP_2)
        outer.setSpacing(C.SP_1)

        self._content_widget = QWidget(self)
        self._content_widget.setStyleSheet("background: transparent;")
        self.content_layout  = QVBoxLayout(self._content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(C.SP_1)
        outer.addWidget(self._content_widget)

        # Animation — collapses content height 0 ↔ natural size in 180 ms
        if collapsible:
            self._anim = QPropertyAnimation(
                self._content_widget, QByteArray(b"maximumHeight"), self
            )
            self._anim.setDuration(180)
            self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        else:
            self._anim = None

    def enterEvent(self, e):
        self._hover = True;  self.update()

    def leaveEvent(self, e):
        self._hover = False; self.update()

    def mousePressEvent(self, e):
        if self._collapsible and e.pos().y() < C.PANEL_HEAD_H:
            self._toggle_collapse()

    def _toggle_collapse(self):
        self._expanded = not self._expanded
        if self._anim is not None:
            if self._expanded:
                # Expand: 0 → natural height (use a large sentinel)
                self._content_widget.setVisible(True)
                self._anim.setStartValue(0)
                self._anim.setEndValue(self._content_widget.sizeHint().height())
            else:
                # Collapse: natural height → 0
                self._anim.setStartValue(self._content_widget.height())
                self._anim.setEndValue(0)
                # Hide after animation finishes
                self._anim.finished.connect(
                    lambda: self._content_widget.setVisible(self._expanded)
                )
            self._anim.start()
        else:
            self._content_widget.setVisible(self._expanded)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        H    = C.PANEL_HEAD_H

        body = clipped_path(0, 0, w, h)

        # Glass fill — uses PANEL_GLASS_TOP / BOT tokens via utils
        panel_glass_fill(p, 0, 0, w, h)

        # Border — dim normally, bright on hover
        bc = QColor(C.CYAN); bc.setAlpha(180 if self._hover else 60)
        p.setPen(QPen(bc, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(body)

        # Hover outer glow
        if self._hover:
            gc = QColor(C.CYAN); gc.setAlpha(18)
            p.setPen(QPen(gc, 6))
            p.drawPath(clipped_path(-3, -3, w + 6, h + 6))

        # Heading band
        hg = QLinearGradient(0, 0, w, 0)
        h1 = QColor(C.CYAN); h1.setAlpha(32)
        h2 = QColor(C.CYAN); h2.setAlpha(6)
        hg.setColorAt(0.0, h1); hg.setColorAt(1.0, h2)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(clipped_path(0, 0, w, H), QBrush(hg))

        # Heading rule
        rc = QColor(C.CYAN); rc.setAlpha(40)
        p.setPen(QPen(rc, 1))
        p.drawLine(0, H, w, H)

        # Title — FONT_SIZE_TITLE, bold, letter-spaced
        tc = QColor(C.CYAN); tc.setAlpha(230)
        p.setPen(tc)
        font = QFont(C.FONT_HUD, C.FONT_SIZE_TITLE)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        p.setFont(font)
        p.drawText(QRectF(C.SP_2, 0, w - C.SP_2 * 3, H),
                   Qt.AlignmentFlag.AlignVCenter, self._title)

        # Collapse chevron
        if self._collapsible:
            cc = QColor(C.CYAN_DIM); cc.setAlpha(160)
            p.setPen(cc)
            font2 = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
            p.setFont(font2)
            p.drawText(QRectF(w - 20, 0, 16, H),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       "▾" if self._expanded else "▸")

        # Clip-corner accent triangle
        tri = QPainterPath()
        tri.moveTo(w - C.PANEL_CLIP, 0)
        tri.lineTo(w, 0)
        tri.lineTo(w, C.PANEL_CLIP)
        tri.closeSubpath()
        ta = QColor(C.CYAN); ta.setAlpha(50)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(tri, QBrush(ta))

        p.end()


# ─────────────────────────────────────────────────────────────────
# MetricRow  — label · bar · value
# ─────────────────────────────────────────────────────────────────
class MetricRow(QWidget):

    # Label column is fixed at this width so bars always start at the same x
    _LBL_W = 52

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(C.ROW_H)
        self._label = label.upper()
        self._value = 0.0
        self._text  = "0%"
        self.setStyleSheet("background: transparent;")

    def set_value(self, v: float, text: str = None):
        self._value = max(0.0, min(100.0, float(v)))
        self._text  = text or f"{self._value:.0f}%"
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        VAL_W  = C.VAL_COL_W    # value column width from theme token
        LBL_W  = self._LBL_W
        GAP    = C.SP_1
        bar_x  = LBL_W + GAP
        bar_w  = w - LBL_W - GAP - VAL_W - GAP
        bar_y  = (h - C.BAR_H) // 2
        radius = C.BAR_H / 2

        # Label — FONT_SIZE_SMALL, muted
        font_lbl = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        p.setFont(font_lbl)
        lc = QColor(C.COLOR_TEXT_MID)
        p.setPen(lc)
        p.drawText(0, 0, LBL_W, h, Qt.AlignmentFlag.AlignVCenter, self._label)

        # Track — rounded
        p.setPen(Qt.PenStyle.NoPen)
        tc = QColor(C.CYAN_FAINT); tc.setAlpha(180)
        p.setBrush(QBrush(tc))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, C.BAR_H), radius, radius)

        # Fill — colour by severity, rounded
        fw = int(bar_w * self._value / 100)
        if fw > 0:
            if self._value >= 90:
                fc = QColor(C.COLOR_CRITICAL)
            elif self._value >= 75:
                fc = QColor(C.COLOR_WARN)
            else:
                fc = QColor(C.CYAN)
            fc.setAlpha(210)
            p.setBrush(QBrush(fc))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fw, C.BAR_H), radius, radius)

            # Glow cap — small bright dot at the leading edge
            gc = QColor(C.CYAN); gc.setAlpha(240)
            p.setBrush(QBrush(gc))
            cap_x = bar_x + fw - radius
            p.drawEllipse(QPointF(cap_x, bar_y + C.BAR_H / 2), radius + 1, radius + 1)

        # Value — FONT_SIZE_BODY bold, gold
        font_val = QFont(C.FONT_MONO, C.FONT_SIZE_BODY)
        font_val.setBold(True)
        p.setFont(font_val)
        vc = QColor(C.GOLD)
        p.setPen(vc)
        p.drawText(w - VAL_W, 0, VAL_W, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   self._text)
        p.end()


# ─────────────────────────────────────────────────────────────────
# StatusDot  — 3-state coloured dot + label text
# ─────────────────────────────────────────────────────────────────
class StatusDot(QWidget):
    """
    3-state status indicator.
    Call set_status(state)  where state is one of:
        "ok"   | "OK"   → cyan dot
        "warn" | "WARN" → warning amber dot
        "crit" | "CRIT" → critical red dot
    Legacy 2-state bool (set_status(True/False)) still works for
    backward compatibility.
    """

    DOT_R = 4   # dot radius in px

    # Colour map keyed on normalised state string
    _STATE_COLORS = {
        "ok":   "CYAN",
        "warn": "WARN",
        "crit": "CRIT",
    }

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(C.ROW_H)
        self._label = label
        self._state = "ok"   # "ok" | "warn" | "crit"
        self.setStyleSheet("background: transparent;")

    # ── Public ────────────────────────────────────────────────────
    def set_status(self, state):
        """Accept str ('ok'/'warn'/'crit') or bool (True→ok, False→crit)."""
        if isinstance(state, bool):
            self._state = "ok" if state else "crit"
        else:
            self._state = str(state).lower()
        self.update()

    def set_label(self, label: str):
        self._label = label
        self.update()

    # ── Paint ─────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()

        # Pick dot colour from state
        state = self._state if self._state in self._STATE_COLORS else "ok"
        if state == "ok":
            dot_col = QColor(C.COLOR_OK)
        elif state == "warn":
            dot_col = QColor(C.COLOR_WARN)
        else:
            dot_col = QColor(C.COLOR_CRITICAL)

        # Outer glow halo
        glow = QColor(dot_col); glow.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(self.DOT_R + 1, h / 2),
                      self.DOT_R + 2, self.DOT_R + 2)

        # Dot core — vertically centred
        p.setBrush(QBrush(dot_col))
        p.drawEllipse(QPointF(self.DOT_R + 1, h / 2), self.DOT_R, self.DOT_R)

        # Label — FONT_SIZE_SMALL, muted
        tc = QColor(C.COLOR_TEXT_MID)
        p.setPen(tc)
        font = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        p.setFont(font)
        left = self.DOT_R * 2 + C.SP_2
        p.drawText(left, 0, self.width() - left, h,
                   Qt.AlignmentFlag.AlignVCenter, self._label.upper())
        p.end()
