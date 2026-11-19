"""获取B站合辑（多P视频）的分P列表。

B站官方 view API 一次返回全部分P元数据（page/cid/标题/时长），毫秒级；
绕开 yt-dlp 逐个枚举整个合集导致的长时间无响应。
"""
from __future__ import annotations

from dataclasses import dataclass

from curl_cffi import requests as cffi_requests

VIEW_API = "https://api.bilibili.com/x/web-interface/view"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 模块级 session，便于测试时 patch 替换
_session = cffi_requests.Session(impersonate="chrome")
_session.headers.update({"User-Agent": _UA})


@dataclass
class PartInfo:
    page: int
    cid: int
    title: str
    duration: int


def fetch_parts(bvid: str, timeout: float = 15.0) -> list[PartInfo]:
    """返回该 BV 视频的全部分P信息，按 page 升序。"""
    resp = _session.get(VIEW_API, params={"bvid": bvid}, timeout=timeout)
    data = resp.json()
    if data.get("code") != 0 or not data.get("data"):
        raise RuntimeError(data.get("message") or "获取分P列表失败")
    pages = (data["data"].get("pages") or [])
    parts = [
        PartInfo(
            page=int(p.get("page") or 0),
            cid=int(p.get("cid") or 0),
            title=str(p.get("part") or f"P{p.get('page')}"),
            duration=int(p.get("duration") or 0),
        )
        for p in pages
    ]
    return sorted(parts, key=lambda x: x.page)


def is_multi_part(parts: list[PartInfo]) -> bool:
    """是否是需要用户选择的合辑（多于 1 个分P）。"""
    return len(parts) > 1


def pick_part_url(base_url: str, part: PartInfo) -> str:
    """把选中的分P编号拼回 URL，供现有解析器精确解析该P。"""
    clean = base_url.split("?")[0].rstrip("/")
    return f"{clean}?p={part.page}"
