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
        log=print,
        on_state_change=lambda state: None,
    ):
        self._transcriber = transcriber
        self._recorder_factory = recorder_factory
        self._send_text = send_text_fn
        self._max_duration = max_duration
        self._stuck_warning_seconds = stuck_warning_seconds
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

        self.last_worker = None  # exposed so tests can join() on it deterministically

    def on_press(self):
        self._log("[voxtype] recording...")
        self._on_state_change("recording")
        recorder = self._recorder_factory()  # fresh instance per hold - avoids clashing with a stuck previous one
        recorder.start()
        with self._lock:
            self._recorder = recorder
            self._finished = False
        self._timer = threading.Timer(
            self._max_duration, self.finish, kwargs={"reason": " (max duration reached)"}
        )
        self._timer.daemon = True
        self._timer.start()

    def on_release(self):
        self.finish()

    def finish(self, reason: str = ""):
        with self._lock:
            if self._finished:
                return
            self._finished = True
            recorder = self._recorder
        if self._timer:
            self._timer.cancel()

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
