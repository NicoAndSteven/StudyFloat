from __future__ import annotations

import sys
import threading
import uuid

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication

from app.config import Config
from app.gc_policy import MainThreadGC
from app.paths import QR_COOKIE_FILE, app_dir, data_path
from app.qt_lifecycle import retire
from app.player.errors import ParseError, PlayerStartError, StudyFloatError
from app.player.mpv_controller import MpvController
from app.source.url_validator import InvalidUrl, normalize_url
from app.ui.launcher import Launcher
from app.ui.part_picker_dialog import PartPickerDialog
from app.ui.qr_login_dialog import QRLoginDialog
from app.ui.theme import app_font
from app.window.geometry import geometry_for_preset, load_geometry, save_geometry


# ---------------------------------------------------------------------------
# 崩溃诊断。windowed 打包后没有 stderr，任何未捕获异常 / Qt fatal / 原生崩溃
# 的表现都是「窗口直接消失」。全部致命信息必须落到 exe 旁的 studyfloat.log。
# ---------------------------------------------------------------------------
def _setup_diagnostics() -> None:
    import faulthandler
    import threading
    import time as _time
    import traceback as _tb

    log_path = data_path("studyfloat.log")
    try:
        if log_path.exists() and log_path.stat().st_size > 2_000_000:
            log_path.unlink()
        stream = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")
    except OSError:
        return

    def _stamp(message: str) -> None:
        stream.write(f"\n[{_time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        stream.flush()

    try:
        import PySide6

        version_note = f"PySide6={PySide6.__version__}"
    except Exception:
        version_note = "version=unknown"
    _stamp(f"启动 frozen={getattr(sys, 'frozen', False)} {version_note}")

    # 原生崩溃（访问冲突 / abort / qFatal）在进程被杀前把所有线程的
    # Python 调用栈写进日志 —— 这是定位「直接消失」的唯一手段。
    faulthandler.enable(stream)

    def _sys_hook(exc_type, exc_value, exc_tb) -> None:
        _stamp("主线程未捕获异常:\n" + "".join(_tb.format_exception(exc_type, exc_value, exc_tb)))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _sys_hook

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        _stamp(
            f"后台线程未捕获异常 ({args.thread}):\n"
            + "".join(_tb.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        )

    threading.excepthook = _thread_hook

    def _qt_handler(mode, context, message) -> None:
        where = ""
        try:
            if context.file:
                where = f" ({context.file}:{context.function or '?'}:{context.line})"
        except Exception:
            pass
        _stamp(f"Qt[mode={int(mode)}] {message}{where}")

    from PySide6.QtCore import qInstallMessageHandler

    qInstallMessageHandler(_qt_handler)


class _ParseWorker(QThread):
    """解析全部在后台线程完成：分P列表抓取、选择、取流都不再阻塞 UI。

    多P视频通过 need_part -> answer_* 在线程与主线程之间同步：
    主线程弹出分P列表，用户的选择经 answer_* 唤醒本线程继续解析。
    """

    parsed = Signal(object)
    failed = Signal(str)
    need_part = Signal(object, int)  # (分P列表, 默认高亮页码)
    part_cancelled = Signal()

    def __init__(self, url: str, raw: str, cookie_path: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.raw = raw
        self.cookie_path = cookie_path
        self._part_event = threading.Event()
        self._choice = "cancel"  # cancel | skip | play
        self._chosen_page = 1

    def answer_play(self, page: int) -> None:
        self._choice = "play"
        self._chosen_page = page
        self._part_event.set()

    def answer_skip(self) -> None:
        """分P窗口异常时退回原链接直接解析。"""
        self._choice = "skip"
        self._part_event.set()

    def answer_cancel(self) -> None:
        self._choice = "cancel"
        self._part_event.set()

    def run(self) -> None:
        url = self.url
        try:
            bvid = _extract_bvid(url)
            if bvid:
                try:
                    from app.source.bilibili_parts import (
                        decide_selection,
                        fetch_parts,
                        pick_part_url,
                    )

                    parts = fetch_parts(bvid)
                    selection = decide_selection(parts, self.raw)
                    if selection.show_picker:
                        self.need_part.emit(parts, selection.highlight_page)
                        if not self._part_event.wait(timeout=180):
                            self.part_cancelled.emit()
                            return
                        if self._choice == "cancel":
                            self.part_cancelled.emit()
                            return
                        if self._choice == "play":
                            url = pick_part_url(url, self._chosen_page)
                        # choice == "skip"：按原链接继续
                except Exception:
                    # 拿不到分P列表时退回原 URL，不让登录/网络问题阻断播放
                    pass

            from app.source.bilibili_parser import BilibiliParser

            stream = BilibiliParser(self.cookie_path).parse(url)
        except ParseError as exc:
            self.failed.emit(str(exc))
            return
        except Exception:
            self.failed.emit("视频解析失败，请检查链接或稍后重试")
            return
        self.parsed.emit(stream)


class _Dispatcher(QObject):
    """把后台线程的结果排队回主线程执行。"""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    @Slot(object)
    def call(self, value) -> None:
        self._callback(value)


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


def main() -> None:
    _setup_diagnostics()
    app = QApplication(sys.argv)
    app.setFont(app_font())
    # 解析线程里的 yt-dlp/curl 会频繁分配内存；绝不能让 CPython 的自动
    # 循环 GC 在后台线程里回收 QWidget 引用环（否则 Qt 对象会在错误线程
    # 被销毁，进程直接消失）。改为只在主线程按阈值回收。
    gc_guard = MainThreadGC(app)
    gc_guard.start()
    config = Config.load(data_path("config.json"))
    window = Launcher(config)
    player: MpvController | None = None
    parse_worker: _ParseWorker | None = None

    def play_stream(url: str, stream) -> None:
        nonlocal player
        # 解析结束、播放开始是一个安全时点：清掉上一轮对话框等垃圾，
        # 避免它们一直堆积到解析线程的下一次分配。
        gc_guard.collect_now()
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

    def on_need_part(worker: _ParseWorker, parts, highlight_page: int) -> None:
        """后台线程抓到多P列表后，在主线程弹选择窗口。"""
        dialog = None
        try:
            dialog = PartPickerDialog(parts, highlight_page=highlight_page)
            picked = dialog.selected_part if dialog.exec() else None
        except Exception:
            window.show_error("分P列表窗口异常，按原链接解析")
            worker.answer_skip()
            return
        finally:
            if dialog is not None:
                retire(dialog)
        if picked is not None:
            worker.answer_play(picked.page)
        else:
            worker.answer_cancel()
        gc_guard.collect_now()

    def on_parse_finished(worker_obj: _ParseWorker) -> None:
        nonlocal parse_worker
        if parse_worker is worker_obj:
            parse_worker = None
        worker_obj._dispatcher = None
        # QThread 对象本身也确定性释放，别留给定时的循环 GC。
        retire(worker_obj)

    def on_play(raw: str):
        nonlocal parse_worker
        try:
            url = normalize_url(raw)
        except InvalidUrl as exc:
            window.show_error(str(exc))
            return
        except Exception:
            window.show_error("链接格式无法识别，请检查后重试")
            return

        if parse_worker is not None and parse_worker.isRunning():
            window.show_info("正在解析，请稍候…")
            return

        # 开始解析前是安全时点：把已关闭窗口的引用环在主线程清掉。
        gc_guard.collect_now()
        window.show_info("正在解析视频…")
        worker = _ParseWorker(url, raw, effective_cookie_path(config))
        dispatcher = _Dispatcher(lambda stream: play_stream(url, stream))
        worker._dispatcher = dispatcher  # keep the main-thread bridge alive
        worker.parsed.connect(dispatcher.call, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(window.show_error, Qt.ConnectionType.QueuedConnection)
        worker.need_part.connect(
            lambda parts, highlight, w=worker: on_need_part(w, parts, highlight),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.part_cancelled.connect(window.clear_error, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(
            lambda w=worker: on_parse_finished(w), Qt.ConnectionType.QueuedConnection
        )
        worker.finished.connect(gc_guard.collect_if_needed, Qt.ConnectionType.QueuedConnection)
        parse_worker = worker
        worker.start()

    def on_login():
        dialog = QRLoginDialog(str(data_path(QR_COOKIE_FILE)))
        window._login_dialog = dialog  # 线程未结束时由对话框自己保活，防 GC 提前销毁
        accepted = False
        try:
            accepted = bool(dialog.exec())
        finally:
            # 确定性释放：线程已停就立即 deleteLater；还在退出中就等
            # thread.finished 后再删。绝不把销毁时机交给 GC。
            dialog.dispose()
            window._login_dialog = None
            gc_guard.collect_now()
        if accepted:
            window.show_login_status("已登录，播放时自动使用登录态")
        else:
            # 失败详情已在对话框内显示；这里只给一句简短提示
            window.show_login_status("扫码未完成，可稍后重试", is_error=True)

    window.play_requested.connect(on_play)
    window.login_requested.connect(on_login)
    if data_path(QR_COOKIE_FILE).is_file():
        window.show_login_status("已登录（扫码登录态有效）")

    def shutdown_parse() -> None:
        from app.ui.qr_login_dialog import shutdown_pending_logins

        shutdown_pending_logins()
        if parse_worker is not None and parse_worker.isRunning():
            parse_worker.terminate()
            parse_worker.wait(1000)

    app.aboutToQuit.connect(shutdown_parse)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
