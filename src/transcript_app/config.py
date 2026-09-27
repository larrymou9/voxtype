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
# Bigger = more accurate, slower, more RAM. "small" is a reasonable starting point
# on Apple Silicon (measured ~1.5s release-to-paste latency); "medium" trades
# ~0.7s more latency (measured ~2.2s) for noticeably better accuracy.
MODEL_SIZE = "medium"

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

# EXPERIMENTAL, off by default - read this before turning it on.
#
# While the hotkey is held, re-transcribe everything captured so far every
# this-many seconds, in the background. On release, only the new audio since
# the last check needs transcribing, instead of the whole recording.
#
# Measured 2026-09-27 on an M1 Max, real mic input, same ~8.5s test clip:
#   MODEL_SIZE=medium:  no streaming 6.09s  vs  streaming (interval=2.0) 7.34s  -> WORSE
#   MODEL_SIZE=small:   no streaming 7.01s  vs  streaming (interval=2.0) 6.50s  -> slightly better
#   MODEL_SIZE=medium, a much longer ~23.5s clip: no streaming 10.78s vs streaming 7.18s -> clearly better
#
# The naive approach here (re-transcribe the whole growing buffer each
# check) only pays off once a periodic check's own transcribe time is
# comfortably faster than real-time speech. "medium" is only marginally
# faster than real-time for this, so checks can't get far enough ahead, and
# the redundant re-work makes typical-length holds slower, not faster - a
# real regression, not just "no benefit." Only "large-v3" is slower still,
# so the safe default is off. If you set MODEL_SIZE to "small"/"base"/"tiny"
# you can reasonably try enabling this (e.g. 2.0); re-measure your own
# typical dictation length before trusting it, using the same before/after
# method as above.
#
# The actual fix - a fast, separate "draft" model for periodic checks,
# decoupled from whichever accurate model does the final tail - is real
# future work, not implemented here. See README's TODO.
#
# Set to 0 (or None) to disable, and always transcribe the whole recording
# at once on release (the default, and the only behavior tested with medium).
PARTIAL_TRANSCRIBE_INTERVAL = 0
