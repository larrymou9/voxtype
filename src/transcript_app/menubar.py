"""Menu bar presence for VoxType - an icon showing idle/recording/processing
state, since the app otherwise has no window and nothing to look at."""
import rumps
from PyObjCTools import AppHelper

from . import config

_TITLES = {
    "idle": "◦ Vox",
    "recording": "● Vox",
    "processing": "… Vox",
}


class VoxTypeApp(rumps.App):
    def __init__(self):
        super().__init__("VoxType", title=_TITLES["idle"], quit_button="Quit VoxType")
        self.menu = [f"Hold {config.HOTKEY.upper()} anywhere to dictate"]

    def set_state(self, state: str) -> None:
        # on_state_change fires from the session's worker thread, but AppKit
        # (rumps' title setter included) expects UI updates on the main thread.
        AppHelper.callAfter(setattr, self, "title", _TITLES.get(state, _TITLES["idle"]))
