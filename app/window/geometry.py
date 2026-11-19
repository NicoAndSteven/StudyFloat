from __future__ import annotations

import json
import re
from pathlib import Path

GEOMETRY_PATH = Path("geometry.json")

PRESETS = {
    "微型": (320, 180),
    "小型": (400, 225),
    "标准": (480, 270),
    "大型": (640, 360),
}

_GEOM_RE = re.compile(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)")


def geometry_for_preset(name: str, x: int = 100, y: int = 100) -> str:
    w, h = PRESETS.get(name, PRESETS["标准"])
    return f"{w}x{h}+{x}+{y}"


def parse_geometry(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    m = _GEOM_RE.search(value)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))


def save_geometry(value: str, path: Path | None = None) -> None:
    p = path or GEOMETRY_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def load_geometry(path: Path | None = None) -> str | None:
    p = path or GEOMETRY_PATH
    if not p.exists():
        return None
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, str) else None
