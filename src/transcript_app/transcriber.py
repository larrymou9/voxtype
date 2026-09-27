"""Wraps faster-whisper for speech-to-text."""
import numpy as np
from faster_whisper import WhisperModel
from huggingface_hub.errors import LocalEntryNotFoundError

from . import config

# Whisper's internal speech/no-speech detection is calibrated for a healthy input
# level. Quiet mics/setups can produce real, intelligible speech that's too faint
# in absolute amplitude for that detection to trigger, so it gets dropped as
# silence. Normalizing each clip's peak up before transcribing fixes that without
# affecting clips that are already loud enough.
_TARGET_PEAK = 0.9


def _normalize(audio: np.ndarray) -> np.ndarray:
    peak = np.abs(audio).max()
    if peak == 0 or peak >= _TARGET_PEAK:
        return audio
    return audio * (_TARGET_PEAK / peak)


class Transcriber:
    def __init__(self, model_size: str = config.MODEL_SIZE, compute_type: str = config.COMPUTE_TYPE):
        print(f"[transcriber] loading model '{model_size}' ({compute_type})... (one-time, happens at startup)")
        try:
            # Once the model is cached, loading it should never touch the
            # network - by default huggingface_hub still makes a "check for
            # updates" connection on every load even when nothing needs to be
            # downloaded, which breaks the "fully local, works offline"
            # promise (confirmed via a real open connection to Hugging
            # Face's CDN while this loaded, even with the model fully
            # cached). local_files_only=True skips that entirely.
            self.model = WhisperModel(model_size, compute_type=compute_type, local_files_only=True)
        except LocalEntryNotFoundError:
            # Genuinely first run on this machine - nothing cached yet, so a
            # one-time download is unavoidable.
            print("[transcriber] model not cached yet, downloading (one time only)...")
            self.model = WhisperModel(model_size, compute_type=compute_type)
        print("[transcriber] model ready")

    def transcribe(self, audio, sample_rate: int = config.SAMPLE_RATE) -> str:
        if audio.size == 0:
            return ""
        segments, _info = self.model.transcribe(
            _normalize(audio),
            language=config.LANGUAGE,
            beam_size=5,
            vad_filter=True,
        )
        return "".join(segment.text for segment in segments).strip()
