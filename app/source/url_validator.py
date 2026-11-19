from __future__ import annotations

import re

_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})", re.IGNORECASE)


class InvalidUrl(ValueError):
    """Raised when the input is not a recognizable Bilibili BV link/id."""


def normalize_url(raw: str) -> str:
    """Accept a BV id, a full/partial Bilibili URL or a b23.tv URL; return canonical URL."""
    text = (raw or "").strip()
    if not text:
        raise InvalidUrl("链接为空")
    if "bilibili.com" not in text and "b23.tv" not in text and not _BV_RE.fullmatch(text):
        raise InvalidUrl("仅支持 Bilibili 视频链接或 BV 号")
    m = _BV_RE.search(text)
    if not m:
        raise InvalidUrl("未找到有效的 BV 号（应为 BV 加 10 位字母数字）")
    return f"https://www.bilibili.com/video/{m.group(1)}"
