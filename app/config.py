from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.json")


@dataclass
class Config:
    cookie_path: str = ""
    default_speed: float = 1.0
    default_volume: int = 100
    window_preset: str = "标准"
    always_on_top: bool = True
    borderless: bool = True
    geometry: str = "480x270+100+100"
    recent_urls: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        p = path or DEFAULT_CONFIG_PATH
        if not p.exists():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, path: Path | None = None) -> None:
        p = path or DEFAULT_CONFIG_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
