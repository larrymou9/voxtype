"""Tests for output.py's paste/type behavior and clipboard restoration."""
from unittest.mock import patch

from transcript_app import config, output


def test_send_text_empty_is_a_noop():
    with patch("transcript_app.output._paste") as paste, patch("transcript_app.output._type") as typ:
        output.send_text("")
        paste.assert_not_called()
        typ.assert_not_called()


def test_paste_mode_copies_then_restores_previous_clipboard(monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_MODE", "paste")
    monkeypatch.setattr(output.time, "sleep", lambda s: None)  # don't actually wait in tests

    with patch("transcript_app.output.pyperclip") as clip, patch("transcript_app.output._keyboard") as kb:
        clip.paste.return_value = "what was on the clipboard before"
        output.send_text("dictated text")

        clip.copy.assert_any_call("dictated text")
        kb.pressed.assert_called_once()
        # the clipboard must end up back the way it was before we touched it
        assert clip.copy.call_args_list[-1].args[0] == "what was on the clipboard before"


def test_paste_mode_survives_unreadable_previous_clipboard(monkeypatch):
    """Some clipboard contents (e.g. non-text) make pyperclip.paste() raise -
    that must not stop the dictated text from still being pasted."""
    monkeypatch.setattr(config, "OUTPUT_MODE", "paste")
    monkeypatch.setattr(output.time, "sleep", lambda s: None)

    with patch("transcript_app.output.pyperclip") as clip, patch("transcript_app.output._keyboard") as kb:
        clip.paste.side_effect = Exception("not text")
        output.send_text("dictated text")
        clip.copy.assert_called_once_with("dictated text")
        kb.pressed.assert_called_once()


def test_type_mode_never_touches_the_clipboard(monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_MODE", "type")
    with patch("transcript_app.output.pyperclip") as clip, patch("transcript_app.output._keyboard") as kb:
        output.send_text("dictated text")
        clip.copy.assert_not_called()
        kb.type.assert_called_once_with("dictated text")
