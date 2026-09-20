"""Tests for transcriber.py's audio normalization.

Regression coverage for the 2026-09-19 finding that real, intelligible
speech captured at a low mic level was too quiet in absolute amplitude for
Whisper's internal speech detection to trigger, even with vad_filter off.
"""
import numpy as np

from transcript_app.transcriber import _TARGET_PEAK, _normalize


def test_normalize_boosts_quiet_audio_to_target_peak():
    audio = np.array([0.0, 0.05, -0.03, 0.02], dtype="float32")
    normalized = _normalize(audio)
    assert np.isclose(np.abs(normalized).max(), _TARGET_PEAK, atol=1e-6)


def test_normalize_leaves_already_loud_audio_unchanged():
    audio = np.array([0.0, 0.95, -0.5], dtype="float32")
    normalized = _normalize(audio)
    assert np.array_equal(normalized, audio)


def test_normalize_handles_silence_without_dividing_by_zero():
    audio = np.zeros(10, dtype="float32")
    normalized = _normalize(audio)
    assert np.array_equal(normalized, audio)
