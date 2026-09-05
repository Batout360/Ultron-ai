# ui/ai_core.py
# Animated AI Core Widget — Pure Holographic Orange
# Fully custom-painted using QPainter (no external assets required)

import math
import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore    import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui     import (
    QPainter, QPen, QBrush, QColor, QFont,
    QRadialGradient, QConicalGradient, QPainterPath,
    QLinearGradient,
)
import theme as C


# ---------------------------------------------------------------------------
# Particle
# ---------------------------------------------------------------------------
class _Particle:
    def __init__(self, cx, cy, radius):
        self.reset(cx, cy, radius)

    def reset(self, cx, cy, radius):
        angle = random.uniform(0, 2 * math.pi)
        r     = random.uniform(radius * 0.3, radius * 0.95)
        self.x  = cx + r * math.cos(angle)
        self.y  = cy + r * math.sin(angle)
        self.vx = random.uniform(-0.4, 0.4)
        self.vy = random.uniform(-0.4, 0.4)
        self.life    = random.uniform(0.6, 1.0)
        self.decay   = random.uniform(0.004, 0.012)
        self.size    = random.uniform(1.5, 3.5)
        self._cx     = cx
        self._cy     = cy
        self._radius = radius

    def update(self):
        self.x    += self.vx
        self.y    += self.vy
        self.life -= self.decay
        if self.life <= 0:
            self.reset(self._cx, self._cy, self._radius)


# ---------------------------------------------------------------------------
# AICoreWidget
# ---------------------------------------------------------------------------
class AICoreWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)

        # Animation state
        self._angle1   = 0.0    # outer ring
        self._angle2   = 0.0    # middle ring (counter)
        self._angle3   = 0.0    # inner ring
        self._scan_ang = 0.0    # radar sweep
        self._pulse    = 0.0    # center pulse phase
        self._flicker  = 1.0    # brightness flicker

        # AI data
        self._neural    = 72.0
        self._proc      = 55.0
        self._conf      = 91.0
        self._task      = "MONITORING"
        self._phase     = 0.0

        # Particles
        self._particles: list[_Particle] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(C.ANIMATION_TICK_MS)

        self.setStyleSheet("background: transparent;")

    # ------------------------------------------------------------------
    def update_ai_state(self, data: dict):
        self._neural = data.get("neural", self._neural)
        self._proc   = data.get("processing", self._proc)
        self._conf   = data.get("confidence", self._conf)
        self._task   = data.get("task", self._task)
        self._phase  = data.get("phase", self._phase)

    # ------------------------------------------------------------------
    def _tick(self):
        self._angle1   = (self._angle1 + 0.5)  % 360
        self._angle2   = (self._angle2 - 0.3)  % 360
        self._angle3   = (self._angle3 + 1.1)  % 360
        self._scan_ang = (self._scan_ang + 1.8) % 360
        self._pulse   += 0.07
        self._flicker  = 0.88 + 0.12 * (0.5 + 0.5 * math.sin(self._pulse * 3.7 + random.uniform(-0.1, 0.1)))

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.42

        # Maintain ~40 particles
        while len(self._particles) < 40:
            self._particles.append(_Particle(cx, cy, r))
        for p in self._particles:
            p._cx, p._cy, p._radius = cx, cy, r
            p.update()

        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        R = min(w, h) * 0.42          # outer ring radius

        self._draw_bg_grid(painter, w, h)
        self._draw_particles(painter, cx, cy)
        self._draw_outer_ring(painter, cx, cy, R)
        self._draw_tick_ring(painter, cx, cy, R * 0.86)
        self._draw_rotating_ring(painter, cx, cy, R * 0.75, self._angle1, dashed=True)
        self._draw_data_arc(painter, cx, cy, R * 0.63, self._neural / 100)
        self._draw_rotating_ring(painter, cx, cy, R * 0.54, self._angle2, dashed=False, width=1.0)
        self._draw_scan_sweep(painter, cx, cy, R * 0.75)
        self._draw_data_arc(painter, cx, cy, R * 0.45, self._proc / 100, color=C.COLOR_ACCENT)
        self._draw_rotating_ring(painter, cx, cy, R * 0.36, self._angle3, dashed=True, width=1.0, color=C.COLOR_DIM)
        self._draw_center_sphere(painter, cx, cy, R * 0.22)
        self._draw_labels(painter, cx, cy, R, w, h)

        painter.end()

    # ------------------------------------------------------------------
    def _draw_bg_grid(self, p: QPainter, w, h):
        p.setPen(QPen(QColor(C.COLOR_GRID), 0.5))
        step = 28
        for x in range(0, w, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            p.drawLine(0, y, w, y)

    # ------------------------------------------------------------------
    def _draw_particles(self, p: QPainter, cx, cy):
        for pt in self._particles:
            alpha = int(pt.life * 200 * self._flicker)
            col   = QColor(C.COLOR_PRIMARY)
            col.setAlpha(max(0, min(255, alpha)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(col))
            p.drawEllipse(QPointF(pt.x, pt.y), pt.size, pt.size)

    # ------------------------------------------------------------------
    def _draw_outer_ring(self, p: QPainter, cx, cy, R):
        # Glow halo
        for glow_r, alpha in [(R + 8, 30), (R + 4, 60), (R, 160)]:
            col = QColor(C.COLOR_PRIMARY)
            col.setAlpha(int(alpha * self._flicker))
            pen = QPen(col, 2 if glow_r == R else 1)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

    # ------------------------------------------------------------------
    def _draw_tick_ring(self, p: QPainter, cx, cy, R):
        p.save()
        p.translate(cx, cy)
        major_col = QColor(C.COLOR_PRIMARY); major_col.setAlpha(200)
        minor_col = QColor(C.COLOR_DIM);     minor_col.setAlpha(120)
        for i in range(72):
            ang_rad = math.radians(i * 5)
            is_major = (i % 9 == 0)
            tick_len = 10 if is_major else 5
            pen = QPen(major_col if is_major else minor_col, 1.5 if is_major else 0.8)
            p.setPen(pen)
            x1 = (R - tick_len) * math.cos(ang_rad)
            y1 = (R - tick_len) * math.sin(ang_rad)
            x2 = R * math.cos(ang_rad)
            y2 = R * math.sin(ang_rad)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        p.restore()

    # ------------------------------------------------------------------
    def _draw_rotating_ring(self, p: QPainter, cx, cy, R, angle,
                             dashed=False, width=1.5, color=None):
        color = color or C.COLOR_PRIMARY
        col = QColor(color)
        col.setAlpha(int(180 * self._flicker))
        pen = QPen(col, width)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        p.save()
        p.translate(cx, cy)
        p.rotate(angle)
        p.drawEllipse(QPointF(0, 0), R, R)
        # Corner notches
        notch_col = QColor(C.COLOR_GLOW)
        notch_col.setAlpha(220)
        p.setPen(QPen(notch_col, 2))
        for deg in range(0, 360, 90):
            rad = math.radians(deg)
            x, y = R * math.cos(rad), R * math.sin(rad)
            p.drawEllipse(QPointF(x, y), 3, 3)
        p.restore()

    # ------------------------------------------------------------------
    def _draw_data_arc(self, p: QPainter, cx, cy, R, fraction,
                       color=None):
        color = color or C.COLOR_PRIMARY
        # Background track
        track_col = QColor(C.COLOR_FAINT)
        track_col.setAlpha(120)
        p.setPen(QPen(track_col, 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(cx - R, cy - R, R * 2, R * 2)
        p.drawEllipse(QPointF(cx, cy), R, R)

        # Filled arc
        arc_col = QColor(color)
        arc_col.setAlpha(int(220 * self._flicker))
        pen = QPen(arc_col, 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        span = int(fraction * 360 * 16)
        p.drawArc(rect, 90 * 16, -span)

    # ------------------------------------------------------------------
    def _draw_scan_sweep(self, p: QPainter, cx, cy, R):
        p.save()
        p.translate(cx, cy)
        p.rotate(self._scan_ang)

        grad = QConicalGradient(QPointF(0, 0), 0)
        sweep_col = QColor(C.COLOR_PRIMARY); sweep_col.setAlpha(80)
        clear_col = QColor(C.COLOR_PRIMARY); clear_col.setAlpha(0)
        grad.setColorAt(0.0,  sweep_col)
        grad.setColorAt(0.25, clear_col)
        grad.setColorAt(1.0,  clear_col)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(0, 0), R, R)

        # Leading edge line
        line_col = QColor(C.COLOR_BRIGHT); line_col.setAlpha(200)
        p.setPen(QPen(line_col, 1.5))
        p.drawLine(QPointF(0, 0), QPointF(R, 0))
        p.restore()

    # ------------------------------------------------------------------
    def _draw_center_sphere(self, p: QPainter, cx, cy, R):
        # Outer glow rings
        for r_off, alpha in [(R + 14, 25), (R + 8, 50), (R + 3, 90)]:
            glow = QColor(C.COLOR_PRIMARY); glow.setAlpha(int(alpha * self._flicker))
            p.setPen(QPen(glow, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r_off, r_off)

        # Radial gradient fill
        grad = QRadialGradient(QPointF(cx - R * 0.3, cy - R * 0.3), R * 1.5)
        center_col = QColor(C.COLOR_GLOW);   center_col.setAlpha(int(230 * self._flicker))
        mid_col    = QColor(C.COLOR_PRIMARY); mid_col.setAlpha(int(180 * self._flicker))
        edge_col   = QColor(C.COLOR_BG);     edge_col.setAlpha(255)
        grad.setColorAt(0.0,  center_col)
        grad.setColorAt(0.4,  mid_col)
        grad.setColorAt(1.0,  edge_col)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), R, R)

        # Inner bright dot
        bright = QRadialGradient(QPointF(cx - R * 0.2, cy - R * 0.2), R * 0.5)
        dot_col = QColor(C.COLOR_WHITE); dot_col.setAlpha(int(200 * self._flicker))
        dot_col2 = QColor(C.COLOR_GLOW); dot_col2.setAlpha(0)
        bright.setColorAt(0.0, dot_col)
        bright.setColorAt(1.0, dot_col2)
        p.setBrush(QBrush(bright))
        p.drawEllipse(QPointF(cx, cy), R * 0.6, R * 0.6)

    # ------------------------------------------------------------------
    def _draw_labels(self, p: QPainter, cx, cy, R, w, h):
        # "AI CORE" above center
        title_col = QColor(C.COLOR_BRIGHT); title_col.setAlpha(int(240 * self._flicker))
        p.setPen(title_col)
        font = QFont(C.FONT_HUD, C.FONT_SIZE_TITLE)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        p.setFont(font)
        p.drawText(QRectF(0, cy - R * 0.82, w, 24), Qt.AlignmentFlag.AlignHCenter, "AI CORE")

        # Processing % inside center sphere
        pct_col = QColor(C.COLOR_WHITE); pct_col.setAlpha(int(230 * self._flicker))
        p.setPen(pct_col)
        font2 = QFont(C.FONT_MONO, C.FONT_SIZE_LARGE)
        font2.setBold(True)
        p.setFont(font2)
        pct_text = f"{int(self._proc):02d}%"
        p.drawText(QRectF(cx - 40, cy - 14, 80, 28), Qt.AlignmentFlag.AlignCenter, pct_text)

        # "ACTIVE" subtitle
        sub_col = QColor(C.COLOR_DIM); sub_col.setAlpha(200)
        p.setPen(sub_col)
        font3 = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        font3.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(font3)
        p.drawText(QRectF(cx - 40, cy + 12, 80, 16), Qt.AlignmentFlag.AlignCenter, "ACTIVE")

        # Neural label (outer ring)
        lbl_col = QColor(C.COLOR_TEXT_MID); lbl_col.setAlpha(180)
        p.setPen(lbl_col)
        font4 = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        p.setFont(font4)
        # Top label — neural
        p.drawText(QRectF(cx - 60, cy - R * 0.67, 120, 14),
                   Qt.AlignmentFlag.AlignCenter,
                   f"NEURAL  {self._neural:.0f}%")
        # Bottom label — confidence
        p.drawText(QRectF(cx - 60, cy + R * 0.58, 120, 14),
                   Qt.AlignmentFlag.AlignCenter,
                   f"CONF  {self._conf:.0f}%")

        # SYSTEM ONLINE top
        sys_col = QColor(C.COLOR_PRIMARY); sys_col.setAlpha(int(220 * self._flicker))
        p.setPen(sys_col)
        font5 = QFont(C.FONT_HUD, C.FONT_SIZE_SMALL)
        font5.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
        p.setFont(font5)
        p.drawText(QRectF(0, 6, w, 16), Qt.AlignmentFlag.AlignHCenter, "SYSTEM ONLINE")

        # Task label bottom
        task_col = QColor(C.COLOR_ACCENT); task_col.setAlpha(180)
        p.setPen(task_col)
        font6 = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        font6.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        p.setFont(font6)
        p.drawText(QRectF(0, h - 22, w, 16), Qt.AlignmentFlag.AlignHCenter, self._task)

        # Cross-hair lines through center
        cross_col = QColor(C.COLOR_PRIMARY); cross_col.setAlpha(30)
        p.setPen(QPen(cross_col, 1, Qt.PenStyle.DotLine))
        p.drawLine(QPointF(0, cy), QPointF(w, cy))
        p.drawLine(QPointF(cx, 0), QPointF(cx, h))
