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

### If Accessibility/Input Monitoring show "granted" but it still doesn't work

Homebrew's Python re-execs into a small bundled `Python.app` to get window-server
access (that's what pynput needs for the global hotkey) — this is the actual
process macOS checks, not your terminal app. Find it with:

```bash
ls /opt/homebrew/Cellar/python@3.13/*/Frameworks/Python.framework/Versions/3.13/Resources/Python.app
```

Add *that* `Python.app` (not Terminal/iTerm) to both **System Settings > Privacy
& Security > Accessibility** and **> Input Monitoring**, toggled on. If the
toggle is already on but it still fails (this happens with unsigned/ad-hoc
binaries), reset and re-request it properly:

```bash
tccutil reset Accessibility org.python.python
python -c "import ApplicationServices as AS; print(AS.AXIsProcessTrustedWithOptions({AS.kAXTrustedCheckOptionPrompt: True}))"
```

This pops a real system dialog — click Allow. Re-run the check; it should print `True`.

### If the mic records only silence (all-zero samples, no prompt, no Settings entry)

Homebrew's `Python.app` doesn't declare `NSMicrophoneUsageDescription` in its
`Info.plist`, so macOS never shows the mic consent prompt or lists it in
Settings — it just silently feeds zeros. Fix once per machine (needs
re-applying after any `brew upgrade python@3.13`):

```bash
PLIST="/opt/homebrew/Cellar/python@3.13/3.13.3/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/Info.plist"
cp "$PLIST" "$PLIST.voxtype-backup"
/usr/libexec/PlistBuddy -c "Add :NSMicrophoneUsageDescription string 'Needed so this Python process can record audio for local dictation (VoxType dev loop).'" "$PLIST"
codesign --force --deep --sign - "$(dirname "$(dirname "$PLIST")")"
killall tccd  # clears a stale cache that otherwise keeps returning silence
```

(Adjust the Python version in the path if yours differs.)

### If `pip install -e .` succeeds but `import transcript_app` fails anyway

If this project lives inside a folder synced by iCloud Drive ("Desktop &
Documents Folders"), the sync daemon can flip newly-installed files back to
macOS's hidden-file flag faster than you'd notice, and Python 3.13+ silently
skips hidden `.pth` files as a security hardening — which breaks editable
installs with no clear error. Fastest fix: keep the venv **outside** the
synced folder and symlink it in, so nothing about the workflow below changes:

```bash
python3 -m venv ~/.venvs/transcript_app
ln -s ~/.venvs/transcript_app .venv
source .venv/bin/activate && pip install -e .
```

## Run it

```bash
python -m transcript_app
# or, equivalently, now that it's installed:
voxtype
```

Hold the hotkey (Control+Option by default — see `config.py`), speak, let go.
Watch the terminal — it prints what it heard, then pastes it.

## Testing & security

```bash
pip install -e ".[dev]"
pytest              # unit tests, incl. regression tests for real bugs found during development
bandit -r src/transcript_app   # static security scan
pip-audit                      # checks dependencies against known CVEs
```

All three run automatically on every push via GitHub Actions (`.github/workflows/ci.yml`).
The test suite mocks the microphone, model, and hotkey listener — it doesn't need a
real mic or macOS permissions to run, so it also works in CI.

## Packaging a real .app

```bash
pip install -e ".[build]"
pyinstaller voxtype.spec --noconfirm
open dist/VoxType.app
```

Notes:

- `entry_point.py` exists only because PyInstaller runs its entry script standalone,
  and `transcript_app/__main__.py`'s relative import doesn't work in that context.
- This produces an **ad-hoc signed** app — it runs, but macOS Gatekeeper will still
  warn on first launch on someone else's Mac (right-click > Open gets past it). A
  real Apple Developer ID + notarization is needed before distributing this to
  people who aren't you.
- The packaged app is its own bundle (`com.voxtype.app`), separate from whatever
  Python you built it with — it needs its **own** Accessibility / Input Monitoring /
  Microphone grants in System Settings the first time it runs, same dance as the
  README's permissions section above, just for a different app in the list.
- If code signing fails with a "resource fork, Finder information, or similar
  detritus not allowed" error, and this project lives inside an iCloud-synced
  folder, run `xattr -cr dist/VoxType.app` and re-sign - same root cause as the
  hidden-`.pth`-file issue above.
- `build/` and `dist/` are gitignored — they're regenerated from `voxtype.spec`,
  never commit them.

## Current limitations (this is the dev version, not the product yet)

- Hold-to-record only (no toggle mode yet)
- Hotkey is set in `config.py`, no in-app way to change it yet
- No settings UI — everything is edited in `config.py`
- Packaged build is ad-hoc signed only — no Developer ID signing/notarization yet,
  so Gatekeeper will warn on another Mac
- Model is downloaded on first launch, not bundled into the installer yet
- First run downloads the whisper model (size depends on `MODEL_SIZE` in `config.py`)

## Roadmap

See the `voxtype-productization-plan.md` doc in Larry's Business project for the
full path from here to a sellable product (packaging, code signing, settings UI,
pricing, launch).
