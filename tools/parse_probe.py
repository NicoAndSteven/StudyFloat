"""Validation A: confirm a public BV URL resolves to playable direct streams."""
import json
import sys
from yt_dlp import YoutubeDL

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.bilibili.com/video/BV1GJ411x7h7"

opts = {"quiet": True, "no_warnings": False, "skip_download": True, "socket_timeout": 20}
if len(sys.argv) > 2:
    opts["cookiefile"] = sys.argv[2]
with YoutubeDL(opts) as ydl:
    info = ydl.extract_info(URL, download=False)

print(json.dumps({
    "title": info.get("title"),
    "duration": info.get("duration"),
    "http_headers": info.get("http_headers", {}),
    "formats": [
        {"id": f.get("format_id"), "vcodec": f.get("vcodec"), "acodec": f.get("acodec"),
         "width": f.get("width"), "height": f.get("height"),
         "protocol": f.get("protocol"), "url_head": (f.get("url") or "")[:80]}
        for f in (info.get("formats") or [])
    ],
}, ensure_ascii=False, indent=2))
