"""Owns the record -> transcribe -> paste lifecycle for one hotkey hold.

Pulled out of app.py so it can be unit tested with fake dependencies instead
of a real microphone, model, and global hotkey listener.
"""
import threading

from . import config
from .audio import Recorder
from .output import send_text

# Just for a diagnostic log line - a genuinely hung native call (audio/model) can't
# be force-killed from Python, so this can't un-stick it. What keeps the app usable
# is that stop/transcribe/paste run on their own disposable thread, so a stuck one
# never blocks the next recording from starting.
STUCK_WARNING_SECONDS = 30


class RecordingSession:
    def __init__(
        self,
        transcriber,
        recorder_factory=Recorder,
        send_text_fn=send_text,
        max_duration=config.MAX_RECORDING_SECONDS,
        stuck_warning_seconds=STUCK_WARNING_SECONDS,
        partial_interval=config.PARTIAL_TRANSCRIBE_INTERVAL,
        log=print,
        on_state_change=lambda state: None,
    ):
        self._transcriber = transcriber
        self._recorder_factory = recorder_factory
        self._send_text = send_text_fn
        self._max_duration = max_duration
        self._stuck_warning_seconds = stuck_warning_seconds
        self._partial_interval = partial_interval
        self._log = log
        # Called with "recording" / "processing" / "idle" - e.g. to drive a menu
        # bar icon. Defaults to a no-op so this class needs no UI to be tested.
        self._on_state_change = on_state_change

        # Guards against the real on_release AND the max-duration timer both
        # trying to finish the same recording (whichever fires first wins).
        self._lock = threading.Lock()
        self._recorder = None
        self._finished = True
        self._timer = None

        # Streaming/partial transcription: while the hotkey is held, we
        # periodically re-transcribe everything captured so far in the
        # background. On release, only the small NEW tail since the last
        # periodic check needs transcribing - release-time latency becomes
        # roughly constant (~partial_interval) instead of scaling with how
        # long the whole hold was. Every sample is transcribed exactly once,
        # either as part of a periodic check or as the final tail.
        self._partial_lock = threading.Lock()
        self._confirmed_text = ""
        self._confirmed_length = 0
        self._partial_stop = None  # threading.Event for the current hold
        # ctranslate2 uses its own internal thread pool per transcribe() call -
        # running a periodic check and the final tail transcribe at the same
        # time doesn't parallelize usefully, it just makes both slower by
        # fighting over the same CPU cores (confirmed: this measurably
        # inflated real release-to-paste latency during testing). This lock
        # ensures only one transcribe() call for this session ever runs at
        # once; the final tail naturally waits for a trailing periodic check
        # to finish, which also means it picks up that check's progress
        # instead of ignoring it.
        self._transcribe_lock = threading.Lock()

        self.last_worker = None  # exposed so tests can join() on it deterministically

    def on_press(self):
        self._log("[voxtype] recording...")
        self._on_state_change("recording")
        recorder = self._recorder_factory()  # fresh instance per hold - avoids clashing with a stuck previous one
        recorder.start()
        with self._lock:
            self._recorder = recorder
            self._finished = False
        with self._partial_lock:
            self._confirmed_text = ""
            self._confirmed_length = 0
        self._timer = threading.Timer(
            self._max_duration, self.finish, kwargs={"reason": " (max duration reached)"}
        )
        self._timer.daemon = True
        self._timer.start()

        if self._partial_interval and self._partial_interval > 0:
            self._partial_stop = threading.Event()
            self._schedule_partial_check(recorder, self._partial_stop)

    def on_release(self):
        self.finish()

    def _schedule_partial_check(self, recorder, stop_event):
        timer = threading.Timer(self._partial_interval, self._run_partial_check, args=(recorder, stop_event))
        timer.daemon = True
        timer.start()

    def _run_partial_check(self, recorder, stop_event):
        if stop_event.is_set():
            return
        audio = recorder.snapshot()
        if audio.size:
            with self._transcribe_lock:
                if stop_event.is_set():  # recheck - release may have happened while we waited for the lock
                    return
                text = self._transcriber.transcribe(audio)
                # Updated while still holding transcribe_lock, so _process()
                # can never observe a stale confirmed_length right after this
                # transcribe() call finishes - it'll see this exact update.
                with self._partial_lock:
                    self._confirmed_text = text
                    self._confirmed_length = audio.size
        if not stop_event.is_set():
            self._schedule_partial_check(recorder, stop_event)

    def finish(self, reason: str = ""):
        with self._lock:
            if self._finished:
                return
            self._finished = True
            recorder = self._recorder
        if self._timer:
            self._timer.cancel()
        if self._partial_stop:
            self._partial_stop.set()  # stops any further periodic checks from (re)scheduling

        # Runs on its own thread so a hang here (e.g. a stuck native audio/model
        # call) can't block the hotkey listener from handling the next press.
        worker = threading.Thread(target=self._process, args=(recorder, reason), daemon=True)
        worker.start()
        self.last_worker = worker
        threading.Thread(target=self._watchdog, args=(worker,), daemon=True).start()

    def _process(self, recorder, reason):
        self._on_state_change("processing")
        self._log(f"[voxtype] transcribing...{reason}")
        audio = recorder.stop()
        peak = float(abs(audio).max()) if audio.size else 0.0
        self._log(f"[voxtype] captured {audio.size} samples, peak amplitude {peak:.5f}")
        if audio.size and peak == 0.0:
            self._log(
                "[voxtype] audio is exactly silent - this usually means microphone "
                "access isn't actually granted, not that you spoke too quietly"
            )

        # Waits here if a periodic check is still mid-transcribe, rather than
        # running both at once and fighting over the same CPU cores. That
        # wait isn't wasted: the trailing check will have just updated
        # _confirmed_length, so the tail we compute below is shorter for it.
        with self._transcribe_lock:
            with self._partial_lock:
                confirmed_text = self._confirmed_text
                confirmed_length = min(self._confirmed_length, audio.size)

            if confirmed_text:
                tail_audio = audio[confirmed_length:]
                tail_text = self._transcriber.transcribe(tail_audio) if tail_audio.size else ""
                text = f"{confirmed_text} {tail_text}".strip() if tail_text else confirmed_text
                self._log(
                    f"[voxtype] streamed: {confirmed_length} samples already transcribed "
                    f"earlier, {tail_audio.size} new samples transcribed now"
                )
            else:
                # No periodic check completed yet (a short hold) - nothing to
                # build on, just transcribe the whole thing like before.
                text = self._transcriber.transcribe(audio)

        if text:
            self._log(f"[voxtype] -> {text}")
            self._send_text(text)
        else:
            self._log("[voxtype] (heard nothing)")
        self._on_state_change("idle")

    def _watchdog(self, worker):
        worker.join(timeout=self._stuck_warning_seconds)
        if worker.is_alive():
            self._log(
                f"[voxtype] warning: a previous recording is still processing after "
                f"{self._stuck_warning_seconds}s (likely stuck) - still listening for new presses"
            )
