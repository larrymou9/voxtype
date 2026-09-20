"""VoxType — hold the hotkey, speak, release, and the transcription is pasted at your cursor."""
from . import config
from .transcriber import Transcriber
from .hotkey import HotkeyListener
from .session import RecordingSession


def main() -> None:
    print("VoxType starting up...")
    print(f"Hold {config.HOTKEY.upper()} to record, release to transcribe and paste.")

    transcriber = Transcriber()  # loaded once, up front, so the first dictation isn't slow
    session = RecordingSession(transcriber)

    listener = HotkeyListener(on_press=session.on_press, on_release=session.on_release)
    listener.start()
    print("Ready.")
    listener.join()


if __name__ == "__main__":
    main()
