# ULTRON — Local AI Assistant

A fast, private, locally-running AI assistant powered by your GPT-OSS model via Ollama.
Natural voice interaction, computer automation, and a futuristic UI — all on your hardware.

```
ULTRON ONLINE
GPT-OSS: gpt-oss:20b @ localhost:11434
GPU: NVIDIA RTX 4060 Ti (16GB)
STT: faster-whisper base (CUDA)
TTS: Piper / Edge TTS
```

---

## Features

- **100% Local AI** — powered by your `gpt-oss:20b` model via Ollama
- **Voice I/O** — faster-whisper STT (CUDA-accelerated) + Piper/Edge TTS
- **Streaming** — tokens stream to UI and audio as they're generated
- **Wake Word** — say "Ultron" to activate
- **Computer Control** — open apps, search web, manage files, control volume
- **Long-term Memory** — remember facts across sessions (SQLite)
- **Futuristic UI** — animated orb, real-time metrics, dark theme
- **Security** — LLM is sandboxed; no arbitrary code execution

---

## Requirements

| Component | Minimum | Your Hardware |
|-----------|---------|---------------|
| Python | 3.10+ | 3.14.5 ✓ |
| RAM | 8 GB | 31 GB ✓ |
| GPU VRAM | 8 GB (for gpt-oss:20b) | 16 GB ✓ |
| OS | Windows 10+ | Windows 11 ✓ |
| Ollama | 0.3.0+ | Running ✓ |

---

## Installation

### 1. Clone / download the project

```
D:\Projects\Ultron ai\
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

On Windows, if `webrtcvad` fails:
```bash
pip install webrtcvad-wheels
```

### 3. Verify Ollama is running

```bash
ollama list
# Should show: gpt-oss:20b
```

If Ollama is not running:
```bash
# Start Ollama (runs as a service automatically after install)
ollama serve
```

### 4. Run ULTRON

```bash
# Full UI mode
python main.py

# Text-only mode (no GUI, CLI chat)
python main.py --text

# System check
python main.py --check

# Debug mode
python main.py --debug
```

Or use the startup script:
```
start_ultron.bat
```

---

## GPT-OSS Setup

Your GPT-OSS model is running via Ollama. The config is pre-configured:

```yaml
llm:
  provider: gpt_oss
  endpoint: "http://localhost:11434"
  model: "gpt-oss:20b"
```

To use a different model:
```bash
ollama pull llama3.2
```
Then update `config/config.yaml`:
```yaml
llm:
  model: "llama3.2"
```

---

## Microphone Setup

1. Open `config/config.yaml`
2. Set your input device:
   ```yaml
   audio:
     input_device: null  # null = system default
   ```
3. To use a specific device, run `python main.py --check` to see device names,
   then set `input_device: "Microphone (High Definition Audio Device)"`

---

## TTS Setup

### Option A: pyttsx3 (offline, uses Windows SAPI voices — zero setup)

```yaml
tts:
  provider: pyttsx3
```

### Option B: Edge TTS (online, best quality)

```bash
pip install edge-tts pydub
```
```yaml
tts:
  provider: edge_tts
  edge_tts_voice: "en-US-GuyNeural"  # or en-US-JennyNeural
```

### Option C: Piper TTS (offline, high quality)

```bash
pip install piper-tts
```
```yaml
tts:
  provider: piper
  voice: "en_US-lessac-medium"  # Downloaded automatically on first run
```

---

## Configuration

Edit `config/config.yaml` to customize everything:

```yaml
# Main settings
assistant:
  name: ULTRON
  wake_word: "ultron"
  wake_word_enabled: true

# LLM (already configured for your setup)
llm:
  provider: gpt_oss
  endpoint: "http://localhost:11434"
  model: "gpt-oss:20b"
  temperature: 0.7
  max_tokens: 1024
  streaming: true

# STT
stt:
  model: base     # tiny | base | small | medium
  device: cuda    # cuda | cpu

# TTS
tts:
  provider: pyttsx3   # Change to piper or edge_tts

# Performance
performance:
  mode: balanced   # ultra | balanced | low_resource
```

All settings can also be overridden via environment variables:
```
ULTRON_LLM_MODEL=gpt-oss:20b
ULTRON_STT_MODEL=small
ULTRON_TTS_PROVIDER=edge_tts
```

---

## Running ULTRON

### Full UI Mode
```bash
python main.py
```
- Click **SEND** or press **Enter** to submit text
- Press **Ctrl+Space** for push-to-talk
- Say **"Ultron"** to activate with wake word
- Click the **⬤** button for push-to-talk

### Text Mode (no UI)
```bash
python main.py --text
```

### System Check
```bash
python main.py --check
```

---

## What ULTRON Can Do

### Voice Commands
- *"Ultron, what time is it?"*
- *"Open Chrome and search for today's weather"*
- *"What's my CPU usage?"*
- *"Remember that I prefer dark mode"*
- *"Take a screenshot"*

### Memory
- *"Remember that my timezone is UTC+5:30"*
- *"Forget what you know about dark mode"*
- *"What do you remember about me?"*

### Computer Control
| Command | Example |
|---------|---------|
| Open app | *"Open Notepad"* |
| Close app | *"Close Chrome"* (requires confirmation) |
| Web search | *"Search for Python tutorials"* |
| Open website | *"Open github.com"* |
| Clipboard | *"What's in my clipboard?"* |
| Volume | *"Set volume to 50%"* |
| Screenshot | *"Take a screenshot"* |
| File ops | *"Read the file notes.txt"* |
| System info | *"How much RAM am I using?"* |

---

## Troubleshooting

### ULTRON won't start
1. Check: `python main.py --check`
2. Install missing packages: `pip install -r requirements.txt`
3. Check logs: `logs/ultron.log`

### GPT-OSS not connecting
1. Verify Ollama is running: `ollama list`
2. Check endpoint: `curl http://localhost:11434/api/tags`
3. Verify model exists: `ollama pull gpt-oss:20b`

### Microphone not working
1. Test in Windows Sound Settings
2. Run `python main.py --check` to see detected devices
3. Set `audio.input_device` in config.yaml

### Whisper very slow
- Switch to `stt.device: cuda` (requires CUDA)
- Use smaller model: `stt.model: tiny`
- Check GPU is being used: `nvidia-smi`

### TTS not working
- Use the pyttsx3 fallback (always works): `tts.provider: pyttsx3`
- For Edge TTS, check internet connection

### UI not starting (PyQt6 error)
```bash
pip install PyQt6 PyQt6-Qt6 PyQt6-sip
```

### webrtcvad install fails on Windows
```bash
pip install webrtcvad-wheels
```

---

## Performance Optimization

### For maximum speed (your hardware can handle it):
```yaml
performance:
  mode: ultra

stt:
  model: base      # tiny is faster but less accurate
  device: cuda
  compute_type: float16

llm:
  max_tokens: 512  # Shorter = faster responses
```

### For lowest latency voice interaction:
- Use `stt.model: tiny` (~50ms on your RTX 4060 Ti)
- Use `tts.provider: pyttsx3` (instant, no synthesis delay)
- Set `llm.max_tokens: 256` for concise voice answers

### Expected latencies on your hardware:
| Component | Expected |
|-----------|----------|
| Wake word detection | <100ms |
| STT (base model) | 150-300ms |
| LLM first token | 300-800ms |
| TTS (pyttsx3) | <50ms |
| Total (voice→voice) | ~1-2 seconds |

---

## Security Notes

- The LLM cannot execute arbitrary code or shell commands
- File access is restricted to allowed extensions and paths
- Destructive operations (delete, overwrite) require explicit confirmation
- No data is sent to external servers (except Edge TTS if enabled)
- Conversation history is stored locally in `data/ultron.db`
- All memories can be viewed and deleted via voice commands

### What ULTRON cannot do:
- Execute shell commands (`run_shell_command` is blocked)
- Modify system registry
- Access `C:\Windows\System32` or credential stores
- Install software without confirmation
- Access files outside allowed extensions

---

## Project Structure

```
Ultron ai/
├── main.py                 # Entry point
├── requirements.txt
├── config/
│   ├── config.yaml         # Main configuration
│   └── settings.py         # Typed settings loader
├── core/
│   ├── assistant.py        # Main orchestrator
│   ├── conversation.py     # Message history
│   ├── memory.py           # Long-term memory
│   ├── event_bus.py        # Async pub/sub
│   └── state.py            # State machine
├── ai/
│   ├── llm_provider.py     # Ollama + OpenAI-compat adapters
│   ├── streaming.py        # Token→sentence buffer for TTS
│   └── prompts.py          # System prompt templates
├── voice/
│   ├── audio.py            # Microphone + speaker I/O
│   ├── vad.py              # Voice activity detection
│   ├── stt.py              # Speech-to-text (faster-whisper)
│   ├── tts.py              # Text-to-speech (Piper/Edge/pyttsx3)
│   └── wakeword.py         # Wake word detection
├── tools/
│   ├── registry.py         # Tool registration + dispatch
│   ├── system.py           # System info, clipboard, volume
│   ├── browser.py          # Web browsing
│   ├── files.py            # File operations
│   └── applications.py     # App control
├── security/
│   ├── permissions.py      # Permission levels per tool
│   └── confirmations.py    # Confirmation workflow
├── storage/
│   ├── database.py         # SQLite (aiosqlite)
│   └── memory_store.py     # Session + persistent store
├── ui/
│   ├── app.py              # Qt application + asyncio
│   ├── main_window.py      # Main window
│   ├── animations.py       # Orb widget
│   └── components/
│       ├── chat_widget.py  # Conversation display
│       └── panels.py       # Status + metrics panels
└── data/
    └── ultron.db           # SQLite database (created at runtime)
```

---

## License

This project is for personal use. Model licensing is governed by the respective model providers.
