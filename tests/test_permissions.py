"""Tests for permissions.py, particularly the non-macOS no-op guards that
make Linux compatibility possible - macOS-only frameworks (ApplicationServices,
AVFoundation) must never even be imported when not on macOS, since they don't
exist there and pip won't have installed them (see pyproject.toml's
sys_platform == 'darwin' markers)."""
import sys
from unittest.mock import MagicMock, patch

from transcript_app import permissions


def test_accessibility_trust_is_a_noop_off_macos(monkeypatch):
    monkeypatch.setattr(permissions, "_IS_MACOS", False)
    # Poison the import so the test fails loudly if the platform guard doesn't
    # actually short-circuit before reaching `import ApplicationServices`.
    with patch.dict(sys.modules, {"ApplicationServices": None}):
        assert permissions.ensure_accessibility_trust() is True


def test_microphone_trust_is_a_noop_off_macos(monkeypatch):
    monkeypatch.setattr(permissions, "_IS_MACOS", False)
    with patch.dict(sys.modules, {"AVFoundation": None}):
        assert permissions.ensure_microphone_trust() is True


def test_accessibility_trust_calls_the_real_macos_api(monkeypatch):
    monkeypatch.setattr(permissions, "_IS_MACOS", True)
    fake_as = MagicMock()
    fake_as.kAXTrustedCheckOptionPrompt = "prompt-key"
    fake_as.AXIsProcessTrustedWithOptions.return_value = True

    with patch.dict(sys.modules, {"ApplicationServices": fake_as}):
        assert permissions.ensure_accessibility_trust() is True
    fake_as.AXIsProcessTrustedWithOptions.assert_called_once_with({"prompt-key": True})


def test_microphone_trust_skips_request_when_already_authorized(monkeypatch):
    monkeypatch.setattr(permissions, "_IS_MACOS", True)
    fake_av = MagicMock()
    fake_av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 3  # authorized

    with patch.dict(sys.modules, {"AVFoundation": fake_av}):
        assert permissions.ensure_microphone_trust() is True
    fake_av.AVCaptureDevice.requestAccessForMediaType_completionHandler_.assert_not_called()


def test_microphone_trust_requests_access_when_not_yet_determined(monkeypatch):
    monkeypatch.setattr(permissions, "_IS_MACOS", True)
    fake_av = MagicMock()
    fake_av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 0  # not determined

    def fake_request(media_type, handler):
        handler(True)  # simulate the user clicking Allow, synchronously

    fake_av.AVCaptureDevice.requestAccessForMediaType_completionHandler_.side_effect = fake_request

    with patch.dict(sys.modules, {"AVFoundation": fake_av}):
        assert permissions.ensure_microphone_trust(timeout=2) is True
    fake_av.AVCaptureDevice.requestAccessForMediaType_completionHandler_.assert_called_once()


def test_microphone_trust_times_out_to_false_if_never_answered(monkeypatch):
    monkeypatch.setattr(permissions, "_IS_MACOS", True)
    fake_av = MagicMock()
    fake_av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 0
    fake_av.AVCaptureDevice.requestAccessForMediaType_completionHandler_.side_effect = lambda *a: None

    with patch.dict(sys.modules, {"AVFoundation": fake_av}):
        assert permissions.ensure_microphone_trust(timeout=0.05) is False
