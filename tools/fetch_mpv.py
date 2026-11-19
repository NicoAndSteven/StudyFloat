"""Download a portable mpv build into resources/mpv/.

Supports .zip and .7z. For .7z with BCJ2 filters we use 7zr.exe (downloaded
into %LOCALAPPDATA%/studyfloat-tools) when py7zr cannot handle the filter.
Override the release URL with --url.
"""
import argparse
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_URL = (
    "https://github.com/zhongfly/mpv-winbuild/releases/download/"
    "2026-11-18-f92afa75cd/mpv-x86_64-20261118-git-f92afa75cd.7z"
)
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


def extract(data: bytes, archive: Path, dest: Path) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(dest)
        print("extracted via zip")
        return
    except zipfile.BadZipFile:
        pass
    try:
        import py7zr
        with py7zr.SevenZipFile(io.BytesIO(data)) as z:
            z.extractall(dest)
        print("extracted via py7zr")
        return
    except Exception as exc:  # BCJ2 or other unsupported filter
        print("py7zr failed:", exc)
    exe7z = get_7zr()
    import subprocess
    subprocess.run([str(exe7z), "x", str(archive), f"-o{dest}", "-y"], check=True)
    print("extracted via 7zr")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    args = ap.parse_args()
    dest = Path(__file__).resolve().parents[1] / "resources" / "mpv"
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "mpv-release.7z"
    print("downloading", args.url)
    req = urllib.request.Request(args.url, headers={"User-Agent": "studyfloat/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    print("downloaded", len(data), "bytes")
    archive.write_bytes(data)
    extract(data, archive, dest)
    exe = dest / "mpv.exe"
    if not exe.exists():
        matches = [p for p in dest.rglob("mpv.exe")]
        if matches:
            shutil.move(str(matches[0]), str(exe))
        else:
            raise SystemExit("mpv.exe not found after extraction")
    print("mpv ready:", exe)


if __name__ == "__main__":
    main()
