"""VoxType — hold the hotkey, speak, release, and the transcription is pasted at your cursor."""
import threading

from . import config
from .audio import Recorder
from .transcriber import Transcriber
from .hotkey import HotkeyListener
from .output import send_text


# Just for a diagnostic log line - a genuinely hung native call (audio/model) can't
# be force-killed from Python, so this can't un-stick it. What keeps the app usable
# is that stop/transcribe/paste run on their own disposable thread (see finish()),
# so a stuck one never blocks the next recording from starting.
STUCK_WARNING_SECONDS = 30


def main() -> None:
    print("VoxType starting up...")
    print(f"Hold {config.HOTKEY.upper()} to record, release to transcribe and paste.")

    transcriber = Transcriber()  # loaded once, up front, so the first dictation isn't slow

    # Guards against the hotkey's real on_release AND the max-duration timer both
    # trying to finish the same recording (whichever fires first wins).
    lock = threading.Lock()
    state = {"recorder": None, "finished": True, "timer": None}

    def process(recorder, reason):
        print(f"[voxtype] transcribing...{reason}")
        audio = recorder.stop()
        text = transcriber.transcribe(audio)
        if text:
            print(f"[voxtype] -> {text}")
            send_text(text)
        else:
            print("[voxtype] (heard nothing)")

    def watchdog(worker):
        worker.join(timeout=STUCK_WARNING_SECONDS)
        if worker.is_alive():
            print(
                f"[voxtype] warning: a previous recording is still processing after "
                f"{STUCK_WARNING_SECONDS}s (likely stuck) - still listening for new presses"
            )

    def finish(reason: str = ""):
        with lock:
            if state["finished"]:
                return
            state["finished"] = True
            recorder = state["recorder"]
        if state["timer"]:
            state["timer"].cancel()

        # Runs on its own thread so a hang here (e.g. today's stuck native audio call)
        # can't block the hotkey listener from handling the next press.
        worker = threading.Thread(target=process, args=(recorder, reason), daemon=True)
        worker.start()
        threading.Thread(target=watchdog, args=(worker,), daemon=True).start()

    def on_press():
        print("[voxtype] recording...")
        recorder = Recorder()  # fresh instance per hold - avoids clashing with a stuck previous one
        recorder.start()
        with lock:
            state["recorder"] = recorder
            state["finished"] = False
        state["timer"] = threading.Timer(config.MAX_RECORDING_SECONDS, finish, kwargs={"reason": " (max duration reached)"})
        state["timer"].daemon = True
        state["timer"].start()

    def on_release():
        finish()

    listener = HotkeyListener(on_press=on_press, on_release=on_release)
    listener.start()
    print("Ready.")
    listener.join()


if __name__ == "__main__":
    main()
