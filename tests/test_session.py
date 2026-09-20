"""Tests for the record -> transcribe -> paste session state machine.

Covers two real incidents from 2026-09-19:
  1. A race between the hotkey's real release and the max-duration safety
     timer could process the same recording twice.
  2. A hung recorder.stop() call (a genuine PortAudio deadlock) froze the
     whole app, because everything ran synchronously on the hotkey
     listener's own thread.
"""
import time
from unittest.mock import MagicMock

from transcript_app.session import RecordingSession


def _fake_recorder(audio_return, stop_side_effect=None):
    recorder = MagicMock()
    recorder.stop.return_value = audio_return
    if stop_side_effect is not None:
        recorder.stop.side_effect = stop_side_effect
    return recorder


def test_full_cycle_records_transcribes_and_pastes():
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "hello world"
    recorder = _fake_recorder("some-audio")
    send_text = MagicMock()

    session = RecordingSession(
        transcriber, recorder_factory=lambda: recorder, send_text_fn=send_text, max_duration=999
    )
    session.on_press()
    recorder.start.assert_called_once()

    session.on_release()
    session.last_worker.join(timeout=2)

    recorder.stop.assert_called_once()
    transcriber.transcribe.assert_called_once_with("some-audio")
    send_text.assert_called_once_with("hello world")


def test_empty_transcription_is_not_pasted():
    transcriber = MagicMock()
    transcriber.transcribe.return_value = ""
    recorder = _fake_recorder("silence")
    send_text = MagicMock()

    session = RecordingSession(
        transcriber, recorder_factory=lambda: recorder, send_text_fn=send_text, max_duration=999
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
    recorder = _fake_recorder("audio")
    send_text = MagicMock()

    session = RecordingSession(
        transcriber, recorder_factory=lambda: recorder, send_text_fn=send_text, max_duration=999
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

    stuck_recorder = _fake_recorder("never-returned", stop_side_effect=lambda: time.sleep(5))
    fast_recorder = _fake_recorder("fast-audio")
    recorders = iter([stuck_recorder, fast_recorder])

    send_text = MagicMock()
    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: next(recorders),
        send_text_fn=send_text,
        max_duration=999,
        stuck_warning_seconds=0.1,
    )

    session.on_press()
    session.on_release()  # kicks off the stuck worker in the background, does not block

    session.on_press()
    session.on_release()
    session.last_worker.join(timeout=2)

    transcriber.transcribe.assert_called_once_with("fast-audio")
    send_text.assert_called_once_with("second")


def test_max_duration_timer_auto_finishes_a_long_hold():
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "auto stopped"
    recorder = _fake_recorder("long-audio")
    send_text = MagicMock()

    session = RecordingSession(
        transcriber, recorder_factory=lambda: recorder, send_text_fn=send_text, max_duration=0.05
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
        transcriber, recorder_factory=MagicMock(), send_text_fn=send_text, max_duration=999
    )
    session.on_release()
    assert session.last_worker is None
    send_text.assert_not_called()


def test_state_changes_drive_the_menu_bar_icon_in_order():
    transcriber = MagicMock()
    transcriber.transcribe.return_value = "hi"
    recorder = _fake_recorder("audio")
    states = []

    session = RecordingSession(
        transcriber,
        recorder_factory=lambda: recorder,
        send_text_fn=MagicMock(),
        max_duration=999,
        on_state_change=states.append,
    )
    session.on_press()
    session.on_release()
    session.last_worker.join(timeout=2)

    assert states == ["recording", "processing", "idle"]
