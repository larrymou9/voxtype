"""Microphone recording — records while the hotkey is held down."""
import threading

import numpy as np
import sounddevice as sd

from . import config


class Recorder:
    """Accumulates microphone audio into an in-memory buffer while active.

    Chunks are kept in an append-only list (not drained/removed) so
    snapshot() can peek at everything captured so far without disturbing an
    in-progress recording - needed for streaming/partial transcription.
    """

    def __init__(self, sample_rate: int = config.SAMPLE_RATE, channels: int = config.CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self._chunks = []
        self._lock = threading.Lock()
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[audio] stream status: {status}")
        with self._lock:
            self._chunks.append(indata.copy())

    def start(self) -> None:
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def snapshot(self) -> np.ndarray:
        """Everything captured so far, without stopping the stream."""
        with self._lock:
            chunks = list(self._chunks)
        if not chunks:
            return np.zeros(0, dtype="float32")
        return np.concatenate(chunks, axis=0).flatten()

    def stop(self) -> np.ndarray:
        """Stop recording and return the captured audio as a single float32 array."""
        if self._stream is None:
            return np.zeros(0, dtype="float32")
        # abort(), not stop(): stop() waits for the callback to finish draining its
        # current buffer, which can hang intermittently. We don't need that last
        # sliver of audio - abort() returns immediately with what's already captured.
        self._stream.abort()
        self._stream.close()
        self._stream = None
        return self.snapshot()
