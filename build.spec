# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build for StudyFloat (portable green folder).

Only QtCore / QtGui / QtWidgets are used by the launcher; everything else in
PySide6 (WebEngine, Qml, Quick, Pdf, Charts, ...) is excluded to keep the
portable package small. mpv is a self-contained binary and is bundled whole.
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

# yt-dlp dynamically imports its extractors -> collect all of them (~9.5 MB).
# We deliberately keep them all: lazy_extractors.py imports unrelated extractor
# modules while resolving some classes, so trimming by hand is brittle. A
# Bilibili-only native parser is the clean way to drop yt-dlp (see
# docs/体积优化分析.md).
datas, binaries, hiddenimports = [], [], []
ydl_d, ydl_b, ydl_h = collect_all("yt_dlp")
datas += ydl_d
binaries += ydl_b
hiddenimports += ydl_h

# Only the Qt modules our UI actually imports. PyInstaller's PySide6 hook then
# collects just the matching DLLs/plugins instead of the whole framework.
hiddenimports += [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "curl_cffi",
    "curl_cffi.requests",
    "qrcode",
]

# curl_cffi ships native libs (libcurl/boringSSL) that must be bundled.
for pkg in ("curl_cffi", "qrcode"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

datas += [
    ("app/player/resources/studyfloat.lua", "app/player/resources"),
    ("app/player/resources/input.conf", "app/player/resources"),
]
binaries += [("resources/mpv/mpv.exe", "resources/mpv")]

# Modules we never use — excluding them removes WebEngine (~280 MB) and friends.
excludes = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngine",
    "PySide6.QtWebView",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtBluetooth",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtNetwork",
    "matplotlib",
    "numpy",
    "PIL",
]

# 输出目录名（改这里可同时切换 EXE 名与精简路径，便于绕开被占用的旧目录）
APP_NAME = "StudyFloat_v8"

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)

# NOTE: do NOT clean the output here. The spec file is evaluated before COLLECT
# actually writes the bundle, so any cleanup at this point would either be a
# no-op or touch a stale directory. Run `python tools/slim_build.py` after
# PyInstaller finishes; `python tools/package.py` then produces the .7z.


