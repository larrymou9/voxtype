"""VoxType — hold the hotkey, speak, release, and the transcription is pasted at your cursor."""
import sys

from . import config
from .transcriber import Transcriber
from .hotkey import HotkeyListener
from .permissions import ensure_microphone_trust
from .session import RecordingSession

IS_MACOS = sys.platform == "darwin"


def main() -> None:
    print("VoxType starting up...")
    print(f"Hold {config.HOTKEY.upper()} to record, release to transcribe and paste.")

    if not ensure_microphone_trust():
        print(
            "[voxtype] Microphone permission needed - a system dialog should have "
            "appeared. Allow it, then restart VoxType."
        )

    # menubar.py imports rumps, which is macOS-only (built on Cocoa) - it won't
    # even install on Linux. Import it lazily, only where it can actually work,
    # and fall back to a plain headless loop (like this app's original form)
    # everywhere else.
    menu_app = None
    on_state_change = lambda state: None  # noqa: E731
    if IS_MACOS:
        from .menubar import VoxTypeApp

        menu_app = VoxTypeApp()
        on_state_change = menu_app.set_state
    else:
        print("[voxtype] No menu bar on this platform - running headless.")

    transcriber = Transcriber()  # loaded once, up front, so the first dictation isn't slow
    session = RecordingSession(transcriber, on_state_change=on_state_change)

    listener = HotkeyListener(on_press=session.on_press, on_release=session.on_release)
    listener.start()
    print("Ready.")

    if menu_app is not None:
        menu_app.run()  # blocks - AppKit's run loop, also drives the menu bar icon
    else:
        listener.join()  # blocks - nothing else needs a run loop here


if __name__ == "__main__":
    main()
