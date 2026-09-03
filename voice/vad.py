"""
ULTRON Voice Activity Detector
Detects when the user is speaking vs silent.
Uses webrtcvad (fast, lightweight, C library) with energy-based fallback.
"""

from __future__ import annotations

import asyncio
import collections
import logging
import time
from typing import Callable, Optional

import numpy as np

from config.settings import Settings, get_settings
from core.event_bus import EventBus, Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


class VADResult:
    def __init__(self, is_speech: bool, energy: float, confidence: float = 0.0):
        self.is_speech = is_speech
        self.energy = energy
        self.confidence = confidence


class VADDetector:
    """
    Voice Activity Detection combining WebRTC VAD + energy threshold.

    Algorithm:
    1. Frame audio into 10/20/30ms chunks
    2. Run WebRTC VAD on each frame
    3. Apply hysteresis: require N consecutive speech frames to trigger START
       and M consecutive silence frames to trigger END
    4. Emit VAD_SPEECH_START / VAD_SPEECH_END events
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()

        cfg = self._settings.vad
        self._sample_rate = cfg.sample_rate
        self._frame_duration_ms = cfg.frame_duration_ms
        self._frame_size = int(self._sample_rate * self._frame_duration_ms / 1000)
        self._energy_threshold = cfg.energy_threshold

        # State machine
        self._is_speech = False
        self._speech_start_time: Optional[float] = None

        # Hysteresis counters
        speech_frames = cfg.speech_threshold_ms // cfg.frame_duration_ms
        silence_frames = cfg.silence_threshold_ms // cfg.frame_duration_ms
        self._speech_trigger = max(1, speech_frames)
        self._silence_trigger = max(2, silence_frames)
        self._speech_counter = 0
        self._silence_counter = 0

        # Audio buffer for building frames from chunk stream
        self._audio_buffer = np.array([], dtype=np.float32)

        # WebRTC VAD (initialized in initialize())
        self._vad = None
        self._use_webrtc = False

        # Collected audio for STT (while speech is active)
        self._speech_audio: list[np.ndarray] = []
        self._on_speech_end: Optional[Callable[[np.ndarray], None]] = None

    async def initialize(self) -> None:
        """Initialize VAD backend."""
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(self._settings.vad.mode)
            self._use_webrtc = True
            logger.info("WebRTC VAD initialized (mode %d)", self._settings.vad.mode)
        except ImportError:
            logger.warning("webrtcvad not installed, using energy-based VAD")
            self._use_webrtc = False
        except Exception as e:
            logger.warning("WebRTC VAD init failed: %s, using energy VAD", e)
            self._use_webrtc = False

    def set_speech_end_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """Set callback invoked when speech ends, with the collected audio."""
        self._on_speech_end = callback

    def process_chunk(self, audio_chunk: np.ndarray) -> None:
        """
        Process an audio chunk from the microphone stream.
        Accumulates frames and runs VAD on each complete frame.
        Called from the audio callback thread - must be fast.
        """
        self._audio_buffer = np.concatenate([self._audio_buffer, audio_chunk])

        while len(self._audio_buffer) >= self._frame_size:
            frame = self._audio_buffer[:self._frame_size]
            self._audio_buffer = self._audio_buffer[self._frame_size:]
            self._process_frame(frame)

    def _process_frame(self, frame: np.ndarray) -> None:
        """Process a single VAD frame."""
        energy = float(np.sqrt(np.mean(frame ** 2)) * 32768)
        is_speech = self._detect_speech(frame, energy)

        if is_speech:
            if self._is_speech:
                # Collect audio during speech
                self._speech_audio.append(frame.copy())
                self._silence_counter = 0
            else:
                self._speech_counter += 1
                self._speech_audio.append(frame.copy())
                if self._speech_counter >= self._speech_trigger:
                    self._on_speech_start()
        else:
            if self._is_speech:
                self._silence_counter += 1
                self._speech_audio.append(frame.copy())  # Include trailing silence
                if self._silence_counter >= self._silence_trigger:
                    self._on_speech_end_detected()
            else:
                self._speech_counter = max(0, self._speech_counter - 1)
                if self._speech_audio:
                    self._speech_audio.clear()

    def _detect_speech(self, frame: np.ndarray, energy: float) -> bool:
        """Determine if the frame contains speech."""
        if energy < self._energy_threshold:
            return False  # Definitely silence

        if self._use_webrtc and self._vad is not None:
            try:
                # WebRTC VAD expects 16-bit PCM bytes
                pcm = (frame * 32768).astype(np.int16).tobytes()
                return self._vad.is_speech(pcm, self._sample_rate)
            except Exception:
                pass

        # Fallback: energy threshold only
        return energy > self._energy_threshold

    def _on_speech_start(self) -> None:
        """Called when speech onset is confirmed."""
        self._is_speech = True
        self._speech_start_time = time.monotonic()
        self._speech_counter = 0
        logger.debug("VAD: speech started")
        self._bus.publish_sync(Event(
            type=EventType.VAD_SPEECH_START,
            source="VAD",
        ))

    def _on_speech_end_detected(self) -> None:
        """Called when sufficient silence follows speech."""
        if not self._is_speech:
            return

        duration_ms = (time.monotonic() - (self._speech_start_time or 0)) * 1000
        audio_data = np.concatenate(self._speech_audio) if self._speech_audio else np.array([])

        self._is_speech = False
        self._silence_counter = 0
        self._speech_counter = 0
        self._speech_audio = []
        self._speech_start_time = None

        logger.debug("VAD: speech ended (%.0f ms, %d samples)", duration_ms, len(audio_data))

        self._bus.publish_sync(Event(
            type=EventType.VAD_SPEECH_END,
            data={"duration_ms": duration_ms, "sample_count": len(audio_data)},
            source="VAD",
        ))

        # Deliver audio to STT
        if self._on_speech_end and len(audio_data) > 0:
            self._on_speech_end(audio_data)

    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speech = False
        self._speech_counter = 0
        self._silence_counter = 0
        self._speech_audio = []
        self._audio_buffer = np.array([], dtype=np.float32)

    @property
    def is_speech_active(self) -> bool:
        return self._is_speech
