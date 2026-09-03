"""
ULTRON Status & Metrics Panel Components
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QGridLayout,
    QProgressBar
)


# ──────────────────────────────────
# Shared styles
# ──────────────────────────────────

PANEL_STYLE = """
QFrame {
    background-color: #050e18;
    border: 1px solid #0d2040;
    border-radius: 8px;
}
"""

LABEL_KEY_STYLE = "color: #4488aa; font-size: 10px; font-family: Consolas; font-weight: bold;"
LABEL_VALUE_STYLE = "color: #80c8e0; font-size: 11px; font-family: Consolas;"
LABEL_GOOD_STYLE = "color: #00ff88; font-size: 11px; font-family: Consolas;"
LABEL_WARN_STYLE = "color: #ffaa00; font-size: 11px; font-family: Consolas;"
LABEL_ERR_STYLE = "color: #ff4444; font-size: 11px; font-family: Consolas;"
LABEL_TITLE_STYLE = "color: #00d4ff; font-size: 11px; font-family: Consolas; font-weight: bold; letter-spacing: 2px;"


def make_key_value(key: str, value: str = "—") -> tuple[QLabel, QLabel]:
    k = QLabel(key + ":")
    k.setStyleSheet(LABEL_KEY_STYLE)
    v = QLabel(value)
    v.setStyleSheet(LABEL_VALUE_STYLE)
    return k, v


# ──────────────────────────────────
# Status Panel
# ──────────────────────────────────

class StatusIndicator(QWidget):
    """A single status row: dot + label + value."""

    STATUS_COLORS = {
        "ready": "#00ff88",
        "connected": "#00ff88",
        "active": "#00d4ff",
        "initializing": "#ffaa00",
        "error": "#ff4444",
        "offline": "#666666",
        "disabled": "#444444",
    }

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self._label = label
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: #666; font-size: 8px;")
        self._dot.setFixedWidth(12)

        self._key_label = QLabel(label.upper())
        self._key_label.setStyleSheet(LABEL_KEY_STYLE)
        self._key_label.setFixedWidth(100)

        self._value_label = QLabel("—")
        self._value_label.setStyleSheet(LABEL_VALUE_STYLE)

        layout.addWidget(self._dot)
        layout.addWidget(self._key_label)
        layout.addWidget(self._value_label)
        layout.addStretch()

    def update_status(self, status: str) -> None:
        status_lower = status.lower()
        for keyword, color in self.STATUS_COLORS.items():
            if keyword in status_lower:
                self._dot.setStyleSheet(f"color: {color}; font-size: 8px;")
                self._value_label.setStyleSheet(f"color: {color}; font-size: 11px; font-family: Consolas;")
                break
        else:
            self._dot.setStyleSheet("color: #888; font-size: 8px;")
            self._value_label.setStyleSheet(LABEL_VALUE_STYLE)
        self._value_label.setText(status.upper())


class StatusPanel(QFrame):
    """Shows connection and component status."""

    COMPONENTS = ["llm", "stt", "tts", "audio", "memory", "tools", "wakeword"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)
        self._indicators: dict[str, StatusIndicator] = {}
        self._setup()

    def _setup(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        title = QLabel("SYSTEM STATUS")
        title.setStyleSheet(LABEL_TITLE_STYLE)
        layout.addWidget(title)

        for comp in self.COMPONENTS:
            indicator = StatusIndicator(comp)
            self._indicators[comp] = indicator
            layout.addWidget(indicator)

    def update_component(self, component: str, status: str) -> None:
        if component in self._indicators:
            self._indicators[component].update_status(status)


# ──────────────────────────────────
# Performance / Metrics Panel
# ──────────────────────────────────

class MetricsPanel(QFrame):
    """Shows real-time performance metrics."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)
        self._labels: dict[str, QLabel] = {}
        self._bars: dict[str, QProgressBar] = {}
        self._setup()

    def _setup(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        title = QLabel("PERFORMANCE")
        title.setStyleSheet(LABEL_TITLE_STYLE)
        layout.addWidget(title)

        # Metrics with progress bars
        metrics_with_bars = [
            ("CPU", "cpu_percent"),
            ("RAM", "ram_percent"),
            ("GPU", "gpu_percent"),
            ("VRAM", "vram_percent"),
        ]
        for name, key in metrics_with_bars:
            row = QHBoxLayout()
            row.setSpacing(8)
            key_label = QLabel(f"{name}:")
            key_label.setStyleSheet(LABEL_KEY_STYLE)
            key_label.setFixedWidth(40)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet("""
                QProgressBar { background: #0a1520; border-radius: 3px; }
                QProgressBar::chunk { background: #00d4ff; border-radius: 3px; }
            """)
            val_label = QLabel("0%")
            val_label.setStyleSheet(LABEL_VALUE_STYLE)
            val_label.setFixedWidth(35)
            row.addWidget(key_label)
            row.addWidget(bar)
            row.addWidget(val_label)
            layout.addLayout(row)
            self._bars[key] = bar
            self._labels[f"{key}_val"] = val_label

        # Latency metrics
        latency_metrics = [
            ("STT", "stt_ms"),
            ("LLM", "llm_ms"),
            ("TTS", "tts_ms"),
            ("TOK/S", "tokens_sec"),
        ]
        for name, key in latency_metrics:
            row = QHBoxLayout()
            row.setSpacing(8)
            k, v = make_key_value(name)
            k.setFixedWidth(50)
            row.addWidget(k)
            row.addWidget(v)
            row.addStretch()
            layout.addLayout(row)
            self._labels[key] = v

    def update_system(self, cpu: float, ram: float, gpu: float = 0, vram: float = 0) -> None:
        def _set(key, val):
            bar = self._bars.get(key)
            lbl = self._labels.get(f"{key}_val")
            if bar:
                bar.setValue(int(val))
                # Color by threshold
                color = "#00ff88" if val < 60 else "#ffaa00" if val < 85 else "#ff4444"
                bar.setStyleSheet(f"""
                    QProgressBar {{ background: #0a1520; border-radius: 3px; }}
                    QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}
                """)
            if lbl:
                lbl.setText(f"{val:.0f}%")
        _set("cpu_percent", cpu)
        _set("ram_percent", ram)
        _set("gpu_percent", gpu)
        _set("vram_percent", vram)

    def update_latencies(self, stt_ms: float = 0, llm_ms: float = 0, tts_ms: float = 0, tokens_sec: float = 0) -> None:
        def _fmt_ms(v): return f"{v:.0f}ms" if v > 0 else "—"
        for key, val in [("stt_ms", stt_ms), ("llm_ms", llm_ms), ("tts_ms", tts_ms)]:
            if key in self._labels:
                self._labels[key].setText(_fmt_ms(val))
        if "tokens_sec" in self._labels:
            self._labels["tokens_sec"].setText(f"{tokens_sec:.1f}/s" if tokens_sec > 0 else "—")
