"""Sends transcribed text wherever the user's cursor currently is."""
import time

import pyperclip
from pynput.keyboard import Controller, Key

from . import config

_keyboard = Controller()


def send_text(text: str) -> None:
    if not text:
        return
    if config.OUTPUT_MODE == "paste":
        _paste(text)
    else:
        _type(text)


def _paste(text: str) -> None:
    previous_clipboard = None
    try:
        previous_clipboard = pyperclip.paste()
    except Exception:
        pass

    pyperclip.copy(text)
    time.sleep(0.05)  # give macOS a moment to register the clipboard update

    with _keyboard.pressed(Key.cmd):
        _keyboard.press("v")
        _keyboard.release("v")

    if previous_clipboard is not None:
        time.sleep(0.2)
        pyperclip.copy(previous_clipboard)


def _type(text: str) -> None:
    _keyboard.type(text)
