# StudyFloat P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build StudyFloat P0 — parse a Bilibili BV URL with yt-dlp and play it in an independent, borderless, always-on-top mpv window controlled over JSON IPC, with a minimal launcher/settings UI, auto-hiding OSC control layer, geometry persistence, and a portable no-install Windows package.

**Architecture:** A thin PySide6 launcher owns URL input, parsing and settings; yt-dlp (library mode) resolves the BV URL into direct DASH/combined stream URLs; a standalone `mpv.exe` process renders a real OS window that survives browser/launcher shutdown and is controlled by newline-delimited JSON over a Windows named pipe. The parser and player are decoupled; all settings persist to a JSON file beside the app.

**Tech Stack:** Python 3.12, PySide6 (LGPL), yt-dlp, mpv (standalone Windows build), JSON IPC over `\\.\pipe\`, PyInstaller `--onedir`, pytest.

**Reference spec:** `docs/superpowers/specs/2026-11-19-studyfloat-design.md`

---

## File Structure

```
D:\Asmallvideo\
├── app/
│   ├── __init__.py
│   ├── main.py                       # entry point, wires UI + parser + player
│   ├── config.py                     # Config dataclass + JSON load/save
│   ├── source/
│   │   ├── __init__.py
│   │   ├── url_validator.py          # BV/full URL validation + normalization
│   │   └── bilibili_parser.py        # yt-dlp wrapper -> StreamInfo
│   ├── player/
│   │   ├── __init__.py
│   │   ├── mpv_controller.py         # mpv subprocess + named-pipe JSON IPC
│   │   ├── errors.py                 # typed exceptions (parse/player errors)
│   │   └── resources/
│   │       ├── studyfloat.lua        # minimal OSC config + drag + menu bindings
│   │       └── input.conf            # keyboard/mouse bindings
│   └── ui/
│       ├── __init__.py
│       ├── launcher.py               # minimal URL input window
│       └── settings_dialog.py        # cookie path, speed, volume, presets, flags
├── tools/
│   └── fetch_mpv.py                  # download mpv_win64 into resources/mpv/
├── resources/mpv/                    # downloaded mpv.exe + DLLs (gitignored)
├── tests/
│   ├── test_url_validator.py
│   ├── test_config.py
│   ├── test_parser.py                # mocks yt_dlp
│   └── test_mpv_controller.py        # mocks pipe I/O
├── docs/superpowers/{specs,plans}/
├── requirements.txt
├── build.spec                        # PyInstaller onedir build
├── README.md
├── 使用说明.md
├── 快捷键说明.md
└── .gitignore
```

Interfaces locked in:
- `Config` fields: `cookie_path: str`, `default_speed: float`, `default_volume: int`, `window_preset: str`, `always_on_top: bool`, `borderless: bool`, `geometry: str`, `recent_urls: list[str]`.
- `StreamInfo(video_url: str, audio_url: str | None, title: str, duration: float | None, http_headers: dict[str, str])`.
- `MpvController.start(launch_args: list[str])`, `.command(*args, timeout=5) -> any`, `.observe(property, callback)`, `.close()`.

---

## Phase 1 — Mandatory Feasibility Validations (before full UI)

### Task 1: Validation A — Bilibili parsing with yt-dlp

**Files:** Create `tools/parse_probe.py`, `requirements.txt`

- [ ] **Step 1: Install yt-dlp**

Run: `py -m pip install -U yt-dlp pytest`
Expected: `Successfully installed yt-dlp-... pytest-...`

- [ ] **Step 2: Create `requirements.txt`**

```text
PySide6>=6.6
yt-dlp>=2025.1.1
pytest>=8.0
pyinstaller>=6.0
```

- [ ] **Step 3: Create probe script `tools/parse_probe.py`**

```python
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
```

- [ ] **Step 4: Run probe against a real public video**

Run: `py tools/parse_probe.py "https://www.bilibili.com/video/BV1GJ411x7h7"`
Expected: JSON with a non-empty `formats` array; at least one entry has a non-empty `url_head` and either both `vcodec`/`acodec` set (combined) or video-only + audio-only DASH entries.
If HTTP 412 appears: note it, add real Cookie file and retry; record in `docs/验证记录.md`.

- [ ] **Step 5: Record validation A result**

Create `docs/验证记录.md` with the exact command, outcome, format table summary, and any 412/cookie notes.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tools/parse_probe.py docs/验证记录.md
git commit -m "validate(A): yt-dlp resolves public BV URL to direct streams"
```

### Task 2: Validation B — independent mpv window

**Files:** Create `tools/fetch_mpv.py`, `docs/验证记录.md` (append)

- [ ] **Step 1: Create `tools/fetch_mpv.py`**

Downloads the mpv-win64 ZIP (shinichirou/mpv-winbuild releases) into `resources/mpv/`, verifies `mpv.exe` exists, prints the path. Use `urllib.request.urlopen` and `zipfile.ZipFile.extractall`. Default URL:
`https://github.com/shinichirou/mpv-winbuild/releases/latest/download/mpv-x86_64-v3-latest.zip` (fallback: `https://sourceforge.net/projects/mpv-player-windows/files/latest/download`). Accept `--url` override.

```python
import argparse, io, urllib.request, zipfile
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://github.com/shinichirou/mpv-winbuild/releases/latest/download/mpv-x86_64-v3-latest.zip")
    args = ap.parse_args()
    dest = Path(__file__).resolve().parents[1] / "resources" / "mpv"
    dest.mkdir(parents=True, exist_ok=True)
    print("downloading", args.url)
    with urllib.request.urlopen(args.url, timeout=120) as r:
        data = r.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest)
    exe = dest / "mpv.exe"
    if not exe.exists():
        raise SystemExit("mpv.exe not found after extraction")
    print("mpv ready:", exe)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Download mpv**

Run: `py tools/fetch_mpv.py`
Expected: `mpv ready: D:\Asmallvideo\resources\mpv\mpv.exe`
If GitHub release asset URL is wrong: use `web_search` to find the current mpv-winbuild release asset URL and re-run with `--url`.

- [ ] **Step 3: Confirm mpv version and available drag option**

Run: `resources\mpv\mpv.exe --version | Select-Object -First 3` and `resources\mpv\mpv.exe --list-options | Select-String "drag|geometry|osc"`
Expected: version printed; note whether `--window-drag` exists (used in Task 7).

- [ ] **Step 4: Launch an independent borderless window with a real stream**

Get one direct URL from Task 1 (use Python one-liner to print `formats[0]["url"]` for a format with a url), then run:

```powershell
$url = py -c "from yt_dlp import YoutubeDL; i=YoutubeDL({'quiet':True}).extract_info('https://www.bilibili.com/video/BV1GJ411x7h7',download=False); print(next(f['url'] for f in i['formats'] if f.get('url')))"
& 'resources\mpv\mpv.exe' --no-config --idle=yes --force-window=yes --border=no --ontop --keepaspect=yes --geometry=480x270+100+100 --hwdec=auto-safe --http-header-fields='Referer: https://www.bilibili.com/' --input-ipc-server='\\.\pipe\studyfloat_probe' $url
```

Expected: a borderless 480×270 video window appears and plays with picture and sound. Minimize any browser; window remains. Close the terminal that launched it — the window remains (separate process).

- [ ] **Step 5: Append validation B result to `docs/验证记录.md`** (command, observed behavior, screenshot path if taken).

- [ ] **Step 6: Commit** `tools/fetch_mpv.py`, `docs/验证记录.md`, and `.gitignore` excluding `resources/mpv/`.

```gitignore
resources/mpv/
build/
dist/
*.spec.bak
__pycache__/
.pytest_cache/
```

### Task 3: Validation C — IPC control and window flags

**Files:** Create `tools/ipc_probe.py`

- [ ] **Step 1: Create `tools/ipc_probe.py`**

```python
"""Validation C: drive an mpv instance over the named pipe and print responses."""
import json, sys, time

PIPE = r"\\.\pipe\studyfloat_probe"

def connect(timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return open(PIPE, "r+b", buffering=0)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("mpv IPC pipe not available")

p = connect()
rid = 0

def cmd(*args):
    global rid
    rid += 1
    p.write((json.dumps({"command": list(args), "request_id": rid}) + "\n").encode("utf-8"))
    while True:
        msg = json.loads(p.readline().decode("utf-8"))
        if msg.get("request_id") == rid:
            print(args, "->", msg.get("error"), msg.get("data"))
            return msg

cmd("get_property", "pause")
cmd("set_property", "pause", True)
cmd("get_property", "time-pos")
cmd("seek", 5, "relative")
cmd("set_property", "speed", 1.5)
cmd("set_property", "volume", 60)
cmd("set_property", "mute", True)
cmd("get_property", "geometry")
cmd("set_property", "ontop", False)
cmd("set_property", "border", True)
time.sleep(0.5)
cmd("set_property", "border", False)
cmd("set_property", "ontop", True)
print("IPC validation done")
```

- [ ] **Step 2: Run validation C while the mpv window from Task 2 is playing**

Run: `py tools/ipc_probe.py`
Expected: every line ends with `-> success`; geometry returns a string like `480x270+100+100`; `time-pos` returns a number; border/ontop toggles visibly affect the window.

- [ ] **Step 3: Append validation C result to `docs/验证记录.md`** and commit.

**Gate:** Do not proceed to Phase 2 until A, B and C are all recorded as passing. If a validation fails, fix the approach before coding the full app (per spec §13 rule 1).

---

## Phase 2 — Core Modules (TDD)

### Task 4: Project skeleton + Config + typed errors

**Files:** Create `app/__init__.py`, `app/config.py`, `app/player/errors.py`, `tests/test_config.py`, `app/source/__init__.py`, `app/player/__init__.py`, `app/ui/__init__.py`

- [ ] **Step 1: Write failing tests `tests/test_config.py`**

```python
import json
from app.config import Config, DEFAULT_CONFIG_PATH

def test_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DEFAULT_CONFIG_PATH", tmp_path / "config.json")
    c = Config.load()
    assert c.default_speed == 1.0
    assert c.default_volume == 100
    assert c.window_preset == "标准"
    assert c.geometry == "480x270+100+100"
    assert c.borderless is True and c.always_on_top is True

def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DEFAULT_CONFIG_PATH", tmp_path / "config.json")
    c = Config.load()
    c.default_speed = 1.5
    c.cookie_path = "cookies.txt"
    c.recent_urls.append("https://www.bilibili.com/video/BV1GJ411x7h7")
    c.save()
    raw = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert raw["default_speed"] == 1.5
    c2 = Config.load()
    assert c2.cookie_path == "cookies.txt"
    assert c2.recent_urls[-1].endswith("BV1GJ411x7h7")
```

- [ ] **Step 2: Run to verify failure** — `py -m pytest tests/test_config.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement `app/config.py`**

```python
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
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, path: Path | None = None) -> None:
        p = path or DEFAULT_CONFIG_PATH
        p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Implement `app/player/errors.py`**

```python
class StudyFloatError(Exception):
    """Base class for user-facing errors (no stack traces shown to users)."""

class InvalidUrlError(StudyFloatError):
    pass

class ParseError(StudyFloatError):
    """Bilibili parsing failed; message is already user-friendly."""

class CookieRejectedError(ParseError):
    pass

class NetworkError(ParseError):
    pass

class PlayerStartError(StudyFloatError):
    pass

class MpvCommandError(StudyFloatError):
    pass
```

- [ ] **Step 5: Run tests** — `py -m pytest tests/test_config.py -v` → PASS (2 tests).

- [ ] **Step 6: Commit** — `git add app tests && git commit -m "feat: config persistence and typed errors"`

### Task 5: URL validator + Bilibili parser

**Files:** Create `app/source/url_validator.py`, `app/source/bilibili_parser.py`, `tests/test_url_validator.py`, `tests/test_parser.py`

- [ ] **Step 1: Write failing tests `tests/test_url_validator.py`**

```python
import pytest
from app.source.url_validator import normalize_url, InvalidUrl

BV = "BV1GJ411x7h7"

@pytest.mark.parametrize("raw", [
    BV,
    f"https://www.bilibili.com/video/{BV}",
    f"https://b23.tv/{BV}",
    f"  https://www.bilibili.com/video/{BV}/?p=1  ",
    f"www.bilibili.com/video/{BV}",
])
def test_normalize_ok(raw):
    assert normalize_url(raw) == f"https://www.bilibili.com/video/{BV}"

@pytest.mark.parametrize("raw", ["", "https://example.com/watch?v=1", "BV123", "av170001"])
def test_normalize_rejects(raw):
    with pytest.raises(InvalidUrl):
        normalize_url(raw)
```

- [ ] **Step 2: Run to verify failure** — `py -m pytest tests/test_url_validator.py -v` → FAIL.

- [ ] **Step 3: Implement `app/source/url_validator.py`**

```python
from __future__ import annotations
import re
from urllib.parse import urlparse

_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})", re.IGNORECASE)

class InvalidUrl(ValueError):
    pass

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
```

- [ ] **Step 4: Run tests** — `py -m pytest tests/test_url_validator.py -v` → PASS.

- [ ] **Step 5: Write failing tests `tests/test_parser.py`** (mock yt_dlp, no network)

```python
from unittest.mock import patch
import pytest
from app.source.bilibili_parser import BilibiliParser, StreamInfo, ParseError

URL = "https://www.bilibili.com/video/BV1GJ411x7h7"

def _info(formats):
    return {"title": "测试视频", "duration": 610, "http_headers": {"Referer": "https://www.bilibili.com/"},
            "formats": formats}

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

def test_dash_fallback_selects_video_and_audio():
    formats = [
        {"format_id": "v1", "vcodec": "avc1", "acodec": "none", "width": 480, "url": "http://v1"},
        {"format_id": "v2", "vcodec": "avc1", "acodec": "none", "width": 1920, "url": "http://v2"},
        {"format_id": "a1", "vcodec": "none", "acodec": "mp4a", "url": "http://a1"},
    ]
    with patch("app.source.bilibili_parser.YoutubeDL") as ydl:
        ydl.return_value.__enter__.return_value.extract_info.return_value = _info(formats)
        info = BilibiliParser().parse(URL)
    assert info.video_url == "http://v2"
    assert info.audio_url == "http://a1"

def test_no_playable_format_raises_parse_error():
    with patch("app.source.bilibili_parser.YoutubeDL") as ydl:
        ydl.return_value.__enter__.return_value.extract_info.return_value = _info([])
    with pytest.raises(ParseError):
        BilibiliParser().parse(URL)

def test_cookiefile_is_passed(tmp_path):
    cookie = tmp_path / "cookies.txt"; cookie.write_text("# Netscape HTTP Cookie File\n")
    with patch("app.source.bilibili_parser.YoutubeDL") as ydl:
        ydl.return_value.__enter__.return_value.extract_info.return_value = _info(
            [{"format_id": "64", "vcodec": "avc1", "acodec": "mp4a", "url": "http://c"}])
        BilibiliParser(cookie_path=str(cookie)).parse(URL)
    assert ydl.call_args.kwargs["opts"].get("cookiefile") == str(cookie)
```

- [ ] **Step 6: Run to verify failure** — `py -m pytest tests/test_parser.py -v` → FAIL.

- [ ] **Step 7: Implement `app/source/bilibili_parser.py`**

```python
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
        except Exception as exc:  # network/DNS/timeout surfaced by yt-dlp
            raise NetworkError("网络连接失败，请检查网络后重试") from exc

        formats = list(info.get("formats") or [])
        combined = [f for f in formats if _has_video(f) and _has_audio(f)]
        if combined:
            best = max(combined, key=lambda f: (f.get("width") or 0, f.get("height") or 0, f.get("tbr") or 0))
            return StreamInfo(best["url"], None, info.get("title") or "", info.get("duration"),
                              info.get("http_headers") or {})
        videos = [f for f in formats if _has_video(f) and not _has_audio(f)]
        audios = [f for f in formats if _has_audio(f) and not _has_video(f)]
        if videos and audios:
            best_v = max(videos, key=lambda f: (f.get("width") or 0, f.get("height") or 0, f.get("tbr") or 0))
            best_a = max(audios, key=lambda f: f.get("tbr") or 0)
            return StreamInfo(best_v["url"], best_a["url"], info.get("title") or "",
                              info.get("duration"), info.get("http_headers") or {})
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
```

- [ ] **Step 8: Run tests** — `py -m pytest tests -v` → PASS (all).

- [ ] **Step 9: Commit** — `git commit -am "feat: URL validation and decoupled Bilibili parser"`

### Task 6: mpv controller (named-pipe JSON IPC)

**Files:** Create `app/player/mpv_controller.py`, `tests/test_mpv_controller.py`

- [ ] **Step 1: Write failing tests `tests/test_mpv_controller.py`** (fake pipe, no real mpv)

```python
import json, queue, threading
from unittest.mock import patch
from app.player.mpv_controller import MpvController
from app.player.errors import MpvCommandError

class FakePipe:
    def __init__(self):
        self.written = []
        self.inbox = queue.Queue()
        self.closed = False
    def write(self, data): self.written.append(data)
    def readline(self):
        item = self.inbox.get(timeout=3)
        return (json.dumps(item) + "\n").encode()
    def close(self): self.closed = True

def make_controller():
    pipe = FakePipe()
    c = MpvController(mpv_path="mpv.exe", pipe_name="testpipe")
    c._pipe = pipe
    c._start_reader()
    return c, pipe

def test_command_matches_request_id():
    c, pipe = make_controller()
    def answer():
        msg = json.loads(pipe.written[0].decode())
        pipe.inbox.put({"request_id": msg["request_id"], "error": "success", "data": 42})
    threading.Timer(0.05, answer).start()
    assert c.command("get_property", "time-pos") == 42

def test_command_raises_on_error():
    c, pipe = make_controller()
    def answer():
        msg = json.loads(pipe.written[0].decode())
        pipe.inbox.put({"request_id": msg["request_id"], "error": "property unavailable"})
    threading.Timer(0.05, answer).start()
    try:
        c.command("get_property", "nope")
        assert False, "should raise"
    except MpvCommandError:
        pass

def test_observe_receives_property_change():
    c, pipe = make_controller()
    seen = []
    c.observe("time-pos", lambda v: seen.append(v))
    pipe.inbox.put({"event": "property-change", "id": 1, "name": "time-pos", "data": 12.5})
    import time; time.sleep(0.1)
    assert seen == [12.5]
```

- [ ] **Step 2: Run to verify failure** — `py -m pytest tests/test_mpv_controller.py -v` → FAIL.

- [ ] **Step 3: Implement `app/player/mpv_controller.py`**

```python
from __future__ import annotations
import itertools, json, queue, subprocess, threading, time
from pathlib import Path
from typing import Any, Callable

from app.player.errors import MpvCommandError, PlayerStartError

class MpvController:
    """Owns one mpv subprocess and one JSON-IPC named-pipe connection."""

    def __init__(self, mpv_path: str | Path, pipe_name: str, script_dir: Path | None = None):
        self.mpv_path = str(mpv_path)
        self.pipe_name = pipe_name
        self.script_dir = script_dir
        self.proc: subprocess.Popen | None = None
        self._pipe = None
        self._ids = itertools.count(1)
        self._pending: dict[int, queue.Queue] = {}
        self._observers: dict[int, Callable[[Any], None]] = {}
        self._observe_ids: dict[str, int] = {}
        self._write_lock = threading.Lock()
        self._reader: threading.Thread | None = None
        self._closed = False

    @property
    def pipe_path(self) -> str:
        return rf"\\.\pipe\{self.pipe_name}"

    def start(self, launch_args: list[str]) -> None:
        if not Path(self.mpv_path).is_file():
            raise PlayerStartError(f"播放器不存在：{self.mpv_path}")
        cmd = [self.mpv_path, "--no-config", "--idle=yes", "--force-window=yes",
               "--keepaspect=yes", "--hwdec=auto-safe", "--osc=yes",
               f"--input-ipc-server={self.pipe_path}", *launch_args]
        if self.script_dir:
            cmd.insert(1, f"--script={self.script_dir / 'studyfloat.lua'}")
            cmd.insert(1, f"--input-conf={self.script_dir / 'input.conf'}")
        self.proc = subprocess.Popen(cmd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self._connect()

    def _connect(self, timeout: float = 8.0) -> None:
        end = time.time() + timeout
        while time.time() < end:
            try:
                self._pipe = open(self.pipe_path, "r+b", buffering=0)
                break
            except OSError:
                if self.proc and self.proc.poll() is not None:
                    raise PlayerStartError("播放窗口启动失败，请重试")
                time.sleep(0.1)
        else:
            raise PlayerStartError("连接播放窗口超时，请重试")
        self._start_reader()

    def _start_reader(self) -> None:
        self._reader = threading.Thread(target=self._read_loop, daemon=True, name="mpv-ipc-reader")
        self._reader.start()

    def _read_loop(self) -> None:
        while not self._closed:
            try:
                line = self._pipe.readline()
            except OSError:
                break
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if "request_id" in msg:
                q = self._pending.pop(msg["request_id"], None)
                if q: q.put(msg)
            if msg.get("event") == "property-change":
                cb = self._observers.get(msg.get("id"))
                if cb:
                    try: cb(msg.get("data"))
                    except Exception: pass
            if msg.get("event") == "file-loaded" or msg.get("event") == "end-file":
                self._on_playback_event(msg)

    def _on_playback_event(self, msg: dict[str, Any]) -> None:
        # Hook for stream-expiry reload; overridden by the app layer.
        pass

    def _send(self, payload: dict[str, Any]) -> None:
        with self._write_lock:
            self._pipe.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))

    def command(self, *args: Any, timeout: float = 5.0) -> Any:
        rid = next(self._ids)
        q: queue.Queue = queue.Queue()
        self._pending[rid] = q
        self._send({"command": list(args), "request_id": rid})
        try:
            msg = q.get(timeout=timeout)
        except queue.Empty as exc:
            self._pending.pop(rid, None)
            raise MpvCommandError("播放器响应超时") from exc
        if msg.get("error") != "success":
            raise MpvCommandError(str(msg.get("error")))
        return msg.get("data")

    def observe(self, prop: str, callback: Callable[[Any], None]) -> None:
        if prop in self._observe_ids:
            self._observers[self._observe_ids[prop]] = callback
            return
        rid = next(self._ids)
        self._observe_ids[prop] = rid
        self._observers[rid] = callback
        self._send({"command": ["observe_property", rid, prop], "request_id": rid})

    def close(self) -> None:
        self._closed = True
        try:
            if self._pipe: self._pipe.close()
        except OSError:
            pass
        if self.proc and self.proc.poll() is None:
            try: self.command("quit")
            except Exception: self.proc.terminate()
```

- [ ] **Step 4: Run tests** — `py -m pytest tests -v` → PASS.

- [ ] **Step 5: Commit** — `git commit -am "feat: mpv subprocess controller with JSON IPC"`

### Task 7: Geometry persistence + OSC/input resources

**Files:** Create `app/window/__init__.py`, `app/window/geometry.py`, `app/player/resources/studyfloat.lua`, `app/player/resources/input.conf`, `tests/test_geometry.py`

- [ ] **Step 1: Write failing tests `tests/test_geometry.py`**

```python
import re
from app.window.geometry import PRESETS, geometry_for_preset, parse_geometry, save_geometry

def test_presets():
    assert PRESETS["微型"] == (320, 180)
    assert PRESETS["标准"] == (480, 270)

def test_geometry_for_preset():
    assert geometry_for_preset("标准", 100, 100) == "480x270+100+100"

def test_parse_geometry():
    assert parse_geometry("640x360+12+34") == (640, 360, 12, 34)
    assert parse_geometry("garbage") is None

def test_save_geometry_round_trip(tmp_path, monkeypatch):
    from app.window.geometry import GEOMETRY_PATH
    monkeypatch.setattr("app.window.geometry.GEOMETRY_PATH", tmp_path / "geometry.json")
    save_geometry("640x360+12+34")
    assert (tmp_path / "geometry.json").read_text(encoding="utf-8").strip() == "640x360+12+34"
```

- [ ] **Step 2: Run to verify failure** — `py -m pytest tests/test_geometry.py -v` → FAIL.

- [ ] **Step 3: Implement `app/window/geometry.py`**

```python
from __future__ import annotations
import json, re
from pathlib import Path

GEOMETRY_PATH = Path("geometry.json")
PRESETS = {"微型": (320, 180), "小型": (400, 225), "标准": (480, 270), "大型": (640, 360)}
_GEOM_RE = re.compile(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)")

def geometry_for_preset(name: str, x: int = 100, y: int = 100) -> str:
    w, h = PRESETS.get(name, PRESETS["标准"])
    return f"{w}x{h}+{x}+{y}"

def parse_geometry(value: str | None) -> tuple[int, int, int, int] | None:
    if not value: return None
    m = _GEOM_RE.search(value)
    if not m: return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))

def save_geometry(value: str, path: Path | None = None) -> None:
    p = path or GEOMETRY_PATH
    p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

def load_geometry(path: Path | None = None) -> str | None:
    p = path or GEOMETRY_PATH
    if not p.exists(): return None
    try: return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return None
```

- [ ] **Step 4: Implement `app/player/resources/studyfloat.lua`**

```lua
-- StudyFloat: keep mpv's OSC minimal and allow dragging the borderless window.
local mp = require 'mp'

mp.set_property('osc', 'yes')
mp.commandv('script-message-to', 'osc', 'set', 'visibility', 'auto')

-- OSC auto-hide after ~2s; small bottom bar.
mp.set_property('script-opts', 'osc-visibility=auto,osc-hidetimeout=2000,osc-layout=bottombar,osc-timetotal=no')

local dragging = false
local last_x, last_y = 0, 0

local function geometry_parts()
  local g = mp.get_property('geometry') or ''
  local w, h, x, y = g:match('(%d+)x(%d+)([+-]%d+)([+-]%d+)')
  if not w then return 480, 270, 100, 100 end
  return tonumber(w), tonumber(h), tonumber(x), tonumber(y)
end

local function mouse()
  local pos = mp.get_property_native('mouse-pos')
  return pos and pos.x or 0, pos and pos.y or 0
end

mp.add_forced_key_binding('MOUSE_BTN0', 'sf_drag_start', function()
  if mp.get_property_native('pause') == nil then return end
  last_x, last_y = mouse()
  dragging = true
end)

mp.add_forced_key_binding('MOUSE_BTN0_UP', 'sf_drag_end', function()
  dragging = false
end)

mp.register_event('mouse-pos', function(pos)
  if not dragging then return end
  local w, h, gx, gy = geometry_parts()
  local nx, ny = gx + (pos.x - last_x), gy + (pos.y - last_y)
  last_x, last_y = pos.x, pos.y
  mp.set_property('geometry', string.format('%dx%d+%d+%d', w, h, nx, ny))
end)

mp.add_key_binding('MBTN_RIGHT', 'sf_menu', function()
  mp.osd_message('StudyFloat: Space 播放/暂停 · ←→ 快进快退 · [ ] 倍速 · F 全屏', 2)
end)
```

- [ ] **Step 5: Implement `app/player/resources/input.conf`**

```text
SPACE cycle pause
LEFT seek -5
RIGHT seek 5
UP add volume 5
DOWN add volume -5
m cycle mute
[ multiply speed 1/1.25
] multiply speed 1.25
f cycle fullscreen
ESC set fullscreen no
q quit
w write-watch-later-config
```

- [ ] **Step 6: Run tests** — `py -m pytest tests -v` → PASS. Commit.

> During execution, verify on the real mpv build that `mouse-pos` events and `geometry` setters actually move the borderless window. If the Lua drag path is unsupported by the downloaded mpv version, replace it with a ctypes Win32 helper in `app/window/drag_win32.py` that moves the mpv HWND (found via `GetWindowRect`/`FindWindowW`) while the left button is held, bound through IPC script-messages. Record the chosen approach in `docs/验证记录.md`.

### Task 8: PySide6 launcher + settings UI

**Files:** Create `app/ui/launcher.py`, `app/ui/settings_dialog.py`

- [ ] **Step 1: Implement `app/ui/settings_dialog.py`**

```python
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QCheckBox, QComboBox,
                               QSpinBox, QDoubleSpinBox, QPushButton, QFileDialog, QLabel)
from PySide6.QtCore import Qt
from app.config import Config

SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("StudyFloat 设置")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        form = QFormLayout(self)

        self.cookie = QLineEdit(config.cookie_path)
        cookie_btn = QPushButton("选择 Cookie 文件")
        cookie_btn.clicked.connect(self._pick_cookie)
        form.addRow(QLabel("Cookie 文件（Netscape 格式，可选）"), self.cookie)
        form.addRow(cookie_btn)

        self.speed = QDoubleSpinBox(); self.speed.setDecimals(2); self.speed.setSingleStep(0.25)
        self.speed.setRange(0.5, 2.0); self.speed.setValue(config.default_speed)
        form.addRow("默认倍速", self.speed)

        self.volume = QSpinBox(); self.volume.setRange(0, 100); self.volume.setValue(config.default_volume)
        form.addRow("默认音量", self.volume)

        self.preset = QComboBox(); self.preset.addItems(["微型", "小型", "标准", "大型", "自定义"])
        self.preset.setCurrentText(config.window_preset)
        form.addRow("窗口预设", self.preset)

        self.ontop = QCheckBox("窗口置顶"); self.ontop.setChecked(config.always_on_top)
        self.borderless = QCheckBox("无边框"); self.borderless.setChecked(config.borderless)
        form.addRow(self.ontop); form.addRow(self.borderless)

        save = QPushButton("保存"); save.clicked.connect(self._save)
        form.addRow(save)

    def _pick_cookie(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Cookie 文件", "", "Text files (*.txt)")
        if path: self.cookie.setText(path)

    def _save(self):
        self.config.cookie_path = self.cookie.text().strip()
        self.config.default_speed = self.speed.value()
        self.config.default_volume = self.volume.value()
        self.config.window_preset = self.preset.currentText()
        self.config.always_on_top = self.ontop.isChecked()
        self.config.borderless = self.borderless.isChecked()
        self.config.save()
        self.accept()
```

- [ ] **Step 2: Implement `app/ui/launcher.py`**

```python
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                               QHBoxLayout, QMessageBox)
from PySide6.QtCore import Qt, Signal
from app.config import Config
from app.ui.settings_dialog import SettingsDialog

class Launcher(QWidget):
    play_requested = Signal(str)

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.setWindowTitle("StudyFloat")
        self.setFixedWidth(460)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("StudyFloat"))
        layout.addWidget(QLabel("输入或粘贴 Bilibili 视频链接 / BV 号"))
        self.url = QLineEdit(); self.url.setPlaceholderText("https://www.bilibili.com/video/BV...")
        self.url.returnPressed.connect(self._emit_play)
        layout.addWidget(self.url)
        self.error = QLabel(""); self.error.setStyleSheet("color: #c62828;")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        row = QHBoxLayout()
        play = QPushButton("播放"); play.clicked.connect(self._emit_play)
        settings = QPushButton("设置"); settings.clicked.connect(self._open_settings)
        row.addWidget(play); row.addWidget(settings)
        layout.addLayout(row)
        self.url.setFocus()

    def show_error(self, message: str):
        self.error.setText(message)

    def clear_error(self):
        self.error.setText("")

    def _emit_play(self):
        self.clear_error()
        self.play_requested.emit(self.url.text())

    def _open_settings(self):
        SettingsDialog(self.config, self).exec()
```

- [ ] **Step 3: Commit** — `git commit -am "feat: minimal launcher and settings UI"`

### Task 9: main.py wiring (end-to-end)

**Files:** Create `app/main.py`

- [ ] **Step 1: Implement `app/main.py`**

```python
from __future__ import annotations
import sys, uuid
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from app.config import Config
from app.player.errors import InvalidUrlError, ParseError, PlayerStartError, StudyFloatError
from app.player.mpv_controller import MpvController
from app.source.bilibili_parser import BilibiliParser
from app.source.url_validator import normalize_url, InvalidUrl
from app.ui.launcher import Launcher
from app.window.geometry import geometry_for_preset, load_geometry, save_geometry, parse_geometry

APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
MPV_PATH = APP_DIR / "resources" / "mpv" / "mpv.exe"
SCRIPT_DIR = APP_DIR / "app" / "player" / "resources"

def app_data_path(name: str) -> Path:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    return base / name

def main() -> None:
    app = QApplication(sys.argv)
    config = Config.load(app_data_path("config.json"))
    window = Launcher(config)
    player: MpvController | None = None
    parser = BilibiliParser(config.cookie_path)

    def on_play(raw: str):
        nonlocal player, parser
        try:
            url = normalize_url(raw)
        except InvalidUrl as exc:
            window.show_error(str(exc)); return
        window.show_error("正在解析视频…")
        QApplication.processEvents()
        parser = BilibiliParser(config.cookie_path)
        try:
            stream = parser.parse(url)
        except ParseError as exc:
            window.show_error(str(exc)); return
        except Exception:
            window.show_error("视频解析失败，请稍后重试"); return

        geo = load_geometry(app_data_path("geometry.json")) or geometry_for_preset(config.window_preset)
        if player is not None:
            player.close(); player = None
        try:
            player = MpvController(MPV_PATH, f"studyfloat_{uuid.uuid4().hex[:8]}", SCRIPT_DIR)
            launch = [f"--geometry={geo}", f"--volume={config.default_volume}",
                      f"--speed={config.default_speed}",
                      "--ontop" if config.always_on_top else "--no-ontop",
                      "--no-border" if config.borderless else "--border"]
            headers = stream.http_headers or {}
            if headers:
                fields = ",".join(f"{k}: {v}" for k, v in headers.items() if v)
                launch.append(f"--http-header-fields={fields}")
            player.start(launch)
            player.command("loadfile", stream.video_url, "replace")
            if stream.audio_url:
                player.command("audio-add", stream.audio_url, "external", "audio")
            player.command("set_property", "pause", False)
            player.observe("geometry", lambda g: save_geometry(g, app_data_path("geometry.json")) if g else None)
            config.recent_urls = [u for u in config.recent_urls if u != url][:9]
            config.recent_urls.insert(0, url)
            config.save(app_data_path("config.json"))
        except StudyFloatError as exc:
            window.show_error(str(exc)); return
        window.clear_error()
        window.showMinimized()

    window.play_requested.connect(on_play)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

> Note: `Config.save()` and `Config.load()` accept an optional `Path` (already implemented) — `main.py` passes `app_data_path(...)`. If Task 4 implemented only no-arg signatures, update them to accept `path: Path | None = None`.

- [ ] **Step 2: Run full test suite** — `py -m pytest tests -v` → PASS.

- [ ] **Step 3: Manual smoke run** — `py -m app.main`, paste a real BV URL, click 播放. Expected: a borderless always-on-top 480×270 window plays the video; OSC appears on mouse move and hides after ~2s; Space/arrows/[ ]/F shortcuts work; launcher minimizes; browser can be closed and video keeps playing.

- [ ] **Step 4: Commit** — `git commit -am "feat: wire launcher, parser and mpv player end-to-end"`

---

## Phase 3 — Packaging and Documentation

### Task 10: PyInstaller portable build

**Files:** Create `build.spec`, `.gitignore` (update)

- [ ] **Step 1: Create `build.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("PySide6", "yt_dlp"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

datas += [
    ("app/player/resources/studyfloat.lua", "app/player/resources"),
    ("app/player/resources/input.conf", "app/player/resources"),
]
binaries += [("resources/mpv/mpv.exe", "resources/mpv")]
from pathlib import Path
for dll in Path("resources/mpv").glob("*.dll"):
    binaries.append((str(dll), "resources/mpv"))

a = Analysis(
    ["app/main.py"], pathex=["."], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="StudyFloat",
          debug=False, bootloader_ignore_signals=False, strip=False,
          upx=False, console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name="StudyFloat")
```

- [ ] **Step 2: Build**

Run: `py -m PyInstaller build.spec --noconfirm`
Expected: `dist/StudyFloat/StudyFloat.exe` plus bundled PySide6/yt-dlp/mpv files.

- [ ] **Step 3: Verify portable run** — copy `dist/StudyFloat` to a fresh folder (no Python installed assumption), launch `StudyFloat.exe`, play a real BV URL. Confirm mpv window plays with no missing-DLL dialog.

- [ ] **Step 4: Commit build script and docs; keep `dist/` out of git** (already in `.gitignore`).

### Task 11: Documentation and final verification

**Files:** Create `README.md`, `使用说明.md`, `快捷键说明.md`, `docs/功能清单.md`, append `docs/验证记录.md`

- [ ] **Step 1: README.md** — project intro, tech-stack rationale (link spec §3), quick start (green folder → `StudyFloat.exe`), directory layout, build step (`py -m PyInstaller build.spec --noconfirm`), dev run (`py -m app.main`), tests (`py -m pytest tests -v`), dependency list (`requirements.txt`), known issues (B站反爬/412/清晰度限制/直链过期/杀毒误报/Cookie 用法), and P1/P2 backlog.

- [ ] **Step 2: 使用说明.md** — step-by-step: 获取 BV 号/链接 → 粘贴 → 播放 → 窗口操作（拖动/缩放/置顶/无边框）→ 悬停控制层 → 设置 Cookie（Netscape 格式，浏览器导出）→ 重新解析 → 关闭窗口。

- [ ] **Step 3: 快捷键说明.md** — table of Space/←/→/↑/↓/M/[/]/F/Esc/q with functions.

- [ ] **Step 4: docs/功能清单.md** — check P0 features from spec §5; list P1/P2 as 未完成; 已知问题 from spec §11.

- [ ] **Step 5: Final verification** — run every acceptance item in spec §9 and record pass/fail in `docs/验证记录.md`; commit.

---

## Self-Review (completed during plan authoring)

- **Spec coverage:** §4 modules → Tasks 4–9; §5 features → Tasks 5–9; §7 errors → Task 5 (classifier) + Task 9 (UI display); §8 validations A/B/C → Tasks 1–3; §9 acceptance → Task 11; §10 deliverables → Tasks 10–11; §11 risks → Task 11 docs + §7/§8 mitigations. No gaps.
- **Placeholders:** none (the mpv drag fallback is a concrete conditional with an exact file and approach).
- **Type consistency:** `Config.load(path)`/`save(path)` signature used in both Task 4 and Task 9 — maintained; `StreamInfo` fields identical in Task 5 and Task 9; `MpvController.start/command/observe/close` identical in Tasks 6 and 9.
