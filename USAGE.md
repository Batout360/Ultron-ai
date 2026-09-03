# ULTRON — User Guide

## Starting ULTRON

```bash
# Full UI with voice (recommended)
python main.py

# Text-only mode (no GUI, terminal chat)
python main.py --text

# Check that everything is working
python main.py --check
```

---

## The UI at a glance

```
┌─────────────────────────────────────────────────────────────┐
│  ⬡ ULTRON                                        ONLINE  ⚙ ✕ │
├─────────┬───────────────────────────────────┬───────────────┤
│         │                                   │  PERFORMANCE  │
│  [ORB]  │       conversation area           │  CPU:  ██░ 34%│
│         │                                   │  RAM:  ███ 48%│
│ SYSTEM  │  ULTRON: Hello! I'm ready.        │  GPU:  █░░ 12%│
│ STATUS  │                                   │  VRAM: ██░ 40%│
│         │                                   │               │
│  llm ●  │                                   │  STT:  180ms  │
│  stt ●  │                                   │  LLM:  420ms  │
│  tts ●  │                                   │  TTS:  45ms   │
│         │                                   │  TOK/S: 18/s  │
│ [VOICE] │                                   │               │
├─────────┴───────────────────────────────────┴───────────────┤
│  ⬤   Type a message or press Ctrl+Space for voice...  SEND CLR│
└─────────────────────────────────────────────────────────────┘
```

- **Orb** — animates to reflect current state (idle pulse, blue spin when thinking, green when speaking)
- **Status panel** — shows each component (llm, stt, tts, audio, memory, tools, wakeword) with a color dot
- **Performance panel** — live CPU/RAM/GPU/VRAM bars + per-component latencies, updated every 2 seconds
- **Header chip** — shows ONLINE / LISTENING / THINKING / SPEAKING / EXECUTING / ERROR

---

## Talking to ULTRON

### Option 1 — Type a message

Click the input box at the bottom (or just start typing), then press **Enter** or click **SEND**.

### Option 2 — Push-to-talk

Hold the **⬤** button in the input bar, or press **Ctrl+Space**. Speak while held; release when done. ULTRON transcribes and responds.

### Option 3 — Wake word (hands-free)

Say **"Ultron"** out loud. ULTRON will activate and listen for your command. Toggle wake-word detection with the **VOICE MODE** button in the left panel.

### Interrupting a response

Start speaking or press **Ctrl+Space** while ULTRON is talking. The current speech will stop and ULTRON will listen to you.

---

## Memory

ULTRON remembers facts across sessions using a local SQLite database.

| What you say | What happens |
|---|---|
| `Remember that my timezone is UTC+5:30` | Stores "timezone → UTC+5:30" persistently |
| `Remember I prefer dark mode` | Stores "dark mode" preference |
| `Forget my timezone` | Removes that memory |
| `What do you remember about me?` | Lists all stored memories |
| `Forget everything about me` | Clears all memories |

Memories are injected into every conversation so ULTRON always has your context.

---

## Things ULTRON can do (21 tools)

### System information

| Say | What ULTRON does |
|---|---|
| `What time is it?` | Returns the current local time |
| `What's today's date?` | Returns the current date |
| `How much RAM am I using?` | Shows RAM total / used / available |
| `What's my CPU usage?` | Shows per-core and total CPU % |
| `What's my GPU temperature?` | Reads from nvidia-smi |
| `Give me a full system report` | CPU, RAM, GPU, disk, OS info |

### Screen & clipboard

| Say | What ULTRON does |
|---|---|
| `Take a screenshot` | Saves a PNG with a timestamped filename |
| `Take a screenshot and save it to D:\pics\now.png` | Saves to that path |
| `What's in my clipboard?` | Reads and shows clipboard text |
| `Copy "Hello world" to clipboard` | Writes that text to clipboard |

### Volume control

| Say | What ULTRON does |
|---|---|
| `Set volume to 50%` | Sets master volume to 50 |
| `Turn volume up` | Increases by 10% |
| `Turn volume down 20%` | Decreases by 20% |
| `Mute` / `Unmute` | Mutes or unmutes audio |

### Web browsing

| Say | What ULTRON does |
|---|---|
| `Search for Python tutorials` | Opens Google search in your browser |
| `Search YouTube for lo-fi music` | Opens YouTube search |
| `Open github.com` | Opens the URL directly |
| `Search DuckDuckGo for privacy news` | Uses DuckDuckGo |

### Applications

ULTRON can open/close apps from a safe whitelist (Chrome, Firefox, Edge, Notepad, Notepad++, Calculator, Explorer, Paint, Task Manager, cmd, PowerShell, Terminal, VS Code, Word, Excel, PowerPoint, Spotify, VLC, Discord, Slack, Steam, OBS).

| Say | What ULTRON does |
|---|---|
| `Open Notepad` | Launches notepad.exe |
| `Open Chrome` | Launches Chrome |
| `Open VS Code` | Launches code.exe |
| `What apps are running?` | Lists all apps with visible windows |
| `Close Notepad` | Asks for confirmation, then kills process |

### File operations

Allowed read extensions: `.txt .md .py .json .yaml .yml .csv .log .ini .cfg .toml`  
Allowed write extensions: `.txt .md .json .yaml .yml .csv .log`

| Say | What ULTRON does |
|---|---|
| `Read the file D:\notes\todo.txt` | Returns file contents (up to 10,000 chars) |
| `List my D:\Projects folder` | Shows files and directories |
| `Create a file called ideas.txt` | Creates an empty file |
| `Write "Hello" to ideas.txt` | Overwrites with confirmation |
| `Rename ideas.txt to brainstorm.txt` | Renames in-place |
| `Move notes.txt to D:\archive\` | Moves with confirmation |
| `Delete old.log` | Permanently deletes with confirmation |

> Blocked paths (Windows system dirs, credential stores) are enforced regardless of what you ask.

---

## Confirmation prompts

Some actions are destructive or privileged. ULTRON will show a dialog before proceeding:

- Overwriting a file (`write_file`)
- Moving or deleting a file
- Closing an application

A popup will appear with **Yes / No** buttons. ULTRON waits for your answer before doing anything.

---

## General conversation

ULTRON is a full conversational AI, not just a command runner. You can:

- Ask questions: `Explain how async/await works in Python`
- Get help with code: `Write me a Python function to parse a CSV`
- Discuss ideas: `What are the tradeoffs between SQLite and PostgreSQL?`
- Do math, analysis, writing — anything the LLM can handle

The last 20 turns of conversation are kept in context. Older turns are summarized automatically.

---

## Text mode (no GUI)

```bash
python main.py --text
```

Same capabilities, just a terminal prompt:

```
YOU: what's the date?
ULTRON: Today is Sunday, August 23, 2026.

YOU: open notepad
ULTRON: Opening Notepad.

YOU: quit
ULTRON offline. Goodbye.
```

---

## Configuration

All settings live in `config/config.yaml`. Key ones:

| Setting | Default | What it does |
|---|---|---|
| `assistant.wake_word` | `ultron` | The word that activates voice listening |
| `assistant.wake_word_enabled` | `true` | Toggle always-on wake word |
| `llm.model` | `gpt-oss:20b` | Which Ollama model to use |
| `llm.temperature` | `0.7` | Response creativity (0 = deterministic) |
| `llm.max_tokens` | `1024` | Max response length |
| `stt.model` | `base` | Whisper model size (tiny/base/small/medium) |
| `stt.device` | `cuda` | Run STT on GPU or CPU |
| `tts.provider` | `piper` | Voice engine: `piper`, `edge_tts`, or `pyttsx3` |
| `audio.input_device` | `null` | Microphone (null = system default) |
| `performance.mode` | `balanced` | `ultra`, `balanced`, or `low_resource` |

Restart ULTRON after editing the config.

---

## Installing optional packages

Some features need extra packages:

```bash
# Voice input (faster-whisper STT) — required for microphone use
pip install faster-whisper

# Wake word / VAD
pip install webrtcvad-wheels   # Windows

# High-quality offline TTS
pip install piper-tts

# High-quality online TTS
pip install edge-tts pydub

# Volume control
pip install pycaw

# Screenshot support
pip install Pillow
```

After installing, run `python main.py --check` to confirm everything is detected.

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Send typed message |
| `Ctrl+Space` | Push-to-talk (hold to speak, release to send) |
| `CLR` button | Clear the conversation display |

---

## Troubleshooting

**ULTRON says GPT-OSS is unavailable**
- Make sure Ollama is running: `ollama serve`
- Check the model exists: `ollama list`

**Voice input not working**
- Install faster-whisper: `pip install faster-whisper`
- Check your mic in Windows Sound Settings
- Run `python main.py --check` and look for audio device

**TTS not speaking**
- The default is Piper (offline). If it fails, ULTRON auto-falls back to pyttsx3 (Windows SAPI voices, always works)
- To force pyttsx3: set `tts.provider: pyttsx3` in config.yaml

**UI won't start**
- `pip install PyQt6 qasync`
- Then run `python main.py` again

**Something still wrong**
- Check the log: `logs/ultron.log`
- Run in debug mode: `python main.py --debug`
