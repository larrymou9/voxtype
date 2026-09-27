"""Tests for the record -> transcribe -> paste session state machine.

Covers real incidents found during development:
  1. (2026-09-19) A race between the hotkey's real release and the
     max-duration safety timer could process the same recording twice.
  2. (2026-09-19) A hung recorder.stop() call (a genuine PortAudio deadlock)
     froze the whole app, because everything ran synchronously on the
     hotkey listener's own thread.
  3. (2026-09-27) Long dictations felt slow because release-time latency
     scaled with how long you'd talked - streaming/partial transcription
     fixes that by doing most of the work in the background while the
     hotkey is still held.

Most tests pass partial_interval=0 to disable the new periodic background
transcription, since it's orthogonal to what they're testing and would
otherwise race unpredictably against short-lived test assertions. The
dedicated streaming tests below cover that behavior directly, with a tiny
interval instead.
"""
import time
from unittest.mock import MagicMock

import numpy as np

from transcript_app.session import RecordingSession


def _audio(peak=0.5, n=8):
    """A minimal real audio array - session.py inspects .size and does
    abs(audio).max() on whatever recorder.stop()/snapshot() returns, so
    tests need something numpy-array-like, not a bare string."""
    arr = np.zeros(n, dtype="float32")
    if n:
        arr[0] = peak
    return arr


def _fake_recorder(audio_return, stop_side_effect=None, snapshot_return=None):
    recorder = MagicMock()
    recorder.stop.return_value = audio_return
    if stop_side_effect is not None:
        recorder.stop.side_effect = stop_side_effect
    # By default, a snapshot mid-recording looks like "nothing new yet" -
    # only the streaming tests below care about a growing snapshot.
    recorder.snapshot.return_value = (
        snapshot_return if snapshot_return is not None else np.zeros(0, dtype="float32")
    )
    return recorder


def test_full_cycle_records_transcribes_and_pastes():
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "hello world"
    audio = _audio()
    recorder = _fake_recorder(audio)
    send_text = MagicMock()

    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: recorder,
        send_text_fn=send_text,
        max_duration=999,
        partial_interval=0,
    )
    session.on_press()
    recorder.start.assert_called_once()

    session.on_release()
    session.last_worker.join(timeout=2)

    recorder.stop.assert_called_once()
    transcriber.transcribe.assert_called_once()
    assert transcriber.transcribe.call_args.args[0] is audio
    send_text.assert_called_once_with("hello world")


def test_empty_transcription_is_not_pasted():
    transcriber = MagicMock()
    transcriber.transcribe.return_value = ""
    recorder = _fake_recorder(_audio(peak=0.0))
    send_text = MagicMock()

    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: recorder,
        send_text_fn=send_text,
        max_duration=999,
        partial_interval=0,
    )
    session.on_press()
    session.on_release()
    session.last_worker.join(timeout=2)

    send_text.assert_not_called()


def test_double_finish_only_processes_once():
    """Regression test: the real on_release and the max-duration timer both
    calling finish() for the same hold must not double-process it."""
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "hi"
    recorder = _fake_recorder(_audio())
    send_text = MagicMock()

    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: recorder,
        send_text_fn=send_text,
        max_duration=999,
        partial_interval=0,
    )
    session.on_press()
    session.finish()
    session.finish()  # simulates the timer firing right after a real release
    session.last_worker.join(timeout=2)
    time.sleep(0.05)  # let a stray second worker (if the guard failed) get scheduled

    recorder.stop.assert_called_once()
    transcriber.transcribe.assert_called_once()
    send_text.assert_called_once()


def test_a_stuck_recording_does_not_block_the_next_one():
    """Regression test for the actual 2026-09-19 incident: a hung
    recorder.stop() must not prevent a brand new hold from being processed."""
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "second"

    fast_audio = _audio(peak=0.3)
    stuck_recorder = _fake_recorder(_audio(), stop_side_effect=lambda: time.sleep(5))
    fast_recorder = _fake_recorder(fast_audio)
    recorders = iter([stuck_recorder, fast_recorder])

    send_text = MagicMock()
    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: next(recorders),
        send_text_fn=send_text,
        max_duration=999,
        stuck_warning_seconds=0.1,
        partial_interval=0,
    )

    session.on_press()
    session.on_release()  # kicks off the stuck worker in the background, does not block

    session.on_press()
    session.on_release()
    session.last_worker.join(timeout=2)

    transcriber.transcribe.assert_called_once()
    assert transcriber.transcribe.call_args.args[0] is fast_audio
    send_text.assert_called_once_with("second")


def test_max_duration_timer_auto_finishes_a_long_hold():
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "auto stopped"
    recorder = _fake_recorder(_audio())
    send_text = MagicMock()

    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: recorder,
        send_text_fn=send_text,
        max_duration=0.05,
        partial_interval=0,
    )
    session.on_press()
    time.sleep(0.2)
    assert session.last_worker is not None
    session.last_worker.join(timeout=2)

    recorder.stop.assert_called_once()
    send_text.assert_called_once_with("auto stopped")


def test_release_before_any_press_does_nothing():
    transcriber = MagicMock()
    send_text = MagicMock()
    session = RecordingSession(
        transcriber,
        recorder_factory=MagicMock(),
        send_text_fn=send_text,
        max_duration=999,
        partial_interval=0,
    )
    session.on_release()
    assert session.last_worker is None
    send_text.assert_not_called()


def test_state_changes_drive_the_menu_bar_icon_in_order():
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "hi"
    recorder = _fake_recorder(_audio())
    states = []

    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: recorder,
        send_text_fn=MagicMock(),
        max_duration=999,
        partial_interval=0,
        on_state_change=states.append,
    )
    session.on_press()
    session.on_release()
    session.last_worker.join(timeout=2)

    assert states == ["recording", "processing", "idle"]


# --- Streaming / partial transcription ------------------------------------


def test_short_hold_with_no_partial_check_falls_back_to_one_full_transcribe():
    """If release happens before the first periodic check ever fires (a
    short hold, or partial_interval=0), behavior must match the pre-
    streaming app exactly: one transcribe() call on the whole recording."""
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "hello world"
    audio = _audio()
    recorder = _fake_recorder(audio)
    send_text = MagicMock()

    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: recorder,
        send_text_fn=send_text,
        max_duration=999,
        partial_interval=999,  # long enough it never fires during this test
    )
    session.on_press()
    session.on_release()
    session.last_worker.join(timeout=2)

    transcriber.transcribe.assert_called_once()
    assert transcriber.transcribe.call_args.args[0] is audio
    send_text.assert_called_once_with("hello world")


def test_a_completed_partial_check_means_release_only_transcribes_the_new_tail():
    """The core streaming behavior: once a periodic check has run, release
    should transcribe only the audio captured since that check, and paste
    the earlier result concatenated with the new tail.

    A short partial_interval can fire the periodic check more than once
    before release (timing isn't exact), so the fake keys its response off
    the audio *size* it's given rather than call order, to stay robust
    regardless of exactly how many times it fires.
    """
    transcriber = MagicMock()
    growing_snapshot = _audio(peak=0.4, n=4)  # what a mid-recording snapshot sees
    final_audio = _audio(peak=0.4, n=10)  # what's captured by the time of release
    tail_size = final_audio.size - growing_snapshot.size  # deliberately != growing_snapshot.size

    def fake_transcribe(audio, *args, **kwargs):
        if audio.size == growing_snapshot.size:
            return "hello"
        assert audio.size == tail_size, "tail call should only cover the new audio, not the whole recording"
        return "world"

    transcriber.transcribe.side_effect = fake_transcribe

    recorder = _fake_recorder(final_audio, snapshot_return=growing_snapshot)
    send_text = MagicMock()

    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: recorder,
        send_text_fn=send_text,
        max_duration=999,
        partial_interval=0.05,
    )
    session.on_press()
    time.sleep(0.2)  # let at least one periodic check complete
    session.on_release()
    session.last_worker.join(timeout=2)

    assert transcriber.transcribe.call_count >= 2  # at least one periodic check, plus the tail
    send_text.assert_called_once_with("hello world")


def test_periodic_checks_stop_after_release_and_dont_leak_into_the_next_hold():
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "ok"
    recorder = _fake_recorder(_audio(), snapshot_return=_audio(n=4))
    send_text = MagicMock()

    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: recorder,
        send_text_fn=send_text,
        max_duration=999,
        partial_interval=0.05,
    )
    session.on_press()
    session.on_release()
    session.last_worker.join(timeout=2)

    calls_at_release = transcriber.transcribe.call_count
    time.sleep(0.3)  # long enough for a leaked periodic check to have fired if the stop failed
    assert transcriber.transcribe.call_count == calls_at_release
