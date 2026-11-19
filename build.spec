# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build for StudyFloat (portable green folder)."""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("PySide6", "yt_dlp"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# Our own resources (Lua OSC + key bindings) and the mpv player binary.
datas += [
    ("app/player/resources/studyfloat.lua", "app/player/resources"),
    ("app/player/resources/input.conf", "app/player/resources"),
]
binaries += [("resources/mpv/mpv.exe", "resources/mpv")]

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StudyFloat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="StudyFloat")
