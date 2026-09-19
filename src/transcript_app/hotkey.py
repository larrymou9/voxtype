"""Global hold-to-record hotkey listener — supports single keys or modifier+key combos."""
from pynput import keyboard

from . import config

_NAMED_KEYS = {
    "space": keyboard.Key.space,
    "ctrl": keyboard.Key.ctrl,
    "control": keyboard.Key.ctrl,
    "cmd": keyboard.Key.cmd,
    "command": keyboard.Key.cmd,
    "alt": keyboard.Key.alt,
    "option": keyboard.Key.alt,
    "shift": keyboard.Key.shift,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
}


def _resolve_key(name: str):
    name = name.strip().lower()
    if name in _NAMED_KEYS:
        return _NAMED_KEYS[name]
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unrecognized key '{name}' in HOTKEY. Add it to hotkey._NAMED_KEYS.")


def resolve_hotkey_combo():
    """Parses config.HOTKEY (e.g. 'ctrl+space' or 'f5') into the set of keys required together."""
    parts = config.HOTKEY.split("+")
    return frozenset(_resolve_key(part) for part in parts)


class HotkeyListener:
    """
    Calls on_press once every key in the combo is held down together,
    and on_release as soon as any one of them comes back up.
    """

    def __init__(self, on_press, on_release):
        self._on_press = on_press
        self._on_release = on_release
        self._held = set()
        self._active = False
        self._listener = keyboard.Listener(
            on_press=self._handle_press, on_release=self._handle_release
        )
        # canonical() can remap a key to a different object than the raw Key/KeyCode
        # it started as (e.g. Key.space -> a plain KeyCode) - canonicalize the combo
        # itself here so it matches what _handle_press/_handle_release put in _held.
        self._combo = frozenset(self._canonical(k) for k in resolve_hotkey_combo())

    def _canonical(self, key):
        # Normalizes left/right variants (e.g. ctrl_l / ctrl_r) to the generic key,
        # so "ctrl+space" matches either physical Control key.
        return self._listener.canonical(key)

    def _handle_press(self, key):
        key = self._canonical(key)
        self._held.add(key)
        if not self._active and self._combo.issubset(self._held):
            self._active = True
            self._on_press()

    def _handle_release(self, key):
        key = self._canonical(key)
        self._held.discard(key)
        if self._active and not self._combo.issubset(self._held):
            self._active = False
            self._on_release()

    def start(self):
        self._listener.start()

    def join(self):
        self._listener.join()
