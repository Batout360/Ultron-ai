# ui/utils.py — Shared paint helpers for ULTRON 3.0
#
# Single source for the clipped-corner panel shape and glass fill.
# Import here instead of duplicating in every widget file.

from PySide6.QtGui  import QPainterPath, QLinearGradient, QBrush, QColor
from PySide6.QtCore import Qt
import theme as C


def clipped_path(x: float, y: float, w: float, h: float,
                 clip: int = None) -> QPainterPath:
    """
    Pentagon with top-right corner clipped — the primary panel shape.

        TL ──────────────── (w-clip, 0)
        |                    ╲
        |                     (w, clip)
        |                     |
        BL ─────────────── BR

    `clip` defaults to theme.PANEL_CLIP (12 px).
    """
    c = clip if clip is not None else C.PANEL_CLIP
    path = QPainterPath()
    path.moveTo(x,         y)
    path.lineTo(x + w - c, y)
    path.lineTo(x + w,     y + c)
    path.lineTo(x + w,     y + h)
    path.lineTo(x,         y + h)
    path.closeSubpath()
    return path


def panel_glass_fill(painter, x: float, y: float, w: float, h: float,
                     clip: int = None):
    """
    Fill a clipped-corner panel with the standard dark navy glass gradient.
    Sets NoPen internally; caller retains control of brush after return.
    """
    path = clipped_path(x, y, w, h, clip)
    grad = QLinearGradient(x, y, x, y + h)
    c1 = QColor(C.PANEL_GLASS_TOP); c1.setAlpha(220)
    c2 = QColor(C.PANEL_GLASS_BOT); c2.setAlpha(190)
    grad.setColorAt(0.0, c1)
    grad.setColorAt(1.0, c2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.fillPath(path, QBrush(grad))
