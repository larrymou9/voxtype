"""Tests for hotkey.py, including a regression test for the canonical-key
mismatch bug found on 2026-09-19: pynput's Listener.canonical() can remap a
key (e.g. Key.space) to a different object than the one HOTKEY resolves to,
so a combo built from raw resolved keys silently never matched a real key
event. Only pure-modifier combos worked by coincidence."""
from unittest.mock import MagicMock, patch

import pytest
from pynput import keyboard

from transcript_app.hotkey import HotkeyListener, _resolve_key, resolve_hotkey_combo


def test_resolve_named_key():
    assert _resolve_key("ctrl") is keyboard.Key.ctrl
    assert _resolve_key("space") is keyboard.Key.space
    assert _resolve_key("Ctrl") is keyboard.Key.ctrl  # case-insensitive


def test_resolve_single_char_key():
    assert _resolve_key("a") == keyboard.KeyCode.from_char("a")


def test_resolve_unknown_key_raises():
    with pytest.raises(ValueError):
        _resolve_key("thisisnotakey")


def test_resolve_hotkey_combo(monkeypatch):
    monkeypatch.setattr("transcript_app.hotkey.config.HOTKEY", "ctrl+alt")
    assert resolve_hotkey_combo() == frozenset({keyboard.Key.ctrl, keyboard.Key.alt})


def _make_listener(canonical_map, on_press=None, on_release=None):
    """Builds a HotkeyListener whose inner pynput Listener.canonical() behaves
    like a given remapping, without touching any real global input hooks."""
    with patch("transcript_app.hotkey.keyboard.Listener") as MockListener:
        instance = MockListener.return_value
        instance.canonical.side_effect = lambda k: canonical_map.get(k, k)
        listener = HotkeyListener(
            on_press=on_press or MagicMock(), on_release=on_release or MagicMock()
        )
    return listener


def test_combo_is_canonicalized_to_match_live_events(monkeypatch):
    """If canonical() remaps Key.space to some other object, the stored combo
    must be canonicalized the same way, or a real space press would never
    match it - exactly what happened with the original ctrl+space hotkey."""
    monkeypatch.setattr("transcript_app.hotkey.config.HOTKEY", "ctrl+space")

    weird_space = keyboard.KeyCode(vk=49)  # stand-in for whatever canonical() maps Key.space to
    listener = _make_listener({keyboard.Key.space: weird_space})

    assert weird_space in listener._combo
    assert keyboard.Key.space not in listener._combo


def test_press_fires_only_once_combo_is_fully_held():
    listener = _make_listener({})
    listener._combo = frozenset({keyboard.Key.ctrl, keyboard.Key.alt})

    listener._handle_press(keyboard.Key.ctrl)
    listener._on_press.assert_not_called()

    listener._handle_press(keyboard.Key.alt)
    listener._on_press.assert_called_once()


def test_press_does_not_refire_while_already_active():
    listener = _make_listener({})
    listener._combo = frozenset({keyboard.Key.ctrl, keyboard.Key.alt})

    listener._handle_press(keyboard.Key.ctrl)
    listener._handle_press(keyboard.Key.alt)
    listener._handle_press(keyboard.Key.alt)  # e.g. OS key-repeat
    listener._on_press.assert_called_once()


def test_release_of_any_combo_key_fires_on_release():
    listener = _make_listener({})
    listener._combo = frozenset({keyboard.Key.ctrl, keyboard.Key.alt})
    listener._handle_press(keyboard.Key.ctrl)
    listener._handle_press(keyboard.Key.alt)

    listener._handle_release(keyboard.Key.ctrl)
    listener._on_release.assert_called_once()


def test_release_of_unrelated_key_does_not_fire():
    listener = _make_listener({})
    listener._combo = frozenset({keyboard.Key.ctrl, keyboard.Key.alt})
    listener._handle_press(keyboard.Key.ctrl)
    listener._handle_press(keyboard.Key.alt)

    listener._handle_release(keyboard.Key.shift)
    listener._on_release.assert_not_called()
