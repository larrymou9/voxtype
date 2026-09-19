"""Configuration constants for VoxType."""

# Hotkey used to trigger recording (press-and-hold to record, release to transcribe).
# Format: "+"-joined key names, e.g. "ctrl+alt", "cmd+shift", or a single key like "f5".
# Prefer combos made ENTIRELY of modifier keys (ctrl/alt/cmd/shift) with no other key.
# Our hotkey listener only watches key events, it doesn't swallow them - the physical
# keys you hold still reach whatever app has focus. Modifier keys don't insert text on
# their own, so they're silently harmless; a non-modifier key (space, a letter, ...)
# WILL leak through and get typed/repeated into the focused text field while held.
# Also avoid the F1-F12 row - on modern Macs those are hardware media keys
# (Dictation/Siri/brightness/etc.) intercepted by macOS itself, so apps can't reliably
# see them. If you change this, check System Settings > Keyboard > Keyboard Shortcuts
# for conflicts first.
HOTKEY = "ctrl+alt"

# faster-whisper model size: tiny, base, small, medium, large-v3
# Bigger = more accurate, slower, more RAM. "small" is a reasonable starting point on Apple Silicon.
MODEL_SIZE = "small"

# Compute type for faster-whisper. "int8" is fastest on CPU and a good default.
COMPUTE_TYPE = "int8"

# Audio settings — Whisper expects 16kHz mono.
SAMPLE_RATE = 16000
CHANNELS = 1

# Output mode: "paste" (copy to clipboard + simulate Cmd+V) or "type" (simulate keystrokes directly).
# "paste" is faster and handles special characters better; "type" doesn't touch the clipboard.
OUTPUT_MODE = "paste"

# Language hint for transcription. None = auto-detect. Set to "en" or "es" to force one.
LANGUAGE = None

# Safety cap: if the hotkey is held longer than this (e.g. accidentally left down),
# recording auto-stops and transcribes what it has so far instead of hanging
# indefinitely and blocking the app from responding to anything else.
MAX_RECORDING_SECONDS = 300
