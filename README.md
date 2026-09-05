# ULTRON — AI Command Center
### Pure Holographic Orange Edition

A futuristic AI HUD command center built with **Python + PySide6**, inspired by Stark Industries / cyberpunk AI aesthetics. Every pixel is custom-painted — no standard Qt widgets, no stock dashboards.

```
╔══════════════════════════════════════════════════════╗
║              ULTRON  v2.0.0   ● SYSTEM ONLINE        ║
╠══════════╦══════════════════════════╦════════════════╣
║ SYSTEM   ║                          ║ TELEMETRY      ║
║ STATUS   ║       ◉  AI CORE         ║ CPU ████░  71% ║
║ CPU  ▓▓▓ ║    72% NEURAL ACTIVE     ║ MEM ███░░  55% ║
║ RAM  ▓▓░ ║  91% CONFIDENCE          ║ NET ██░░░  30% ║
╠══════════║                          ╠════════════════╣
║ AI LOG   ║   [SCANNING ENVIRONMENT] ║ ENVIRONMENT    ║
║ [SYS] …  ║                          ║ 23.5°C  45%RH  ║
╠══════════╩══════════════════════════╩════════════════╣
║  > ENTER COMMAND...                                  ║
╚══════════════════════════════════════════════════════╝
```

---

## Features

- **Pure Holographic Orange** color theme — glowing orange on near-black
- **Animated AI Core** — rotating rings, radar sweep, particle field, pulsing sphere
- **Real System Monitoring** — CPU, RAM, disk, network via `psutil`
- **Live Telemetry Graphs** — scrolling waveforms for CPU / memory / network / AI
- **System Log** — continuously updating event feed with boot sequence
- **Futuristic Command Console** — blinking cursor, command history (↑/↓), scrolling output
- **AI Response Engine** — responds to typed commands with simulated intelligence
- **HUD Panels** — hover glow, corner notches, glass background, collapsible

---

## Installation

### Requirements
- Python 3.10+
- Windows / macOS / Linux

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run

```bash
python main.py
```

---

## Commands

Type any of these in the console at the bottom:

| Command | Description |
|---------|-------------|
| `status` | Full system status report |
| `scan` | Quick scan |
| `system scan` | Deep full-system scan |
| `analyze network` | Network topology analysis |
| `diagnostics` | Hardware diagnostics |
| `run protocol` | Execute defense protocol |
| `help` | List all commands |
| `clear` | Clear console output |

---

## Architecture

```
Ultron ai/
├── main.py                    # Entry point — QApplication setup
├── config.py                  # Theme constants, colors, fonts, timing
│
├── services/
│   ├── system_monitor.py      # Real CPU/RAM/disk/network via psutil
│   ├── ai_engine.py           # Simulated AI state + command responses
│   └── telemetry_service.py   # Rolling history buffers for graphs
│
├── ui/
│   ├── main_window.py         # Full layout assembly + signal wiring
│   ├── ai_core.py             # Animated AI Core (QPainter)
│   ├── hud_panel.py           # Base HUD panel + MetricRow + StatusDot
│   ├── system_log.py          # Live scrolling log widget
│   ├── telemetry.py           # TelemetryGraph + EnvironmentWidget + AIActivityWidget
│   └── command_console.py     # Futuristic command console + blinking cursor input
│
├── assets/
│   ├── fonts/
│   └── sounds/
│
└── requirements.txt
```

---

## Color Palette

| Token | Hex | Role |
|-------|-----|------|
| `COLOR_PRIMARY` | `#FF6A00` | Core orange — borders, arcs, active elements |
| `COLOR_BRIGHT`  | `#FF8C00` | Hover highlights, text emphasis |
| `COLOR_GLOW`    | `#FFA040` | Bloom / glow layer |
| `COLOR_ACCENT`  | `#FFB347` | Warm accent — secondary graphs |
| `COLOR_DIM`     | `#993D00` | Inactive / secondary text |
| `COLOR_BG`      | `#050400` | Near-black background |
| `COLOR_WARN`    | `#FF2200` | Warning state |
| `COLOR_CRITICAL`| `#FF0000` | Critical alert |

---

## License

Personal use. Model licensing governed by respective providers.
