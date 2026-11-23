"""Pack the portable onedir bundle into a compressed .7z (the "installer").

The folder itself is the installed app (~200 MB); this archive is what users
download. 7zr is fetched once into %LOCALAPPDATA%/studyfloat-tools.

Usage:
    python tools/package.py                    # dist/StudyFloat_v5 -> .7z
    python tools/package.py --name StudyFloat_v5
"""
from __future__ import annotations

import argparse
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEVEN_ZIPR_URL = "https://github.com/ip7z/7zip/releases/download/26.06/7zr.exe"


def get_7zr() -> Path:
    tools = Path.home() / "AppData" / "Local" / "studyfloat-tools"
    tools.mkdir(parents=True, exist_ok=True)
    exe = tools / "7zr.exe"
    if not exe.exists():
        print("downloading 7zr.exe")
        req = urllib.request.Request(SEVEN_ZIPR_URL, headers={"User-Agent": "studyfloat/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            exe.write_bytes(r.read())
    return exe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="StudyFloat_v5")
    ap.add_argument("--dist", default=str(ROOT / "dist"))
    args = ap.parse_args()

    dist = Path(args.dist)
    src = dist / args.name
    if not src.is_dir():
        raise SystemExit(f"bundle not found: {src}")

    out = dist / f"{args.name}.7z"
    out.unlink(missing_ok=True)
    print(f"[pack] compressing {src.name} -> {out.name}")
    subprocess.run(
        [str(get_7zr()), "a", "-t7z", "-mx=9", "-mmt=on", str(out), args.name],
        cwd=dist,
        check=True,
    )

    raw = sum(f.stat().st_size for f in src.rglob("*") if f.is_file()) / (1024 * 1024)
    packed = out.stat().st_size / (1024 * 1024)
    print(f"[pack] installed {raw:.1f} MB -> download {packed:.1f} MB ({raw / packed:.2f}x)")


if __name__ == "__main__":
    main()
