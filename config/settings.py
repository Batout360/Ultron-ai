"""
ULTRON Configuration Manager
Loads, validates, and provides typed access to config.yaml settings.
Supports environment variable overrides for any setting.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# Project root - two levels up from this file
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"


@dataclass
class AssistantConfig:
    name: str = "ULTRON"
    wake_word: str = "ultron"
    wake_word_enabled: bool = True
    push_to_talk_key: str = "ctrl+space"
    personality: str = "confident"
    voice_response_max_words: int = 80
    interrupt_on_speech: bool = True


@dataclass
class LLMConfig:
    provider: str = "gpt_oss"
    endpoint: str = "http://localhost:11434"
    model: str = "gpt-oss:20b"
    temperature: float = 0.7
    max_tokens: int = 1024
    context_size: int = 8192
    streaming: bool = True
    timeout: int = 60
    retry_attempts: int = 2
    retry_delay: float = 1.0


@dataclass
class STTConfig:
    provider: str = "faster_whisper"
    model: str = "base"
    language: str = "auto"
    device: str = "auto"
    compute_type: str = "float16"
    beam_size: int = 5
    vad_filter: bool = True
    chunk_length_s: int = 30


@dataclass
class VADConfig:
    mode: int = 2
    frame_duration_ms: int = 30
    sample_rate: int = 16000
    silence_threshold_ms: int = 800
    speech_threshold_ms: int = 200
    energy_threshold: int = 300


@dataclass
class TTSConfig:
    provider: str = "piper"
    voice: str = "en_US-lessac-medium"
    speed: float = 1.05
    pitch: int = 0
    edge_tts_voice: str = "en-US-GuyNeural"
    pyttsx3_rate: int = 185
    streaming: bool = True


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    input_device: Optional[int | str] = None
    output_device: Optional[int | str] = None
    activation_sound: bool = True
    activation_sound_file: str = "assets/sounds/activate.wav"


@dataclass
class WakeWordConfig:
    provider: str = "simple"
    sensitivity: float = 0.6
    porcupine_keyword: str = "ultron"
    porcupine_access_key: str = ""


@dataclass
class PerformanceConfig:
    mode: str = "balanced"
    max_workers: int = 4
    ui_update_interval_ms: int = 50
    reduce_effects_on_load: bool = True
    cpu_load_threshold: int = 80
    gpu_load_threshold: int = 90


@dataclass
class MemoryConfig:
    short_term_max_turns: int = 20
    long_term_enabled: bool = True
    auto_summarize: bool = True
    db_path: str = "data/ultron.db"


@dataclass
class SecurityConfig:
    require_confirmation_destructive: bool = True
    require_confirmation_privileged: bool = True
    allowed_file_extensions: dict = field(default_factory=lambda: {
        "read": [".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv", ".log"],
        "write": [".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".log"]
    })
    max_file_size_mb: int = 50
    blocked_paths: list[str] = field(default_factory=lambda: [
        "C:\\Windows\\System32",
        "C:\\Windows\\SysWOW64",
    ])


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/ultron.log"
    max_file_size_mb: int = 10
    backup_count: int = 3
    console: bool = True
    structured: bool = True


@dataclass
class UIConfig:
    theme: str = "dark"
    accent_color: str = "#00d4ff"
    secondary_color: str = "#0066ff"
    background_color: str = "#050a0f"
    animation_fps: int = 60
    window_width: int = 1200
    window_height: int = 800
    always_on_top: bool = False
    start_minimized: bool = False
    system_tray: bool = True
    font_family: str = "Segoe UI"
    font_size: int = 13
    show_performance_panel: bool = True
    show_status_bar: bool = True


@dataclass
class Settings:
    """Root settings object. All modules receive a reference to this."""
    assistant: AssistantConfig = field(default_factory=AssistantConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    wakeword: WakeWordConfig = field(default_factory=WakeWordConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    # Resolved absolute path to the DB
    @property
    def db_path(self) -> Path:
        p = Path(self.memory.db_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    @property
    def log_file_path(self) -> Path:
        p = Path(self.logging.file)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p


def _apply_dict_to_dataclass(instance: Any, data: dict) -> None:
    """Recursively update a dataclass instance from a dict."""
    for key, value in data.items():
        if hasattr(instance, key):
            attr = getattr(instance, key)
            if hasattr(attr, '__dataclass_fields__') and isinstance(value, dict):
                _apply_dict_to_dataclass(attr, value)
            else:
                setattr(instance, key, value)


def _apply_env_overrides(settings: Settings) -> None:
    """
    Allow environment variable overrides.
    E.g. ULTRON_LLM_ENDPOINT=http://localhost:1234
         ULTRON_STT_MODEL=small
    """
    prefix = "ULTRON_"
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        parts = env_key[len(prefix):].lower().split("_", 1)
        if len(parts) != 2:
            continue
        section, key = parts
        section_obj = getattr(settings, section, None)
        if section_obj is not None and hasattr(section_obj, key):
            current = getattr(section_obj, key)
            try:
                if isinstance(current, bool):
                    setattr(section_obj, key, env_val.lower() in ("true", "1", "yes"))
                elif isinstance(current, int):
                    setattr(section_obj, key, int(env_val))
                elif isinstance(current, float):
                    setattr(section_obj, key, float(env_val))
                else:
                    setattr(section_obj, key, env_val)
                logger.debug("ENV override: %s.%s = %s", section, key, env_val)
            except (ValueError, TypeError) as e:
                logger.warning("Could not apply env override %s: %s", env_key, e)


def load_settings(config_path: Optional[Path] = None) -> Settings:
    """
    Load settings from config.yaml, then apply environment variable overrides.
    Falls back to defaults if file is missing or malformed.
    """
    settings = Settings()
    path = config_path or CONFIG_FILE

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            # The YAML key 'A:' should map to 'assistant'
            # Handle both 'A' and 'assistant' keys
            if "A" in data and "assistant" not in data:
                data["assistant"] = data.pop("A")

            for section_name, section_data in data.items():
                section_obj = getattr(settings, section_name, None)
                if section_obj is not None and isinstance(section_data, dict):
                    _apply_dict_to_dataclass(section_obj, section_data)
                elif section_obj is None:
                    logger.debug("Unknown config section: %s", section_name)

            logger.debug("Configuration loaded from %s", path)
        except yaml.YAMLError as e:
            logger.error("YAML parse error in config file: %s. Using defaults.", e)
        except OSError as e:
            logger.error("Could not read config file: %s. Using defaults.", e)
    else:
        logger.warning("Config file not found at %s. Using defaults.", path)

    _apply_env_overrides(settings)

    # Auto-detect STT device if set to 'auto'
    if settings.stt.device == "auto":
        try:
            import torch
            settings.stt.device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            settings.stt.device = "cpu"
        logger.debug("STT device auto-detected: %s", settings.stt.device)

    # Ensure directories exist
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.log_file_path.parent.mkdir(parents=True, exist_ok=True)

    return settings


# Module-level singleton loaded on first import
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the global settings singleton."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reload_settings() -> Settings:
    """Force-reload settings from disk."""
    global _settings
    _settings = load_settings()
    return _settings
