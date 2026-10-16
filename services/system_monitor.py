# services/system_monitor.py — ULTRON 3.0
# Real-time system metrics via psutil
#
# 3.0 changes:
#   • Disk usage now queries the drive where THIS file lives (fixes D: vs C: on Windows)
#   • Adds threshold_crossed(metric: str, state: str, value: float) signal
#     emitted when a metric crosses 75 % (warn) or 90 % (crit) thresholds
#   • Tracks previous values to emit ONLY on state transitions (rising edge)

import os
import time
import psutil
from PySide6.QtCore import QObject, Signal, QTimer


# Resolve the drive this project lives on — works on Windows and POSIX
_THIS_DIR  = os.path.dirname(os.path.abspath(__file__))
_DRIVE     = os.path.splitdrive(_THIS_DIR)[0]
_DISK_PATH = (_DRIVE + "\\") if _DRIVE else "/"


class SystemMonitor(QObject):
    """
    Polls system metrics every INTERVAL_MS and emits:
      data_updated(dict)                 — full metrics payload
      threshold_crossed(str, str, float) — (metric_key, 'warn'|'crit', value)
    """

    data_updated      = Signal(dict)
    threshold_crossed = Signal(str, str, float)   # metric, state, value

    INTERVAL_MS = 800
    _WARN = 75.0
    _CRIT = 90.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer    = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._boot_time = psutil.boot_time()
        psutil.cpu_percent(interval=None)          # prime first call
        self._net_last  = psutil.net_io_counters()
        self._net_ts    = time.monotonic()
        # Previous metric states for edge-detection  {metric: 'ok'|'warn'|'crit'}
        self._states: dict[str, str] = {}

    # ── Public ────────────────────────────────────────────────────────
    def start(self):
        self._timer.start(self.INTERVAL_MS)

    def stop(self):
        self._timer.stop()

    # ── Internal ──────────────────────────────────────────────────────
    def _classify(self, value: float) -> str:
        if value >= self._CRIT:
            return "crit"
        if value >= self._WARN:
            return "warn"
        return "ok"

    def _check_threshold(self, key: str, value: float):
        """Emit threshold_crossed only on rising-edge state changes."""
        new_state = self._classify(value)
        old_state = self._states.get(key, "ok")
        if new_state != old_state:
            self._states[key] = new_state
            if new_state in ("warn", "crit"):
                self.threshold_crossed.emit(key, new_state, value)

    def _poll(self):
        now = time.monotonic()

        # ── CPU ───────────────────────────────────────────────
        cpu_pct  = psutil.cpu_percent(interval=None)
        freq     = psutil.cpu_freq()
        cpu_freq = freq.current if freq else 0.0

        temps = {}
        try:
            temps = psutil.sensors_temperatures() or {}
        except (AttributeError, NotImplementedError):
            pass
        cpu_temp = 0.0
        for key in ("coretemp", "cpu_thermal", "k10temp", "cpu-thermal"):
            if key in temps and temps[key]:
                cpu_temp = temps[key][0].current
                break

        # ── RAM ───────────────────────────────────────────────
        vm        = psutil.virtual_memory()
        ram_pct   = vm.percent
        ram_used  = vm.used  / (1024 ** 3)
        ram_total = vm.total / (1024 ** 3)

        # ── Disk — project drive, not always C: ───────────────
        try:
            disk     = psutil.disk_usage(_DISK_PATH)
            disk_pct = disk.percent
        except OSError:
            disk_pct = 0.0

        # ── Network ───────────────────────────────────────────
        net_now  = psutil.net_io_counters()
        dt       = max(now - self._net_ts, 0.001)
        net_up   = (net_now.bytes_sent - self._net_last.bytes_sent) / dt
        net_down = (net_now.bytes_recv - self._net_last.bytes_recv) / dt
        self._net_last = net_now
        self._net_ts   = now

        # ── Uptime ────────────────────────────────────────────
        uptime_s   = int(time.time() - self._boot_time)
        h, rem     = divmod(uptime_s, 3600)
        m, s       = divmod(rem, 60)
        uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

        payload = {
            "cpu_pct":   cpu_pct,
            "cpu_freq":  cpu_freq,
            "cpu_temp":  cpu_temp,
            "ram_pct":   ram_pct,
            "ram_used":  ram_used,
            "ram_total": ram_total,
            "disk_pct":  disk_pct,
            "net_up":    net_up,
            "net_down":  net_down,
            "uptime":    uptime_str,
        }
        self.data_updated.emit(payload)

        # ── Threshold checks ──────────────────────────────────
        self._check_threshold("cpu",  cpu_pct)
        self._check_threshold("ram",  ram_pct)
        self._check_threshold("disk", disk_pct)
