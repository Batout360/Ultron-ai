"""
ULTRON Text-to-Speech Engine
Primary: Piper TTS (offline, fast, natural voices)
Fallback 1: edge-tts (online, Microsoft voices)
Fallback 2: pyttsx3 (fully offline, basic quality)
"""

from __future__ import annotations

import asyncio
import io
import logging
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np

from config.settings import Settings, get_settings
from core.event_bus import EventBus, Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


class TTSEngine(ABC):
    """Abstract base class for TTS backends."""

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def synthesize(self, text: str) -> Optional[bytes]:
        """Synthesize text to PCM/WAV bytes."""
        ...

    @abstractmethod
    async def speak(self, text: str) -> None:
        """Synthesize and play audio immediately."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop any currently playing speech."""
        ...

    @abstractmethod
    async def close(self) -> None: ...


class PiperTTS(TTSEngine):
    """
    Piper TTS - fast, offline, high-quality neural voices.
    Requires piper-tts Python package: pip install piper-tts
    Models downloaded on first use.
    """

    def __init__(self, settings: Settings, bus: Optional[EventBus] = None) -> None:
        self._settings = settings
        self._bus = bus or get_event_bus()
        self._voice = settings.tts.voice
        self._speed = settings.tts.speed
        self._tts = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="piper-tts")
        self._audio_manager = None
        self._is_speaking = False

    async def initialize(self) -> None:
        """Initialize Piper and load the voice model."""
        logger.info("Initializing Piper TTS, voice: %s", self._voice)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, self._load_voice)
            logger.info("Piper TTS ready")
        except Exception as e:
            logger.error("Piper TTS init failed: %s", e)
            raise

    def _load_voice(self) -> None:
        try:
            from piper.voice import PiperVoice
            # Model file location: ~/.local/share/piper-tts/
            models_dir = Path.home() / ".local" / "share" / "piper-tts"
            models_dir.mkdir(parents=True, exist_ok=True)
            model_path = models_dir / f"{self._voice}.onnx"

            if not model_path.exists():
                logger.info("Downloading Piper voice model: %s", self._voice)
                self._download_voice(model_path)

            self._tts = PiperVoice.load(str(model_path))
            logger.debug("Piper voice loaded from %s", model_path)
        except ImportError:
            raise ImportError("piper-tts not installed: pip install piper-tts")

    def _download_voice(self, model_path: Path) -> None:
        """Download a Piper voice model."""
        import urllib.request
        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
        voice = self._voice
        # Parse voice name: en_US-lessac-medium -> en/en_US/lessac/medium/
        parts = voice.split("-")
        if len(parts) >= 3:
            lang_code = parts[0]  # en_US
            lang = lang_code.split("_")[0]  # en
            name = parts[1]
            quality = parts[2]
            url = f"{base_url}/{lang}/{lang_code}/{name}/{quality}/{voice}.onnx"
            config_url = f"{base_url}/{lang}/{lang_code}/{name}/{quality}/{voice}.onnx.json"
        else:
            raise ValueError(f"Cannot parse voice name: {voice}")

        logger.info("Downloading: %s", url)
        urllib.request.urlretrieve(url, str(model_path))
        urllib.request.urlretrieve(config_url, str(model_path) + ".json")

    async def synthesize(self, text: str) -> Optional[bytes]:
        """Synthesize text to WAV bytes."""
        if self._tts is None:
            return None
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: self._synthesize_sync(text),
        )

    def _synthesize_sync(self, text: str) -> bytes:
        """Synthesize in thread."""
        buf = io.BytesIO()
        with io.BytesIO() as wave_buf:
            self._tts.synthesize(text, wave_buf)
            return wave_buf.getvalue()

    async def speak(self, text: str) -> None:
        """Synthesize and play immediately."""
        if not text.strip():
            return

        self._is_speaking = True
        await self._bus.publish(Event(
            type=EventType.TTS_SPEAKING,
            data={"text": text},
        ))

        try:
            audio_bytes = await self.synthesize(text)
            if audio_bytes:
                await self._play_audio(audio_bytes)
        except Exception as e:
            logger.error("Piper speak error: %s", e)
            await self._bus.publish(Event(type=EventType.TTS_ERROR, error=e))
        finally:
            self._is_speaking = False
            await self._bus.publish(Event(type=EventType.TTS_DONE))

    async def _play_audio(self, audio_bytes: bytes) -> None:
        """Play synthesized audio via sounddevice."""
        try:
            import sounddevice as sd
            import wave
            with io.BytesIO(audio_bytes) as buf:
                with wave.open(buf, 'rb') as wav:
                    sample_rate = wav.getframerate()
                    frames = wav.readframes(wav.getnframes())
            audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: (sd.play(audio_np, samplerate=sample_rate), sd.wait()))
        except Exception as e:
            logger.error("Audio playback error: %s", e)

    async def stop(self) -> None:
        """Stop current playback."""
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        self._is_speaking = False

    async def close(self) -> None:
        self._executor.shutdown(wait=False)


class EdgeTTS(TTSEngine):
    """
    Microsoft Edge TTS via edge-tts package.
    Requires internet connection. High quality, many voices.
    Free to use.
    """

    def __init__(self, settings: Settings, bus: Optional[EventBus] = None) -> None:
        self._settings = settings
        self._bus = bus or get_event_bus()
        self._voice = settings.tts.edge_tts_voice
        self._rate = f"+{int((settings.tts.speed - 1.0) * 100)}%"
        self._is_speaking = False

    async def initialize(self) -> None:
        try:
            import edge_tts
            logger.info("Edge TTS initialized, voice: %s", self._voice)
        except ImportError:
            raise ImportError("edge-tts not installed: pip install edge-tts")

    async def synthesize(self, text: str) -> Optional[bytes]:
        import edge_tts
        try:
            communicate = edge_tts.Communicate(text, self._voice, rate=self._rate)
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            return audio_bytes
        except Exception as e:
            logger.error("EdgeTTS synthesis error: %s", e)
            return None

    async def speak(self, text: str) -> None:
        if not text.strip():
            return

        self._is_speaking = True
        await self._bus.publish(Event(type=EventType.TTS_SPEAKING, data={"text": text}))

        try:
            import edge_tts
            import sounddevice as sd

            communicate = edge_tts.Communicate(text, self._voice, rate=self._rate)
            audio_chunks = []

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])

            if audio_chunks:
                # Decode MP3 to PCM
                audio_data = b"".join(audio_chunks)
                audio_np = self._decode_mp3(audio_data)
                if audio_np is not None:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: (sd.play(audio_np, samplerate=24000), sd.wait()),
                    )
        except Exception as e:
            logger.error("EdgeTTS speak error: %s", e)
            await self._bus.publish(Event(type=EventType.TTS_ERROR, error=e))
        finally:
            self._is_speaking = False
            await self._bus.publish(Event(type=EventType.TTS_DONE))

    def _decode_mp3(self, data: bytes) -> Optional[np.ndarray]:
        """Decode MP3 bytes to float32 array using pydub or ffmpeg."""
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_mp3(io.BytesIO(data))
            seg = seg.set_frame_rate(24000).set_channels(1)
            return np.array(seg.get_array_of_samples(), dtype=np.int16).astype(np.float32) / 32768.0
        except ImportError:
            pass
        try:
            import subprocess
            result = subprocess.run(
                ["ffmpeg", "-i", "pipe:0", "-ar", "24000", "-ac", "1", "-f", "s16le", "pipe:1"],
                input=data, capture_output=True, timeout=10,
            )
            return np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as e:
            logger.error("MP3 decode failed: %s", e)
            return None

    async def stop(self) -> None:
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        self._is_speaking = False

    async def close(self) -> None:
        pass


class Pyttsx3TTS(TTSEngine):
    """
    pyttsx3 - fully offline, uses system TTS voices.
    Windows: uses SAPI5 voices. Low quality but zero dependencies.
    """

    def __init__(self, settings: Settings, bus: Optional[EventBus] = None) -> None:
        self._settings = settings
        self._bus = bus or get_event_bus()
        self._engine = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pyttsx3")
        self._is_speaking = False

    async def initialize(self) -> None:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, self._init_engine)
            logger.info("pyttsx3 TTS initialized")
        except Exception as e:
            raise ImportError(f"pyttsx3 not available: {e}")

    def _init_engine(self) -> None:
        import pyttsx3
        self._engine = pyttsx3.init()
        self._engine.setProperty('rate', self._settings.tts.pyttsx3_rate)
        self._engine.setProperty('volume', 0.9)
        # Try to find a suitable voice
        voices = self._engine.getProperty('voices')
        for voice in voices:
            if 'english' in voice.name.lower() or 'david' in voice.name.lower():
                self._engine.setProperty('voice', voice.id)
                break

    async def synthesize(self, text: str) -> Optional[bytes]:
        """pyttsx3 doesn't easily return bytes; use speak() instead."""
        return None

    async def speak(self, text: str) -> None:
        if not text.strip():
            return
        self._is_speaking = True
        await self._bus.publish(Event(type=EventType.TTS_SPEAKING, data={"text": text}))
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, self._speak_sync, text)
        except Exception as e:
            logger.error("pyttsx3 error: %s", e)
        finally:
            self._is_speaking = False
            await self._bus.publish(Event(type=EventType.TTS_DONE))

    def _speak_sync(self, text: str) -> None:
        if self._engine:
            self._engine.say(text)
            self._engine.runAndWait()

    async def stop(self) -> None:
        if self._engine:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    self._engine.stop,
                )
            except Exception:
                pass
        self._is_speaking = False

    async def close(self) -> None:
        self._executor.shutdown(wait=False)


def create_tts_engine(settings: Optional[Settings] = None, bus: Optional[EventBus] = None) -> TTSEngine:
    """Factory: create TTS engine with auto-fallback."""
    cfg = settings or get_settings()
    provider = cfg.tts.provider.lower()

    logger.info("Creating TTS engine: %s", provider)

    if provider == "piper":
        return PiperTTS(cfg, bus)
    elif provider == "edge_tts":
        return EdgeTTS(cfg, bus)
    elif provider in ("pyttsx3", "system"):
        return Pyttsx3TTS(cfg, bus)
    else:
        logger.warning("Unknown TTS provider '%s', using pyttsx3", provider)
        return Pyttsx3TTS(cfg, bus)
