# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build for StudyFloat (portable green folder).

Only QtCore / QtGui / QtWidgets are used by the launcher; everything else in
PySide6 (WebEngine, Qml, Quick, Pdf, Charts, ...) is excluded to keep the
portable package small. mpv is a self-contained binary and is bundled whole.
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

# yt-dlp dynamically imports its extractors -> collect all of them (~10 MB).
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
    "PySide6.QtSvgWidgets",
    "matplotlib",
    "numpy",
    "PIL",
]

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
    name="StudyFloat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="StudyFloat")

# --- Post-build slimming -------------------------------------------------
# PyInstaller's PySide6 hook collects more Qt DLLs than we need. Keep only
# QtCore/QtGui/QtWidgets (+ their runtime deps) and drop the rest.
from pathlib import Path
import shutil

qt_dir = Path(DISTPATH) / "StudyFloat" / "_internal" / "PySide6"
keep_dlls = {
    "Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll", "Qt6Network.dll",
    "Qt6Svg.dll", "pyside6.abi3.dll", "MSVCP140.dll", "MSVCP140_1.dll",
    "MSVCP140_2.dll", "VCRUNTIME140.dll", "VCRUNTIME140_1.dll",
}
if qt_dir.exists():
    for dll in qt_dir.glob("*.dll"):
        if dll.name not in keep_dlls:
            dll.unlink()
    # Qt translations are unused; platform 'styles'/'imageformats' plugins and
    # the 'platforms' plugin are required for the GUI to run.
    trans = qt_dir / "translations"
    if trans.exists():
        shutil.rmtree(trans)
    # Keep only essential plugin folders.
    plug = qt_dir / "plugins"
    if plug.exists():
        keep_plugins = {"platforms", "styles", "imageformats"}
        for child in list(plug.iterdir()):
            if child.is_dir() and child.name not in keep_plugins:
                shutil.rmtree(child)
print("[StudyFloat] slimmed PySide6 runtime")

