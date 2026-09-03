"""
ULTRON Speech-to-Text Engine
Primary: faster-whisper (CUDA-accelerated, runs locally on RTX 4060 Ti)
Fallback: SpeechRecognition with Google (online) or Vosk (offline)
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np

from config.settings import Settings, get_settings
from core.event_bus import EventBus, Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


class STTResult:
    def __init__(self, text: str, confidence: float = 1.0, language: str = "en", latency_ms: float = 0.0):
        self.text = text
        self.confidence = confidence
        self.language = language
        self.latency_ms = latency_ms

    def __bool__(self) -> bool:
        return bool(self.text.strip())

    def __repr__(self) -> str:
        return f"STTResult('{self.text[:60]}...', conf={self.confidence:.2f}, {self.latency_ms:.0f}ms)"


class STTEngine(ABC):
    """Abstract base class for STT backends."""

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> STTResult: ...

    @abstractmethod
    async def close(self) -> None: ...


class FasterWhisperSTT(STTEngine):
    """
    faster-whisper: runs on CUDA, ~5-10x faster than OpenAI Whisper.
    On RTX 4060 Ti with 'base' model: ~100-200ms for typical utterances.
    """

    def __init__(self, settings: Settings, bus: Optional[EventBus] = None) -> None:
        self._settings = settings
        self._bus = bus or get_event_bus()
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")
        self._model_size = settings.stt.model
        self._device = settings.stt.device
        self._compute_type = settings.stt.compute_type
        self._language = None if settings.stt.language == "auto" else settings.stt.language
        self._beam_size = settings.stt.beam_size

    async def initialize(self) -> None:
        """Load the Whisper model. Runs in a thread to avoid blocking."""
        logger.info(
            "Loading faster-whisper '%s' on %s (%s)...",
            self._model_size, self._device, self._compute_type
        )
        start = time.monotonic()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._load_model)

        elapsed = (time.monotonic() - start) * 1000
        logger.info("Whisper loaded in %.0f ms", elapsed)

    def _load_model(self) -> None:
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                num_workers=1,
                cpu_threads=4,
                download_root=str(Path.home() / ".cache" / "whisper"),
            )
        except Exception as e:
            logger.error("Failed to load faster-whisper: %s", e)
            raise

    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> STTResult:
        """Transcribe audio (runs in thread to avoid blocking the event loop)."""
        if self._model is None:
            return STTResult("", confidence=0.0, latency_ms=0)

        await self._bus.publish(Event(type=EventType.STT_STARTED))
        start = time.monotonic()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            lambda: self._transcribe_sync(audio, sample_rate),
        )

        latency = (time.monotonic() - start) * 1000
        result.latency_ms = latency

        logger.info("STT: '%s' (%.0f ms, confidence %.2f)", result.text[:80], latency, result.confidence)

        await self._bus.publish(Event(
            type=EventType.STT_RESULT,
            data={"text": result.text, "confidence": result.confidence, "latency_ms": latency},
        ))

        return result

    def _transcribe_sync(self, audio: np.ndarray, sample_rate: int) -> STTResult:
        """Actual transcription (runs in executor thread)."""
        try:
            # Ensure correct format: float32, mono, 16kHz
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            if np.max(np.abs(audio)) > 1.0:
                audio = audio / 32768.0

            # Resample if needed (faster-whisper expects 16kHz)
            if sample_rate != 16000:
                try:
                    import resampy
                    audio = resampy.resample(audio, sample_rate, 16000)
                except ImportError:
                    # Simple decimation/interpolation fallback
                    ratio = 16000 / sample_rate
                    new_len = int(len(audio) * ratio)
                    audio = np.interp(
                        np.linspace(0, len(audio) - 1, new_len),
                        np.arange(len(audio)),
                        audio,
                    ).astype(np.float32)

            segments, info = self._model.transcribe(
                audio,
                language=self._language,
                beam_size=self._beam_size,
                vad_filter=self._settings.stt.vad_filter,
                vad_parameters={"min_silence_duration_ms": 300},
                temperature=0.0,  # Greedy decoding for speed
                without_timestamps=True,
            )

            text_parts = []
            avg_confidence = 0.0
            seg_count = 0

            for segment in segments:
                text_parts.append(segment.text.strip())
                # faster-whisper provides avg_logprob per segment
                avg_confidence += getattr(segment, 'avg_logprob', -0.3)
                seg_count += 1

            text = " ".join(text_parts).strip()
            confidence = min(1.0, max(0.0, avg_confidence / max(1, seg_count) + 1.0))

            return STTResult(
                text=text,
                confidence=confidence,
                language=info.language if info else "en",
            )

        except Exception as e:
            logger.error("Whisper transcription error: %s", e, exc_info=True)
            return STTResult("", confidence=0.0)

    async def close(self) -> None:
        self._executor.shutdown(wait=False)


class VoskSTT(STTEngine):
    """
    Vosk - offline STT, lighter than Whisper, lower quality.
    Good fallback when CUDA is unavailable.
    """

    def __init__(self, settings: Settings, bus: Optional[EventBus] = None) -> None:
        self._settings = settings
        self._bus = bus or get_event_bus()
        self._model = None
        self._recognizer = None

    async def initialize(self) -> None:
        try:
            from vosk import Model, KaldiRecognizer
            import urllib.request
            model_path = Path.home() / ".cache" / "vosk" / "vosk-model-small-en-us-0.15"
            if not model_path.exists():
                logger.warning("Vosk model not found at %s", model_path)
                logger.warning("Download from https://alphacephei.com/vosk/models")
                return
            self._model = Model(str(model_path))
            self._recognizer = KaldiRecognizer(self._model, self._settings.vad.sample_rate)
            logger.info("Vosk STT initialized")
        except ImportError:
            logger.error("Vosk not installed: pip install vosk")
        except Exception as e:
            logger.error("Vosk init failed: %s", e)

    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> STTResult:
        if self._recognizer is None:
            return STTResult("", confidence=0.0)

        import json
        start = time.monotonic()
        pcm = (audio * 32768).astype(np.int16).tobytes()

        if self._recognizer.AcceptWaveform(pcm):
            result = json.loads(self._recognizer.Result())
            text = result.get("text", "")
        else:
            result = json.loads(self._recognizer.PartialResult())
            text = result.get("partial", "")

        latency = (time.monotonic() - start) * 1000
        return STTResult(text=text, confidence=0.8, latency_ms=latency)

    async def close(self) -> None:
        pass


def create_stt_engine(settings: Optional[Settings] = None, bus: Optional[EventBus] = None) -> STTEngine:
    """Factory: create the configured STT engine."""
    cfg = settings or get_settings()
    provider = cfg.stt.provider.lower()

    logger.info("Creating STT engine: %s", provider)

    if provider == "faster_whisper":
        return FasterWhisperSTT(cfg, bus)
    elif provider == "vosk":
        return VoskSTT(cfg, bus)
    else:
        logger.warning("Unknown STT provider '%s', using faster-whisper", provider)
        return FasterWhisperSTT(cfg, bus)
