"""Explicit permission requests for things pynput/sounddevice need but don't
properly request themselves.

Manually toggling Accessibility/Input Monitoring/Microphone on in System
Settings for an ad-hoc-signed app (no Apple Developer ID) can *look* granted
while the OS-level check still says no - confirmed repeatedly today, across
all three permissions, and across every rebuild (ad-hoc signatures change
per-build, invalidating prior grants). Simply opening a CGEventTap or an
audio stream doesn't reliably trigger macOS's real consent flow or register
the app in Settings at all. Calling the actual "please ask" APIs is the
correct fix: it shows a real system dialog and registers the exact right
binary identity, instead of leaving the user to hunt through Settings and
hit this same silent mismatch.
"""
import sys
import threading

_IS_MACOS = sys.platform == "darwin"


def ensure_accessibility_trust():
    """Needed for pynput's hotkey listener (even listen-only) and for
    simulating the paste keystroke. Only meaningful on macOS - Linux/X11 has
    no equivalent gate, so this is a no-op (assumed granted) elsewhere."""
    if not _IS_MACOS:
        return True

    import ApplicationServices as AS

    return AS.AXIsProcessTrustedWithOptions({AS.kAXTrustedCheckOptionPrompt: True})


def ensure_microphone_trust(timeout=15):
    """Needed for sounddevice to capture real audio instead of silent zeros.
    Requires NSMicrophoneUsageDescription to be set in the app's Info.plist -
    without it, macOS won't show the consent prompt at all. macOS-only; not
    meaningful on Linux."""
    if not _IS_MACOS:
        return True

    import AVFoundation

    AUTHORIZED = 3
    status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
        AVFoundation.AVMediaTypeAudio
    )
    if status == AUTHORIZED:
        return True

    result = {}
    done = threading.Event()

    def handler(granted):
        result["granted"] = granted
        done.set()

    AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
        AVFoundation.AVMediaTypeAudio, handler
    )
    done.wait(timeout)
    return result.get("granted", False)
