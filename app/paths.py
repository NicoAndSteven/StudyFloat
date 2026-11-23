"""可执行文件 / 配置路径解析。

单独成模块，避免设置窗口为了读一个路径而 import app.main（后者会连锁
import yt-dlp / curl_cffi，拖慢窗口打开速度）。
"""
from __future__ import annotations

import sys
from pathlib import Path

QR_COOKIE_FILE = "qr_cookies.txt"


def app_dir() -> Path:
    """Root of the bundled app (PyInstaller _MEIPASS or project root in dev)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def data_path(name: str) -> Path:
    """Settings/config files live beside the executable (or cwd in dev)."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    return base / name
