from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.player.errors import CookieRejectedError, NetworkError, ParseError


@dataclass
class StreamInfo:
    video_url: str
    audio_url: str | None
    title: str
    duration: float | None
    http_headers: dict[str, str] = field(default_factory=dict)


def _has_video(f: dict[str, Any]) -> bool:
    return bool(f.get("url")) and f.get("vcodec") not in (None, "none")


def _has_audio(f: dict[str, Any]) -> bool:
    return bool(f.get("url")) and f.get("acodec") not in (None, "none")


def _best_video_score(f: dict[str, Any]) -> tuple[int, int, float]:
    return (f.get("width") or 0, f.get("height") or 0, f.get("tbr") or 0.0)


class BilibiliParser:
    """Parsing only: no UI, no mpv. Stream URLs are never cached (they expire)."""

    def __init__(self, cookie_path: str | None = None):
        self.cookie_path = cookie_path or ""

    def parse(self, url: str) -> StreamInfo:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 20,
            "retries": 2,
        }
        if self.cookie_path and Path(self.cookie_path).is_file():
            opts["cookiefile"] = self.cookie_path
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except DownloadError as exc:
            raise self._classify(str(exc)) from exc
        except Exception as exc:
            raise NetworkError("网络连接失败，请检查网络后重试") from exc

        formats = list(info.get("formats") or [])
        headers = dict(info.get("http_headers") or {})
        title = info.get("title") or ""
        duration = info.get("duration")

        combined = [f for f in formats if _has_video(f) and _has_audio(f)]
        if combined:
            best = max(combined, key=_best_video_score)
            return StreamInfo(best["url"], None, title, duration, headers)

        videos = [f for f in formats if _has_video(f) and not _has_audio(f)]
        audios = [f for f in formats if _has_audio(f) and not _has_video(f)]
        if videos and audios:
            best_v = max(videos, key=_best_video_score)
            best_a = max(audios, key=lambda f: f.get("tbr") or 0.0)
            return StreamInfo(best_v["url"], best_a["url"], title, duration, headers)

        raise ParseError("未找到可播放的视频流，请稍后重试或更新 Cookie")

    @staticmethod
    def _classify(message: str) -> ParseError:
        low = message.lower()
        if "412" in low or "forbidden" in low or "blocked" in low:
            return CookieRejectedError("访问被平台拒绝，请更新 Cookie 或稍后重试")
        if any(k in low for k in ("login", "会员", "登录", "permission", "private", "removed", "deleted")):
            return ParseError("无法访问该视频：可能需要登录或视频已删除")
        if any(k in low for k in ("network", "timeout", "dns", "connection")):
            return NetworkError("网络连接失败，请检查网络后重试")
        return ParseError("视频解析失败，请检查链接或稍后重试")
