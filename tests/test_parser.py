from unittest.mock import patch

import pytest

from app.player.errors import CookieRejectedError, NetworkError, ParseError
from app.source.bilibili_parser import BilibiliParser, StreamInfo

URL = "https://www.bilibili.com/video/BV1GJ411x7h7"


def _info(formats):
    return {
        "title": "测试视频",
        "duration": 610,
        "http_headers": {"Referer": "https://www.bilibili.com/"},
        "formats": formats,
    }


def test_prefers_combined_format():
    formats = [
        {"format_id": "dash-v", "vcodec": "avc1", "acodec": "none", "width": 1920, "url": "http://v"},
        {"format_id": "dash-a", "vcodec": "none", "acodec": "mp4a", "url": "http://a"},
        {"format_id": "64", "vcodec": "avc1", "acodec": "mp4a", "width": 480, "url": "http://combined"},
    ]
    with patch("app.source.bilibili_parser.YoutubeDL") as ydl:
        ydl.return_value.__enter__.return_value.extract_info.return_value = _info(formats)
        info = BilibiliParser().parse(URL)
    assert isinstance(info, StreamInfo)
    assert info.video_url == "http://combined"
    assert info.audio_url is None
    assert info.title == "测试视频"
    assert info.http_headers == {"Referer": "https://www.bilibili.com/"}


def test_dash_fallback_selects_best_video_and_best_audio():
    # Real-world case seen in validation A: all Bilibili formats are DASH.
    formats = [
        {"format_id": "v1", "vcodec": "avc1", "acodec": "none", "width": 480, "url": "http://v1"},
        {"format_id": "v2", "vcodec": "avc1", "acodec": "none", "width": 1920, "url": "http://v2"},
        {"format_id": "a1", "vcodec": "none", "acodec": "mp4a", "tbr": 64, "url": "http://a1"},
        {"format_id": "a2", "vcodec": "none", "acodec": "mp4a", "tbr": 128, "url": "http://a2"},
    ]
    with patch("app.source.bilibili_parser.YoutubeDL") as ydl:
        ydl.return_value.__enter__.return_value.extract_info.return_value = _info(formats)
        info = BilibiliParser().parse(URL)
    assert info.video_url == "http://v2"
    assert info.audio_url == "http://a2"


def test_no_playable_format_raises_parse_error():
    with patch("app.source.bilibili_parser.YoutubeDL") as ydl:
        ydl.return_value.__enter__.return_value.extract_info.return_value = _info([])
        with pytest.raises(ParseError):
            BilibiliParser().parse(URL)


def test_cookiefile_is_passed(tmp_path):
    cookie = tmp_path / "cookies.txt"
    cookie.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    with patch("app.source.bilibili_parser.YoutubeDL") as ydl:
        ydl.return_value.__enter__.return_value.extract_info.return_value = _info(
            [{"format_id": "64", "vcodec": "avc1", "acodec": "mp4a", "url": "http://c"}]
        )
        BilibiliParser(cookie_path=str(cookie)).parse(URL)
    assert ydl.call_args.args[0].get("cookiefile") == str(cookie)


@pytest.mark.parametrize("message,expected", [
    ("HTTP Error 412: Precondition Failed", CookieRejectedError),
    ("Video is protected: login required", ParseError),
    ("network connection timed out", NetworkError),
    ("some unknown extractor error", ParseError),
])
def test_error_classification(message, expected):
    with patch("app.source.bilibili_parser.YoutubeDL") as ydl:
        from yt_dlp.utils import DownloadError
        ydl.return_value.__enter__.return_value.extract_info.side_effect = DownloadError(message)
        with pytest.raises(expected):
            BilibiliParser().parse(URL)
