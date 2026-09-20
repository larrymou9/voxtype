# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# faster-whisper/ctranslate2 ship compiled .dylibs and data files PyInstaller's
# default analysis won't find on its own.
for pkg in ["ctranslate2", "faster_whisper", "tokenizers", "huggingface_hub"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += [
    "pynput.keyboard._darwin",
    "pynput.mouse._darwin",
]

a = Analysis(
    ["entry_point.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoxType",
    debug=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="VoxType")

app = BUNDLE(
    coll,
    name="VoxType.app",
    icon=None,
    bundle_identifier="com.voxtype.app",
    info_plist={
        "NSMicrophoneUsageDescription": "VoxType needs microphone access to transcribe your speech locally - audio never leaves this Mac.",
        "LSUIElement": True,
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHumanReadableCopyright": "VoxType",
    },
)
