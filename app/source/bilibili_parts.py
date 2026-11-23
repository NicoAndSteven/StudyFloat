"""获取B站合辑（多P视频）的分P列表。

B站官方 view API 一次返回全部分P元数据（page/cid/标题/时长），毫秒级；
绕开 yt-dlp 逐个枚举整个合集导致的长时间无响应。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

VIEW_API = "https://api.bilibili.com/x/web-interface/view"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 仅作为测试/调用方注入点保留；正常路径每次请求自建会话并在同一线程关闭。
_session = None


def _new_session():
    from curl_cffi import requests as cffi_requests

    session = cffi_requests.Session(impersonate="chrome")
    session.headers.update({"User-Agent": _UA})
    return session


@dataclass
class PartInfo:
    page: int
    cid: int
    title: str
    duration: int


def fetch_parts(bvid: str, timeout: float = 15.0) -> list[PartInfo]:
    """返回该 BV 视频的全部分P信息，按 page 升序。

    每次调用创建并关闭自己的 curl_cffi Session：解析在后台 QThread 里，
    若把 Session 留在模块全局，它会被下一个线程复用/在别的线程析构，
    Curl.__del__ 会在 Python 线程退出时触发原生崩溃。显式 close 放在
    finally，保证 curl_easy_cleanup 与创建发生在同一线程。
    """
    session = _session
    owned = session is None
    if owned:
        session = _new_session()
    try:
        resp = session.get(VIEW_API, params={"bvid": bvid}, timeout=timeout)
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
    finally:
        if owned:
            try:
                session.close()
            except Exception:
                pass


@dataclass
class PartSelection:
    """分P选择决策结果。show_picker 为是否弹列表；highlight_page 为默认选中的 P。"""
    show_picker: bool
    highlight_page: int


def requested_page(url: str) -> int | None:
    """从 URL 的 p 查询参数中提取分P编号（无效/缺失返回 None）。"""
    try:
        raw = parse_qs(urlparse(url).query).get("p", [None])[0]
    except Exception:
        return None
    return int(raw) if raw and str(raw).isdigit() else None


def decide_selection(parts: list[PartInfo], url: str) -> PartSelection:
    """决定是否需要弹分P列表，以及默认高亮哪一P。

    合辑（>1 个分P）总是弹列表，即便 URL 带 ?p=N；单P视频直接播放。
    高亮 URL 里请求的 P；若缺失或越界则默认第一P。
    """
    pages = {p.page for p in parts}
    if not is_multi_part(parts):
        first = min(pages) if pages else 1
        return PartSelection(show_picker=False, highlight_page=first)
    requested = requested_page(url)
    highlight = requested if requested in pages else (min(pages) if pages else 1)
    return PartSelection(show_picker=True, highlight_page=highlight)


def is_multi_part(parts: list[PartInfo]) -> bool:
    """是否是需要用户选择的合辑（多于 1 个分P）。"""
    return len(parts) > 1


def pick_part_url(base_url: str, part: PartInfo) -> str:
    """把选中的分P编号拼回 URL，供现有解析器精确解析该P。"""
    clean = base_url.split("?")[0].rstrip("/")
    return f"{clean}?p={part.page}"
