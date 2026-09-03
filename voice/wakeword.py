"""
ULTRON Wake Word Detector
Listens for the wake word (default: "Ultron") in low-power mode.

Primary: Pvporcupine (Picovoice - free tier, <1% CPU)
Fallback: Simple keyword STT (uses faster-whisper in a sliding window, higher CPU)
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np

from config.settings import Settings, get_settings
from core.event_bus import EventBus, Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


class WakeWordDetector(ABC):
    """Abstract base for wake word detectors."""

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def run(self) -> None:
        """Main detection loop. Should run in the background."""
        ...

    @abstractmethod
    async def stop(self) -> None: ...


class SimpleWakeWordDetector(WakeWordDetector):
    """
    Simple wake word detector using periodic STT on short audio windows.
    Less CPU-efficient than Porcupine but requires no API key.

    Strategy: Record 2s windows every 1.5s. Transcribe. Check for wake word.
    Not production-quality but functional as a fallback.
    """

    WAKE_CHECK_INTERVAL = 0.5   # seconds between checks
    WINDOW_DURATION = 2.0       # seconds of audio to analyze

    def __init__(self, settings: Settings, bus: Optional[EventBus] = None) -> None:
        self._settings = settings
        self._bus = bus or get_event_bus()
        self._wake_word = settings.assistant.wake_word.lower()
        self._running = False
        self._detected = False
        self._audio_buffer: list[np.ndarray] = []
        self._buffer_max_samples = int(settings.vad.sample_rate * self.WINDOW_DURATION)
        self._stt = None

    async def initialize(self) -> None:
        """Initialize with a tiny Whisper model for speed."""
        try:
            from voice.stt import FasterWhisperSTT
            from config.settings import Settings
            import copy

            # Use tiny model for wake word (faster)
            mini_settings = copy.deepcopy(self._settings)
            mini_settings.stt.model = "tiny"
            mini_settings.stt.beam_size = 1

            self._stt = FasterWhisperSTT(mini_settings, self._bus)
            await self._stt.initialize()
            logger.info("Simple wake word detector ready (word: '%s')", self._wake_word)
        except Exception as e:
            logger.warning("Wake word STT init failed: %s", e)

    def feed_audio(self, chunk: np.ndarray) -> None:
        """Feed audio chunk from microphone. Called from audio thread."""
        self._audio_buffer.append(chunk)
        # Keep only the most recent window
        total = sum(len(c) for c in self._audio_buffer)
        while total > self._buffer_max_samples and self._audio_buffer:
            removed = self._audio_buffer.pop(0)
            total -= len(removed)

    async def run(self) -> None:
        """Periodically check the audio buffer for the wake word."""
        self._running = True
        logger.info("Wake word detection started")

        while self._running:
            await asyncio.sleep(self.WAKE_CHECK_INTERVAL)

            if not self._audio_buffer or self._stt is None:
                continue

            try:
                audio = np.concatenate(self._audio_buffer)
                if len(audio) < self._settings.vad.sample_rate * 0.5:
                    continue

                result = await self._stt.transcribe(audio)
                if result.text and self._wake_word in result.text.lower():
                    logger.info("Wake word detected: '%s'", result.text)
                    await self._on_wake_word()

            except Exception as e:
                logger.debug("Wake word check error: %s", e)

    async def _on_wake_word(self) -> None:
        """Triggered when wake word is detected."""
        self._audio_buffer.clear()
        await self._bus.publish(Event(
            type=EventType.WAKEWORD_DETECTED,
            data={"word": self._wake_word, "provider": "simple"},
            source="WakeWord",
        ))

    async def stop(self) -> None:
        self._running = False
        logger.info("Wake word detection stopped")


class PorcupineWakeWordDetector(WakeWordDetector):
    """
    Picovoice Porcupine - ultra-low CPU wake word detection.
    Free tier requires an access key (free at picovoice.console.ai).
    Uses the built-in "computer" keyword or custom keyword files.

    Note: Porcupine doesn't have "ultron" as a built-in keyword.
    We use "computer" as the wake word or a custom .ppn file.
    """

    def __init__(self, settings: Settings, bus: Optional[EventBus] = None) -> None:
        self._settings = settings
        self._bus = bus or get_event_bus()
        self._access_key = settings.wakeword.porcupine_access_key
        self._sensitivity = settings.wakeword.sensitivity
        self._running = False
        self._porcupine = None
        self._audio_stream = None

    async def initialize(self) -> None:
        if not self._access_key:
            raise ValueError(
                "Porcupine requires an access key. Get one free at picovoice.console.ai "
                "and set it in config.yaml under wakeword.porcupine_access_key"
            )

        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        await loop.run_in_executor(executor, self._init_porcupine)

    def _init_porcupine(self) -> None:
        try:
            import pvporcupine
            self._porcupine = pvporcupine.create(
                access_key=self._access_key,
                keywords=["computer"],  # Closest built-in to "ultron"
                sensitivities=[self._sensitivity],
            )
            logger.info(
                "Porcupine initialized (keyword: 'computer', sample_rate: %d)",
                self._porcupine.sample_rate,
            )
        except ImportError:
            raise ImportError("pvporcupine not installed: pip install pvporcupine")

    async def run(self) -> None:
        """Main wake word loop - processes audio in Porcupine's native frame size."""
        if self._porcupine is None:
            return

        self._running = True
        import sounddevice as sd

        frame_length = self._porcupine.frame_length
        sample_rate = self._porcupine.sample_rate

        logger.info("Porcupine listening (frame_length=%d)", frame_length)

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype='int16',
                blocksize=frame_length,
            ) as stream:
                while self._running:
                    frames, overflowed = stream.read(frame_length)
                    if overflowed:
                        continue
                    pcm = frames[:, 0].tolist()
                    keyword_index = self._porcupine.process(pcm)
                    if keyword_index >= 0:
                        logger.info("Porcupine: wake word detected")
                        await self._bus.publish(Event(
                            type=EventType.WAKEWORD_DETECTED,
                            data={"word": "computer", "provider": "porcupine"},
                        ))
        except Exception as e:
            logger.error("Porcupine run error: %s", e)

    async def stop(self) -> None:
        self._running = False
        if self._porcupine:
            self._porcupine.delete()


def create_wakeword_detector(
    settings: Optional[Settings] = None,
    bus: Optional[EventBus] = None,
) -> WakeWordDetector:
    """Factory: create wake word detector based on config."""
    cfg = settings or get_settings()
    provider = cfg.wakeword.provider.lower()

    logger.info("Creating wake word detector: %s", provider)

    if provider == "pvporcupine" and cfg.wakeword.porcupine_access_key:
        return PorcupineWakeWordDetector(cfg, bus)
    else:
        return SimpleWakeWordDetector(cfg, bus)
