from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

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
    canonical = f"https://www.bilibili.com/video/{m.group(1)}"

    # 多P视频必须保留 p 参数：剥离后 yt-dlp 会把整个合集当作多条目资源枚举，
    # 导致解析长时间无响应。p=1 可安全省略（等价于默认第一P）。
    try:
        params = parse_qs(urlparse(text).query)
        p = params.get("p", [None])[0]
    except Exception:
        p = None
    if p and p.isdigit() and int(p) > 1:
        canonical += f"?p={int(p)}"
    return canonical
