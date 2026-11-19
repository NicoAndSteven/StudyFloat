"""实测 yt-dlp 的 cookiesfrombrowser 能否自动读取本机 Chrome/Edge 的 B站 Cookie。"""
from yt_dlp import YoutubeDL

URL = "https://www.bilibili.com/video/BV1GJ411x7h7"

for browser in ("chrome", "edge"):
    print(f"=== {browser} ===")
    try:
        with YoutubeDL({
            "quiet": True,
            "no_warnings": False,
            "skip_download": True,
            "socket_timeout": 20,
            "cookiesfrombrowser": (browser,),
        }) as ydl:
            info = ydl.extract_info(URL, download=False)
        fmts = info.get("formats") or []
        heights = sorted({f.get("height") for f in fmts if f.get("height")}, reverse=True)
        print(f"  解析成功: 标题={info.get('title', '')[:25]}, 清晰度={heights[:6]}")
    except Exception as e:
        print(f"  失败: {type(e).__name__}: {str(e)[:180]}")
