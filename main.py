"""
ULTRON - Main Entry Point
High-performance local AI assistant powered by GPT-OSS via Ollama.

Usage:
    python main.py                    # Full UI mode
    python main.py --text             # Text-only mode (no UI, CLI chat)
    python main.py --check            # Run system check and exit
    python main.py --config PATH      # Use alternate config file
    python main.py --debug            # Enable debug logging
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# ────────────────────────────────────────────────────────────
# Set up path so all imports work regardless of working dir
# ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ────────────────────────────────────────────────────────────
# On Windows, the default console encoding (cp1252) cannot
# encode Unicode box/check characters.  Reconfigure stdout/
# stderr to UTF-8 so the system-check symbols render correctly.
# ────────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass  # Older Python or non-reconfigurable stream; fall through to ASCII fallback


def setup_logging(level: str = "INFO", log_file: Path = None) -> None:
    """Configure structured logging."""
    from logging.handlers import RotatingFileHandler

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)-25s %(message)s",
        datefmt="%H:%M:%S",
    )

    handlers: list[logging.Handler] = []

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    handlers.append(console)

    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
    )

    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("PyQt6").setLevel(logging.WARNING)


logger = logging.getLogger("ultron.main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ULTRON - Local AI Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--text", action="store_true", help="Text-only mode (CLI, no UI)")
    parser.add_argument("--check", action="store_true", help="Run system check and exit")
    parser.add_argument("--config", type=Path, help="Path to alternate config.yaml")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice I/O")
    return parser.parse_args()


async def run_system_check() -> None:
    """Run a quick system check and report component status."""
    print("\n" + "="*60)
    print("  ULTRON System Check")
    print("="*60)

    from config.settings import load_settings
    settings = load_settings()

    checks = []

    # Python version
    import platform
    py_version = sys.version.split()[0]
    checks.append(("Python", py_version, "ok"))

    # GPU
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode == 0 and r.stdout.strip():
            checks.append(("NVIDIA GPU", r.stdout.strip().replace("\n", " "), "ok"))
        else:
            checks.append(("NVIDIA GPU", "Not found", "warn"))
    except Exception:
        checks.append(("NVIDIA GPU", "nvidia-smi not found", "warn"))

    # Ollama
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.llm.endpoint}/api/tags")
            if r.status_code == 200:
                data = r.json()
                models = [m["name"] for m in data.get("models", [])]
                model_found = any(settings.llm.model in m for m in models)
                if model_found:
                    checks.append(("Ollama + GPT-OSS", f"{settings.llm.model} READY", "ok"))
                else:
                    checks.append(("Ollama", "Running, but model not found", "warn"))
            else:
                checks.append(("Ollama", "Error: " + str(r.status_code), "error"))
    except Exception as e:
        checks.append(("Ollama", f"Not reachable: {e}", "error"))

    # Packages
    packages = [
        ("PyQt6", "pip install PyQt6"),
        ("faster_whisper", "pip install faster-whisper"),
        ("sounddevice", "pip install sounddevice"),
        ("aiosqlite", "pip install aiosqlite"),
        ("pyttsx3", "pip install pyttsx3"),
        ("httpx", "pip install httpx"),
        ("psutil", "pip install psutil"),
        ("qasync", "pip install qasync"),
        ("webrtcvad", "pip install webrtcvad"),
    ]
    for pkg, install_cmd in packages:
        try:
            __import__(pkg)
            checks.append((f"pkg: {pkg}", "installed", "ok"))
        except ImportError:
            checks.append((f"pkg: {pkg}", f"MISSING - {install_cmd}", "warn"))

    # Print results — use Unicode where the console supports it, ASCII otherwise
    _enc = getattr(sys.stdout, "encoding", "ascii") or "ascii"
    _can_unicode = _enc.lower().replace("-", "") in ("utf8", "utf16", "utf32")
    ok_sym   = "\u2713" if _can_unicode else "[OK]"
    warn_sym = "\u26a0"  if _can_unicode else "[!!]"
    err_sym  = "\u2717" if _can_unicode else "[XX]"

    for name, value, status in checks:
        sym = {"ok": ok_sym, "warn": warn_sym, "error": err_sym}.get(status, "?")
        print(f"  {sym}  {name:<30} {value}")

    missing = [c for c in checks if c[2] != "ok"]
    if missing:
        print(f"\n  {len(missing)} item(s) need attention.")
        print("  Run: pip install -r requirements.txt")
    else:
        print("\n  All systems ready.")

    print("="*60 + "\n")


async def run_text_mode(settings) -> None:
    """Run ULTRON in text-only CLI mode (no GUI, no voice)."""
    from core.assistant import Assistant
    from core.event_bus import Event, EventType, get_event_bus

    print("\n" + "="*60)
    print("  ULTRON - Text Mode")
    print("  Type 'quit' or press Ctrl+C to exit")
    print("="*60 + "\n")

    assistant = Assistant(settings=settings)
    await assistant.initialize()

    bus = get_event_bus()

    # Subscribe to assistant output and print it
    async def on_complete(event):
        text = event.data.get("text", "")
        if text:
            print(f"\nULTRON: {text}\n")

    bus.subscribe(EventType.ASSISTANT_MESSAGE, on_complete)

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("YOU: ").strip()
            )
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break
            await assistant.process_text_input(user_input)
        except (KeyboardInterrupt, EOFError):
            break

    await assistant.shutdown()
    print("\nULTRON offline. Goodbye.")


def main() -> int:
    args = parse_args()

    # Load settings
    from config.settings import load_settings
    settings = load_settings(config_path=args.config)

    # Setup logging
    log_level = "DEBUG" if args.debug else settings.logging.level
    setup_logging(level=log_level, log_file=settings.log_file_path)

    logger.info("=" * 60)
    logger.info("ULTRON starting - Python %s", sys.version.split()[0])
    logger.info("Model: %s @ %s", settings.llm.model, settings.llm.endpoint)
    logger.info("=" * 60)

    # Disable voice if requested
    if args.no_voice:
        settings.assistant.wake_word_enabled = False

    # ── System check mode
    if args.check:
        asyncio.run(run_system_check())
        return 0

    # ── Text mode (no UI)
    if args.text:
        asyncio.run(run_text_mode(settings))
        return 0

    # ── Full UI mode
    try:
        from core.assistant import Assistant
        assistant = Assistant(settings=settings)

        from ui.app import run_app
        return run_app(assistant=assistant, settings=settings)

    except ImportError as e:
        logger.error("Import error: %s", e)
        logger.error("Some dependencies may be missing. Run: pip install -r requirements.txt")
        # Fall back to text mode
        logger.info("Falling back to text mode...")
        asyncio.run(run_text_mode(settings))
        return 0
    except Exception as e:
        logger.critical("Fatal error: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
