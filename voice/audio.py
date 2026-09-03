"""
ULTRON Audio Manager
Manages microphone input and speaker output using sounddevice.
Uses WASAPI on Windows for low latency.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import wave
from pathlib import Path
from typing import Optional, Callable

import numpy as np

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class AudioDevice:
    """Info about an audio device."""
    def __init__(self, index: int, name: str, channels: int, sample_rate: float, is_input: bool):
        self.index = index
        self.name = name
        self.channels = channels
        self.sample_rate = sample_rate
        self.is_input = is_input

    def __repr__(self) -> str:
        kind = "input" if self.is_input else "output"
        return f"AudioDevice({self.index}: {self.name} [{kind}])"


class AudioManager:
    """
    Handles audio I/O.
    - Lists available devices
    - Captures microphone audio in chunks
    - Plays audio files / PCM bytes
    - Manages audio state
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._input_stream = None
        self._output_stream = None
        self._is_recording = False
        self._audio_callback: Optional[Callable[[np.ndarray], None]] = None
        self._playback_queue: asyncio.Queue = asyncio.Queue()
        self._sd = None  # sounddevice module (lazy loaded)
        self._input_devices: list[AudioDevice] = []
        self._output_devices: list[AudioDevice] = []
        self._selected_input: Optional[AudioDevice] = None
        self._selected_output: Optional[AudioDevice] = None

    def _import_sounddevice(self):
        if self._sd is None:
            import sounddevice as sd
            self._sd = sd
        return self._sd

    async def initialize(self) -> None:
        """Initialize audio, enumerate devices, select default devices."""
        try:
            sd = self._import_sounddevice()
            self._enumerate_devices(sd)
            self._select_devices()
            logger.info(
                "Audio initialized. Input: %s | Output: %s",
                self._selected_input.name if self._selected_input else "none",
                self._selected_output.name if self._selected_output else "none",
            )
        except ImportError:
            logger.error("sounddevice not installed. Run: pip install sounddevice")
            raise
        except Exception as e:
            logger.error("Audio initialization failed: %s", e)
            raise

    def _enumerate_devices(self, sd) -> None:
        """List all available audio devices."""
        self._input_devices = []
        self._output_devices = []
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    self._input_devices.append(AudioDevice(
                        index=i,
                        name=dev['name'],
                        channels=dev['max_input_channels'],
                        sample_rate=dev['default_samplerate'],
                        is_input=True,
                    ))
                if dev['max_output_channels'] > 0:
                    self._output_devices.append(AudioDevice(
                        index=i,
                        name=dev['name'],
                        channels=dev['max_output_channels'],
                        sample_rate=dev['default_samplerate'],
                        is_input=False,
                    ))

            logger.debug("Input devices: %s", [d.name for d in self._input_devices])
            logger.debug("Output devices: %s", [d.name for d in self._output_devices])
        except Exception as e:
            logger.error("Device enumeration failed: %s", e)

    def _select_devices(self) -> None:
        """Select input/output devices from config or system defaults."""
        cfg_input = self._settings.audio.input_device
        cfg_output = self._settings.audio.output_device

        if cfg_input is not None:
            self._selected_input = self._find_device(cfg_input, self._input_devices)
        if self._selected_input is None and self._input_devices:
            # Use system default
            self._selected_input = self._input_devices[0]

        if cfg_output is not None:
            self._selected_output = self._find_device(cfg_output, self._output_devices)
        if self._selected_output is None and self._output_devices:
            self._selected_output = self._output_devices[0]

    def _find_device(
        self,
        identifier: int | str,
        devices: list[AudioDevice],
    ) -> Optional[AudioDevice]:
        """Find a device by index or name substring."""
        if isinstance(identifier, int):
            return next((d for d in devices if d.index == identifier), None)
        return next(
            (d for d in devices if identifier.lower() in d.name.lower()),
            None,
        )

    def start_recording(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        Start capturing microphone audio.
        callback receives numpy float32 arrays at the configured sample rate.
        """
        if self._is_recording:
            return

        sd = self._import_sounddevice()
        self._audio_callback = callback
        sample_rate = self._settings.audio.sample_rate
        chunk_size = self._settings.audio.chunk_size
        device_idx = self._selected_input.index if self._selected_input else None

        def _stream_callback(indata, frames, time_info, status):
            if status:
                logger.debug("Audio stream status: %s", status)
            if self._audio_callback:
                # Copy to avoid race; flatten to 1D mono
                audio_chunk = indata[:, 0].copy()
                self._audio_callback(audio_chunk)

        try:
            self._input_stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype='float32',
                blocksize=chunk_size,
                device=device_idx,
                callback=_stream_callback,
            )
            self._input_stream.start()
            self._is_recording = True
            logger.info("Recording started (device: %s)", self._selected_input.name if self._selected_input else "default")
        except Exception as e:
            logger.error("Failed to start recording: %s", e)
            raise

    def stop_recording(self) -> None:
        """Stop the microphone stream."""
        if self._input_stream:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception as e:
                logger.debug("Stream close warning: %s", e)
            self._input_stream = None
        self._is_recording = False
        logger.info("Recording stopped")

    def play_audio_bytes(self, audio_bytes: bytes, sample_rate: int = 22050) -> None:
        """
        Play raw PCM audio bytes (blocking in a thread).
        Used for TTS output.
        """
        def _play():
            try:
                sd = self._import_sounddevice()
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                device_idx = self._selected_output.index if self._selected_output else None
                sd.play(audio_np, samplerate=sample_rate, device=device_idx)
                sd.wait()
            except Exception as e:
                logger.error("Audio playback error: %s", e)

        thread = threading.Thread(target=_play, daemon=True)
        thread.start()
        return thread

    def play_wav_file(self, path: str | Path) -> None:
        """Play a WAV file (for activation sounds etc.)."""
        path = Path(path)
        if not path.exists():
            logger.debug("Sound file not found: %s", path)
            return

        def _play():
            try:
                sd = self._import_sounddevice()
                with wave.open(str(path), 'rb') as wav_file:
                    sample_rate = wav_file.getframerate()
                    frames = wav_file.readframes(wav_file.getnframes())
                    audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    device_idx = self._selected_output.index if self._selected_output else None
                    sd.play(audio_np, samplerate=sample_rate, device=device_idx)
                    sd.wait()
            except Exception as e:
                logger.debug("WAV playback error: %s", e)

        threading.Thread(target=_play, daemon=True).start()

    def stop_playback(self) -> None:
        """Immediately stop any ongoing audio playback."""
        try:
            sd = self._import_sounddevice()
            sd.stop()
        except Exception:
            pass

    async def stop(self) -> None:
        """Cleanup: stop all streams."""
        self.stop_recording()
        self.stop_playback()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def input_devices(self) -> list[AudioDevice]:
        return list(self._input_devices)

    @property
    def output_devices(self) -> list[AudioDevice]:
        return list(self._output_devices)

    @property
    def selected_input(self) -> Optional[AudioDevice]:
        return self._selected_input

    @property
    def selected_output(self) -> Optional[AudioDevice]:
        return self._selected_output
