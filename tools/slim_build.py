"""Post-build slimming for the PyInstaller onedir bundle.

PyInstaller's PySide6 hook collects every Qt6*.dll and every plugin in the
wheel. This app only uses QtCore/QtGui/QtWidgets, so the rest is dead weight.

The keep-list below is explicit: anything under ``_internal/PySide6`` that is
not listed is deleted. That is safe for a widgets-only app and is verified by
launching the frozen exe after slimming.

Usage:
    python tools/slim_build.py                 # default dist/StudyFloat_v5
    python tools/slim_build.py --name Foo

yt-dlp extractors are intentionally *not* trimmed here: lazy_extractors.py
imports unrelated extractor modules while resolving some classes, so a naive
delete can break a B站 parse. Dropping yt-dlp altogether is a code change, not
a packaging step.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files (relative to _internal/PySide6) that a QtWidgets app needs on Windows.
# Qt6Network/Qt6Svg and the image-format/platform plugins are NOT needed: the
# UI draws everything with QPainter and loads no images.
KEEP = {
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
    "QtCore.pyd",
    "QtGui.pyd",
    "QtWidgets.pyd",
    "pyside6.abi3.dll",
    "MSVCP140.dll",
    "MSVCP140_1.dll",
    "MSVCP140_2.dll",
    "VCRUNTIME140.dll",
    "VCRUNTIME140_1.dll",
    r"plugins\platforms\qwindows.dll",
    r"plugins\styles\qmodernwindowsstyle.dll",
}


def _size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / (1024 * 1024)


def slim_pyside6(bundle: Path) -> tuple[float, int]:
    qt = bundle / "_internal" / "PySide6"
    if not qt.is_dir():
        return 0.0, 0

    before = _size_mb(qt)
    removed = 0
    for path in sorted(qt.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.is_file():
            continue
        rel = str(path.relative_to(qt))
        rel_dir = rel.replace("/", "\\")
        if rel_dir in KEEP:
            continue
        path.unlink(missing_ok=True)
        removed += 1

    # Remove now-empty plugin folders and __pycache__.
    for path in sorted(qt.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()

    return before - _size_mb(qt), removed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="StudyFloat_v5", help="COLLECT name used by build.spec")
    ap.add_argument("--dist", default=str(ROOT / "dist"), help="dist directory")
    args = ap.parse_args()

    bundle = Path(args.dist) / args.name
    if not bundle.is_dir():
        raise SystemExit(f"bundle not found: {bundle}")

    before = _size_mb(bundle)
    saved_qt, removed = slim_pyside6(bundle)

    # Build-only helper shipped inside the yt-dlp package.
    shutil.rmtree(bundle / "_internal" / "yt_dlp" / "__pyinstaller", ignore_errors=True)

    after = _size_mb(bundle)
    print(f"[slim] {bundle}")
    print(f"[slim] removed {removed} Qt files, saved {saved_qt:.1f} MB")
    print(f"[slim] {before:.1f} MB -> {after:.1f} MB (saved {before - after:.1f} MB)")


if __name__ == "__main__":
    main()
