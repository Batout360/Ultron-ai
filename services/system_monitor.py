# services/system_monitor.py
# Real-time system metrics via psutil

import time
import psutil
from PySide6.QtCore import QObject, Signal, QTimer


class SystemMonitor(QObject):
    """Polls system metrics every INTERVAL_MS and emits updated data."""

    data_updated = Signal(dict)

    INTERVAL_MS = 800

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._boot_time = psutil.boot_time()
        # Prime cpu_percent so first call returns a valid value
        psutil.cpu_percent(interval=None)
        self._net_last = psutil.net_io_counters()
        self._net_ts   = time.monotonic()

    # ------------------------------------------------------------------
    def start(self):
        self._timer.start(self.INTERVAL_MS)

    def stop(self):
        self._timer.stop()

    # ------------------------------------------------------------------
    def _poll(self):
        now = time.monotonic()

        # CPU
        cpu_pct = psutil.cpu_percent(interval=None)

        # RAM
        vm = psutil.virtual_memory()
        ram_pct  = vm.percent
        ram_used = vm.used  / (1024 ** 3)
        ram_total= vm.total / (1024 ** 3)

        # Disk
        disk = psutil.disk_usage("/")
        disk_pct = disk.percent

        # Network (bytes/s)
        net_now = psutil.net_io_counters()
        dt = max(now - self._net_ts, 0.001)
        net_up   = (net_now.bytes_sent - self._net_last.bytes_sent) / dt
        net_down = (net_now.bytes_recv - self._net_last.bytes_recv) / dt
        self._net_last = net_now
        self._net_ts   = now

        # CPU frequency & temperature (best-effort)
        freq = psutil.cpu_freq()
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

        # Uptime
        uptime_s = int(time.time() - self._boot_time)
        h, rem = divmod(uptime_s, 3600)
        m, s   = divmod(rem, 60)
        uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

        payload = {
            "cpu_pct":    cpu_pct,
            "cpu_freq":   cpu_freq,
            "cpu_temp":   cpu_temp,
            "ram_pct":    ram_pct,
            "ram_used":   ram_used,
            "ram_total":  ram_total,
            "disk_pct":   disk_pct,
            "net_up":     net_up,
            "net_down":   net_down,
            "uptime":     uptime_str,
        }
        self.data_updated.emit(payload)
