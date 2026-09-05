# services/telemetry_service.py
# Maintains rolling history buffers for animated graph widgets.

import random
import math
from collections import deque
from PySide6.QtCore import QObject, Signal, QTimer


class TelemetryService(QObject):
    """
    Receives system_monitor data and exposes fixed-length history
    deques that telemetry graph widgets can read directly.
    Emits history_updated every tick so graphs know to repaint.
    """

    history_updated = Signal()

    HISTORY_LEN = 80

    def __init__(self, parent=None):
        super().__init__(parent)

        self._cpu     = deque([0.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)
        self._ram     = deque([0.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)
        self._net_up  = deque([0.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)
        self._net_dn  = deque([0.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)
        self._ai_proc = deque([0.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)

        # Environment (simulated — no sensor access on most desktops)
        self._env_temp     = 23.5
        self._env_humidity = 45.0
        self._env_phase    = 0.0

        self._env_timer = QTimer(self)
        self._env_timer.timeout.connect(self._sim_env)
        self._env_timer.start(3000)

    # ------------------------------------------------------------------
    # Properties (read-only snapshots for widgets)
    # ------------------------------------------------------------------
    @property
    def cpu(self)     -> deque: return self._cpu
    @property
    def ram(self)     -> deque: return self._ram
    @property
    def net_up(self)  -> deque: return self._net_up
    @property
    def net_dn(self)  -> deque: return self._net_dn
    @property
    def ai_proc(self) -> deque: return self._ai_proc

    @property
    def env(self) -> dict:
        return {
            "temp":       self._env_temp,
            "humidity":   self._env_humidity,
            "pressure":   1013.2 + 2 * math.sin(self._env_phase * 0.5),
        }

    # ------------------------------------------------------------------
    def on_system_data(self, data: dict):
        """Slot — connect to SystemMonitor.data_updated."""
        self._cpu.append(data.get("cpu_pct",  0.0))
        self._ram.append(data.get("ram_pct",  0.0))

        # Scale network bytes/s to 0-100 % representation (100 Mbps = 100%)
        up_kbps  = data.get("net_up",   0.0) / 1024
        dn_kbps  = data.get("net_down", 0.0) / 1024
        self._net_up.append(min(up_kbps / 1000 * 100, 100))
        self._net_dn.append(min(dn_kbps / 1000 * 100, 100))

        self.history_updated.emit()

    def on_ai_data(self, data: dict):
        """Slot — connect to AIEngine.state_updated."""
        self._ai_proc.append(data.get("processing", 0.0))
        self.history_updated.emit()

    # ------------------------------------------------------------------
    def _sim_env(self):
        self._env_phase    += 1
        self._env_temp      = 22.0 + 3 * math.sin(self._env_phase * 0.2) + random.uniform(-0.2, 0.2)
        self._env_humidity  = 44.0 + 6 * math.sin(self._env_phase * 0.15) + random.uniform(-0.5, 0.5)
