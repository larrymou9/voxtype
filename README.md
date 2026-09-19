# VoxType

Hold a hotkey, speak, release it, and the transcription gets pasted wherever your cursor is.
Runs fully locally (faster-whisper) — audio never leaves your Mac.

## Setup

```bash
cd transcript_app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

`pip install -e .` installs the dependencies AND registers this project as an
importable/runnable package (that's what makes `python -m transcript_app` and the
`voxtype` command below work). If you already ran `pip install -r requirements.txt`
before this file existed, just run `pip install -e .` once more in the same venv —
it'll reuse what's already downloaded and just add the missing registration step.

## macOS permissions (required)

The first time you run it, macOS will need to grant two permissions to your terminal
(or to the packaged app, later):

1. **System Settings > Privacy & Security > Microphone** — so it can hear you.
2. **System Settings > Privacy & Security > Accessibility** — so it can capture the
   global hotkey reliably and simulate the paste keystroke.

If dictation silently does nothing, this is almost always the cause — check both.

## Run it

```bash
python -m transcript_app
# or, equivalently, now that it's installed:
voxtype
```

Hold the hotkey (Control+Space by default — see `config.py`), speak, let go.
Watch the terminal — it prints what it heard, then pastes it.

## Current limitations (this is the dev version, not the product yet)

- Hold-to-record only (no toggle mode yet)
- Hotkey is set in `config.py`, no in-app way to change it yet
- No settings UI — everything is edited in `config.py`
- Not packaged as a real .app yet — this is scaffolding to develop and test the core loop
- First run downloads the whisper model (size depends on `MODEL_SIZE` in `config.py`)

## Roadmap

See the `voxtype-productization-plan.md` doc in Larry's Business project for the
full path from here to a sellable product (packaging, code signing, settings UI,
pricing, launch).
