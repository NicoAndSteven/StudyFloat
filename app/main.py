from __future__ import annotations

import sys
import uuid
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.config import Config
from app.player.errors import ParseError, PlayerStartError, StudyFloatError
from app.player.mpv_controller import MpvController
from app.source.bilibili_parser import BilibiliParser
from app.source.bilibili_parts import fetch_parts, is_multi_part, pick_part_url
from app.source.url_validator import InvalidUrl, normalize_url
from app.ui.launcher import Launcher
from app.ui.part_picker_dialog import PartPickerDialog
from app.ui.qr_login_dialog import QRLoginDialog
from app.window.geometry import geometry_for_preset, load_geometry, save_geometry


def app_dir() -> Path:
    """Root of the bundled app (PyInstaller _MEIPASS or project root in dev)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def data_path(name: str) -> Path:
    """Settings/config files live beside the executable (or cwd in dev)."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    return base / name


QR_COOKIE_FILE = "qr_cookies.txt"


def effective_cookie_path(config: Config) -> str:
    """扫码保存的登录态优先，其次手动设置的 cookie 文件。"""
    qr = data_path(QR_COOKIE_FILE)
    if qr.is_file():
        return str(qr)
    return config.cookie_path


def _extract_bvid(url: str) -> str:
    """从规范化 URL 里取 BV 号。"""
    import re
    m = re.search(r"(BV[0-9A-Za-z]{10})", url)
    return m.group(1) if m else ""


def resolve_part(url: str, raw: str, parent) -> str | None:
    """合辑处理：链接已带 p=N 则直接用；否则弹分P选择框。

    返回最终要解析的 URL；用户取消返回 None。
    """
    # 用户明确指定了分P（如 &p=18），尊重其意图，直接播放。
    from urllib.parse import parse_qs, urlparse
    if parse_qs(urlparse(raw).query).get("p"):
        return url
    bvid = _extract_bvid(url)
    if not bvid:
        return url
    try:
        parts = fetch_parts(bvid)
    except Exception:
        return url  # 拿不到分P列表时退回原 URL，不让登录/网络问题阻断播放
    if not is_multi_part(parts):
        return url
    dialog = PartPickerDialog(parts, parent=parent)
    if dialog.exec() and dialog.selected_part is not None:
        return pick_part_url(url, dialog.selected_part)
    return None  # 用户取消


def main() -> None:
    app = QApplication(sys.argv)
    config = Config.load(data_path("config.json"))
    window = Launcher(config)
    player: MpvController | None = None

    def on_play(raw: str):
        nonlocal player
        try:
            url = normalize_url(raw)
        except InvalidUrl as exc:
            window.show_error(str(exc))
            return

        # 合辑：让用户选择分P（链接已带 p=N 则跳过）
        url = resolve_part(url, raw, window)
        if url is None:
            window.clear_error()
            return

        window.show_error("正在解析视频…")
        QApplication.processEvents()

        parser = BilibiliParser(effective_cookie_path(config))
        try:
            stream = parser.parse(url)
        except ParseError as exc:
            window.show_error(str(exc))
            return
        except Exception:
            window.show_error("视频解析失败，请检查链接或稍后重试")
            return

        geo = load_geometry(data_path("geometry.json")) or geometry_for_preset(config.window_preset)
        if player is not None:
            player.close()
            player = None

        succeeded = False
        try:
            launch = [
                f"--geometry={geo}",
                f"--volume={config.default_volume}",
                f"--speed={config.default_speed}",
                "--ontop" if config.always_on_top else "--no-ontop",
                "--no-border" if config.borderless else "--border",
                "--window-dragging=yes",
            ]
            headers = stream.http_headers or {}
            if headers:
                fields = ",".join(f"{k}: {v}" for k, v in headers.items() if v)
                launch.append(f"--http-header-fields={fields}")

            player = MpvController(
                app_dir() / "resources" / "mpv" / "mpv.exe",
                f"studyfloat_{uuid.uuid4().hex[:8]}",
                app_dir() / "app" / "player" / "resources",
            )
            player.start(launch)

            # loadfile replies before the file is actually ready; poll until
            # mpv reports a real path before touching playback properties.
            player.command("loadfile", stream.video_url, "replace")
            import time as _time
            ready = False
            for _ in range(20):
                try:
                    if player.command("get_property", "path", timeout=1):
                        ready = True
                        break
                except Exception:
                    pass
                _time.sleep(0.15)
            if not ready:
                raise PlayerStartError("视频加载超时，请重试")

            if stream.audio_url:
                # Validation C: mpv's audio-add takes exactly (url) — extra flags
                # like "external" return "invalid parameter".
                player.command("audio-add", stream.audio_url)
            player.command("set_property", "pause", False)
            player.command("set_property", "speed", config.default_speed)
            player.command("set_property", "volume", config.default_volume)

            # Persist window geometry whenever mpv reports a change.
            player.observe("geometry", lambda g: save_geometry(g, data_path("geometry.json")) if g else None)

            config.recent_urls = [u for u in config.recent_urls if u != url][:9]
            config.recent_urls.insert(0, url)
            config.save(data_path("config.json"))
            succeeded = True
        except StudyFloatError as exc:
            window.show_error(str(exc))
            return
        except Exception:
            window.show_error("播放窗口启动失败，请重试")
            return
        finally:
            if not succeeded and player is not None:
                player.close()
                player = None

        window.clear_error()
        window.showMinimized()

    def on_login():
        dialog = QRLoginDialog(str(data_path(QR_COOKIE_FILE)), window)
        if dialog.exec():
            window.show_login_status("已登录，播放时自动使用登录态")
        else:
            # 失败详情已在对话框内显示；这里只给一句简短提示
            window.show_login_status("扫码未完成，可稍后重试", is_error=True)

    window.play_requested.connect(on_play)
    window.login_requested.connect(on_login)
    if data_path(QR_COOKIE_FILE).is_file():
        window.show_login_status("已登录（扫码登录态有效）")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
