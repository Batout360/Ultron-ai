# ui/ai_core.py — ULTRON 3.0
# AI Core — JARVIS Machine Brain Particle Swarm
#
# Performance design:
#   • COUNT = 800   — QPainter sweet spot; additive blending makes it look
#                     far denser than the raw number suggests
#   • SimThread     — all math runs on a worker QThread; main thread only
#                     calls update() to schedule a repaint, never blocks
#   • paintEvent    — switches to CompositionMode_Plus (additive, mirrors
#                     Three.js AdditiveBlending) then draws 800×2 ellipses.
#                     Two layers (glow + core) instead of four cuts draw
#                     calls in half vs previous attempts.
#   • _hsl_to_qcolor— inlined HSL→QColor with no intermediate objects
#
# 5-layer brain geometry (verbatim port of the HTML source):
#   Layer 0-2  Cortex Shell      — gyri-wrinkled prolate spheroid surface
#   Layer 3-4  White Matter      — circuit axon grid bundles
#   Layer 5-6  Signal Wavefronts — travelling action-potential pulses
#   Layer 7    Equatorial Arc    — JARVIS scan ring
#   Layer 8    Molten Core       — arc-reactor singularity
#
# Colour palette (verbatim from HTML): molten gold/amber hue 0.06–0.11

import math
import random

from PySide6.QtWidgets import QWidget
from PySide6.QtCore    import Qt, QThread, Signal, QMutex, QMutexLocker, QTimer, QRectF, QPointF
from PySide6.QtGui     import QPainter, QPen, QBrush, QColor, QFont, QRadialGradient

import theme as C

# ─────────────────────────────────────────────────────────────────
# Tuning
# ─────────────────────────────────────────────────────────────────
COUNT        = 800    # particles — fast in QPainter, looks dense with additive blend
LERP         = 0.10
TICK_MS      = 33     # ≈30 fps

SIGNAL_SPEED   = 1.8
FIRE_INTENSITY = 0.72
BRAIN_SCALE    = 0.40   # fraction of min(w,h) → world-space brain radius
CORE_GLOW      = 0.65


# ─────────────────────────────────────────────────────────────────
# Fast helpers
# ─────────────────────────────────────────────────────────────────
def _frac(x: float) -> float:
    return x - math.floor(x)


def _hsl_qcolor(h: float, s: float, l: float, alpha: int) -> QColor:
    """Inline HSL→QColor, no intermediate allocations."""
    h = max(0.0, min(1.0, h))
    s = max(0.0, min(1.0, s))
    l = max(0.0, min(1.0, l))
    if s == 0.0:
        v = int(l * 255)
        return QColor(v, v, v, alpha)
    q = l * (1.0 + s) if l < 0.5 else l + s - l * s
    p2 = 2.0 * l - q
    def ch(t):
        t %= 1.0
        if t < 1/6: return p2 + (q - p2) * 6.0 * t
        if t < 0.5: return q
        if t < 2/3: return p2 + (q - p2) * (2/3 - t) * 6.0
        return p2
    return QColor(int(ch(h + 1/3)*255), int(ch(h)*255), int(ch(h - 1/3)*255), alpha)


# ─────────────────────────────────────────────────────────────────
# Particle state — flat lists, no per-object attribute overhead
# ─────────────────────────────────────────────────────────────────
class _Buf:
    def __init__(self, n: int):
        self.sx  = [random.uniform(-300, 300) for _ in range(n)]  # screen x (smoothed)
        self.sy  = [random.uniform(-300, 300) for _ in range(n)]  # screen y (smoothed)
        self.r   = [200] * n
        self.g   = [150] * n
        self.b   = [30]  * n
        self.a   = [180] * n
        self.sz  = [1.5] * n


# ─────────────────────────────────────────────────────────────────
# Simulation thread
# ─────────────────────────────────────────────────────────────────
class _SimThread(QThread):
    frame_ready = Signal()

    def __init__(self, buf: _Buf, parent=None):
        super().__init__(parent)
        self._buf      = buf
        self._running  = False
        self._time     = 0.0
        self._w        = 512
        self._h        = 512
        self._mutex    = QMutex()

        # Pre-compute constant per-particle seeds
        self._fA = [_frac(i * 1.6180339887 * 7919.0) for i in range(COUNT)]
        self._fB = [_frac(i * 2.2360679774 * 6271.0) for i in range(COUNT)]
        self._fC = [_frac(i * 0.7071067811 * 4987.0) for i in range(COUNT)]
        self._fD = [_frac(i * 1.4142135623 * 3571.0) for i in range(COUNT)]

    def set_size(self, w: int, h: int):
        with QMutexLocker(self._mutex):
            self._w, self._h = w, h

    def stop(self):
        self._running = False
        self.wait(500)

    def run(self):
        self._running = True
        while self._running:
            with QMutexLocker(self._mutex):
                w, h = self._w, self._h
            self._step(w, h)
            self.frame_ready.emit()
            self.msleep(TICK_MS)

    def _step(self, w: int, h: int):
        if w < 4 or h < 4:
            return

        self._time += TICK_MS / 1000.0
        time        = self._time
        t           = time * SIGNAL_SPEED
        brain       = min(w, h) * BRAIN_SCALE
        cx          = w * 0.5
        cy          = h * 0.5
        flicker     = 0.88 + 0.12 * (0.5 + 0.5 * math.sin(time * 3.7))
        tau         = math.tau
        pi          = math.pi

        rot_a = time * 0.07
        cos_r = math.cos(rot_a)
        sin_r = math.sin(rot_a)

        buf  = self._buf
        fA   = self._fA
        fB   = self._fB
        fC   = self._fC
        fD   = self._fD
        lerp = LERP

        for i in range(COUNT):
            fa = fA[i]; fb = fB[i]; fc = fC[i]; fd = fD[i]
            layer = i % 9

            # ── Brain surface geometry ─────────────────────────────
            phi    = fa * pi
            theta  = fb * tau
            sin_ph = math.sin(phi);  cos_ph = math.cos(phi)
            sin_th = math.sin(theta); cos_th = math.cos(theta)

            bx0 = brain * 1.15 * sin_ph * cos_th
            by0 = brain * 0.82 * cos_ph
            bz0 = brain * 0.95 * sin_ph * sin_th

            hemi    = 1.0 if bx0 >= 0 else -1.0
            fissure = math.exp(-bx0*bx0 * 0.0012 / (brain*brain + 1e-6)) * brain * 0.125
            bx = bx0 + hemi * fissure

            gyri = 1.8 * brain/44.0 * (
                math.sin(phi*6.0 + fc*4.0) * math.cos(theta*4.2 + fd*3.0)
            )
            nx = sin_ph*cos_th;  ny = cos_ph;  nz = sin_ph*sin_th
            gx = bx  + nx*gyri
            gy = by0 + ny*gyri
            gz = bz0 + nz*gyri

            # ── Per-layer geometry + colour ────────────────────────
            if layer <= 2:
                # Cortex Shell
                jitter = (0.9 + fc*1.2) * brain/44.0
                pulse  = math.sin(t*1.4 + fa*9.7) * 0.5
                sj = jitter + pulse*brain/44.0
                px3 = gx + nx*sj;  py3 = gy + ny*sj;  pz3 = gz + nz*sj
                hue = 0.095 + 0.025*math.sin((i/COUNT)*11.0 + t*0.3)
                sat = 0.95
                lit = 0.28 + 0.18*fa + 0.12*abs(pulse)
                sz  = 1.8

            elif layer <= 4:
                # White Matter
                ti  = math.floor(fc*180.0)
                ta  = ti * (tau/180.0)
                tp  = fb
                tr  = brain*(0.30 + 0.55*tp)
                lb  = math.floor(fd*9.0) * (pi/9.0)
                cl  = math.cos(lb);  sl = math.sin(lb)
                px3 = tr*math.cos(ta)*sl
                py3 = tr*cl*(0.85 + 0.15*math.sin(t*0.5 + ti*0.4))
                pz3 = tr*math.sin(ta)*sl
                fv  = math.sin(t*3.0 + tp*tau + ti*1.3) * FIRE_INTENSITY
                hue = 0.08 + 0.03*math.sin(tp*8.0 + t*0.8)
                sat = 1.0
                lit = 0.22 + 0.30*tp + 0.28*abs(fv)
                sz  = 1.5

            elif layer <= 6:
                # Signal Wavefronts
                ai  = math.floor(fa*60.0)
                aa  = ai*(tau/60.0)
                al  = math.floor(fd*6.0)*(pi/6.0)
                st2 = fb + t*0.55 + ai*0.07
                sp  = st2 - math.floor(st2)
                sr  = brain*(0.08 + 0.88*sp)
                cal = math.cos(al);  sal = math.sin(al)
                px3 = sr*math.cos(aa)*sal
                py3 = sr*cal
                pz3 = sr*math.sin(aa)*sal
                spike = math.exp(-((sp-0.9)*12.0)**2)
                tail  = math.exp(-((sp-0.85)*4.0)**2)*0.4
                hue = 0.07 + 0.04*spike
                sat = 1.0
                lit = 0.35 + 0.55*(spike+tail)*FIRE_INTENSITY
                sz  = 1.3 + spike*2.2

            elif layer == 7:
                # Arc Ring
                ra  = fa*tau + t*0.22
                rt  = fb*0.5 - 0.25
                rr  = brain*(1.02 + 0.04*math.sin(t*2.0 + fa*12.0))
                rs  = (1.5*fc - 0.75)*brain/44.0
                px3 = rr*math.cos(ra)
                py3 = rr*math.sin(rt) + rs
                pz3 = rr*math.sin(ra)
                rp  = math.sin(t*4.0 + fa*tau)*0.5 + 0.5
                hue = 0.10 + 0.02*rp
                sat = 1.0
                lit = 0.50 + 0.40*rp*CORE_GLOW
                sz  = 2.0 + rp*1.2

            else:
                # Molten Core
                cr  = brain*0.18*(0.4 + 0.6*fa)
                ca  = fb*tau + t*(1.5 + fc*2.0)
                ce  = (fd-0.5)*1.8
                tw  = math.sin(t*2.3 + fa*5.0)*0.8
                px3 = cr*math.cos(ca+tw)
                py3 = cr*math.sin(ce) + math.sin(t*1.7 + fb*4.0)*brain*0.04
                pz3 = cr*math.sin(ca+tw*0.7)
                rn  = cr/(brain*0.18 + 1e-6)
                hue = 0.06 + 0.06*rn
                sat = 0.90 + 0.10*rn
                lit = 0.80 - 0.45*rn + 0.15*CORE_GLOW*abs(math.sin(t*3.1 + fa*7.0))
                sz  = 2.5 - rn*0.8

            # ── Y-axis rotation → screen ───────────────────────────
            fx =  px3*cos_r - pz3*sin_r
            fy =  py3

            tx = cx + fx
            ty = cy - fy   # flip Y

            # Lerp
            buf.sx[i] += (tx - buf.sx[i]) * lerp
            buf.sy[i] += (ty - buf.sy[i]) * lerp

            # Colour
            col = _hsl_qcolor(hue, sat, lit, 0)
            buf.r[i] = col.red()
            buf.g[i] = col.green()
            buf.b[i] = col.blue()
            buf.a[i] = max(20, min(240, int(lit*255*flicker)))
            buf.sz[i] = max(0.6, min(5.5, sz))


# ─────────────────────────────────────────────────────────────────
# Widget
# ─────────────────────────────────────────────────────────────────
class AICoreWidget(QWidget):
    """Drop-in replacement. Public API: update_ai_state(data: dict)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.setStyleSheet("background: transparent;")

        self._neural  = 72.0
        self._proc    = 55.0
        self._conf    = 91.0
        self._task    = "MONITORING"
        self._phase   = 0.0
        self._flicker = 1.0

        self._buf = _Buf(COUNT)
        self._sim = _SimThread(self._buf, self)
        self._sim.frame_ready.connect(self.update)
        self._sim.set_size(self.width() or 512, self.height() or 512)
        self._sim.start()

        # Lightweight flicker on main thread
        self._ftimer = QTimer(self)
        self._ftimer.timeout.connect(self._tick_flicker)
        self._ftimer.start(TICK_MS)

    def update_ai_state(self, data: dict):
        self._neural  = data.get("neural",     self._neural)
        self._proc    = data.get("processing", self._proc)
        self._conf    = data.get("confidence", self._conf)
        self._task    = data.get("task",       self._task)
        self._phase   = data.get("phase",      self._phase)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sim.set_size(self.width(), self.height())

    def closeEvent(self, event):
        self._sim.stop()
        super().closeEvent(event)

    def _tick_flicker(self):
        self._phase  += TICK_MS / 1000.0
        self._flicker = 0.88 + 0.12*(0.5 + 0.5*math.sin(self._phase*3.7))

    # ── Paint ─────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h   = self.width(), self.height()
        cx, cy = w*0.5, h*0.5
        R      = min(w, h) * BRAIN_SCALE

        # 1. Background
        painter.fillRect(0, 0, w, h, QColor(C.COLOR_BG))

        # 2. Nebula glow — two radial passes
        self._draw_nebula(painter, cx, cy, R)

        # 3. Particles — additive compositing
        #    CompositionMode_Plus: RGB values add together.
        #    Overlapping particles genuinely accumulate light → bloom for free.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        painter.setPen(Qt.PenStyle.NoPen)

        buf = self._buf
        for i in range(COUNT):
            r, g, b, a, sz = buf.r[i], buf.g[i], buf.b[i], buf.a[i], buf.sz[i]
            qp = QPointF(buf.sx[i], buf.sy[i])

            # Glow layer
            painter.setBrush(QBrush(QColor(r, g, b, max(0, int(a*0.22)))))
            painter.drawEllipse(qp, sz*3.0, sz*3.0)

            # Core dot
            painter.setBrush(QBrush(QColor(r, g, b, min(255, a))))
            painter.drawEllipse(qp, sz*0.7, sz*0.7)

        # 4. Back to normal for HUD text
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        self._draw_labels(painter, cx, cy, R, w, h)
        painter.end()

    def _draw_nebula(self, painter: QPainter, cx: float, cy: float, R: float):
        # Wide amber ambient
        g1 = QRadialGradient(QPointF(cx, cy), R * 1.1)
        c1 = QColor(C.GOLD);       c1.setAlpha(28)
        c2 = QColor(C.COLOR_GLOW); c2.setAlpha(10)
        c3 = QColor(C.COLOR_BG);   c3.setAlpha(0)
        g1.setColorAt(0.0, c1); g1.setColorAt(0.4, c2); g1.setColorAt(1.0, c3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(g1))
        painter.drawEllipse(QPointF(cx, cy), R*1.1, R*1.1)

        # Tight bright core
        g2 = QRadialGradient(QPointF(cx, cy), R*0.20)
        d1 = QColor(C.GOLD_BRIGHT); d1.setAlpha(60)
        d2 = QColor(C.COLOR_BG);    d2.setAlpha(0)
        g2.setColorAt(0.0, d1); g2.setColorAt(1.0, d2)
        painter.setBrush(QBrush(g2))
        painter.drawEllipse(QPointF(cx, cy), R*0.20, R*0.20)

    def _draw_labels(self, painter: QPainter, cx: float, cy: float,
                     R: float, w: float, h: float):
        fl = self._flicker

        # "AI CORE"
        col = QColor(C.GOLD); col.setAlpha(int(220*fl))
        painter.setPen(col)
        font = QFont(C.FONT_HUD, C.FONT_SIZE_TITLE)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5)
        painter.setFont(font)
        painter.drawText(QRectF(0, 8, w, 22), Qt.AlignmentFlag.AlignHCenter, "AI CORE")

        # Processing %
        col2 = QColor(C.GOLD_BRIGHT); col2.setAlpha(int(220*fl))
        painter.setPen(col2)
        f2 = QFont(C.FONT_MONO, C.FONT_SIZE_DISPLAY); f2.setBold(True)
        painter.setFont(f2)
        dh = R*0.20
        painter.drawText(QRectF(cx - R*0.60, cy - dh, R*1.20, dh*2),
                         Qt.AlignmentFlag.AlignCenter, f"{int(self._proc):02d}%")

        # Neural %
        col3 = QColor(C.GOLD_DIM); col3.setAlpha(200)
        painter.setPen(col3)
        f3 = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        f3.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        painter.setFont(f3)
        ry = cy + R*0.14
        painter.drawText(QRectF(cx - R*0.50, ry, R*1.00, R*0.12),
                         Qt.AlignmentFlag.AlignCenter, f"NEURAL  {self._neural:.0f}%")

        # Confidence %
        col4 = QColor(C.GOLD); col4.setAlpha(170)
        painter.setPen(col4)
        f4 = QFont(C.FONT_MONO, C.FONT_SIZE_SMALL)
        painter.setFont(f4)
        painter.drawText(QRectF(cx - R*0.50, ry + R*0.13, R*1.00, R*0.12),
                         Qt.AlignmentFlag.AlignCenter, f"CONF  {self._conf:.0f}%")

        # Task label bottom
        col5 = QColor(C.CYAN); col5.setAlpha(int(180*fl))
        painter.setPen(col5)
        f5 = QFont(C.FONT_HUD, C.FONT_SIZE_SMALL)
        f5.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        painter.setFont(f5)
        painter.drawText(QRectF(0, h - R*0.14, w, R*0.12),
                         Qt.AlignmentFlag.AlignHCenter, f"[ {self._task} ]")

        # Faint crosshair
        col6 = QColor(C.COLOR_PRIMARY); col6.setAlpha(18)
        painter.setPen(QPen(col6, 1, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(0, cy), QPointF(w, cy))
        painter.drawLine(QPointF(cx, 0), QPointF(cx, h))
