"""Microphone recording — records while the hotkey is held down."""
import queue

import numpy as np
import sounddevice as sd

from . import config


class Recorder:
    """Accumulates microphone audio into an in-memory buffer while active."""

    def __init__(self, sample_rate: int = config.SAMPLE_RATE, channels: int = config.CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self._queue = queue.Queue()
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[audio] stream status: {status}")
        self._queue.put(indata.copy())

    def start(self) -> None:
        self._queue = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

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

        chunks = []
        while not self._queue.empty():
            chunks.append(self._queue.get())
        if not chunks:
            return np.zeros(0, dtype="float32")
        return np.concatenate(chunks, axis=0).flatten()
