"""扫码登录窗口 —— 一张二维码卡片。

二维码必须白底黑码（不跟深色主题走），所以视觉上是深色窗口里的一块亮面。
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.qt_lifecycle import retire
from app.ui.theme import DANGER, DIM, FAINT, TEXT, apply_opaque_shell, apply_theme
from app.ui.widgets import BrandMark, GlyphButton, Hairline


class _QRWidget(QWidget):
    """用 QPainter 直接绘制 qrcode 布尔矩阵，无图片/IO 依赖。"""

    def __init__(self):
        super().__init__()
        self._matrix: list[list[bool]] = []
        self.setFixedSize(212, 212)
        self.setStyleSheet("background: white;")

    def set_url(self, url: str):
        import qrcode

        qr = qrcode.QRCode(border=2, box_size=1)
        qr.add_data(url)
        qr.make(fit=True)
        self._matrix = qr.get_matrix()
        self.update()

    def paintEvent(self, event):
        if not self._matrix:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.white)
        n = len(self._matrix)
        cell = min(self.width(), self.height()) / n
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("black"))
        for r, row in enumerate(self._matrix):
            for c, dark in enumerate(row):
                if dark:
                    painter.drawRect(
                        int(c * cell), int(r * cell), int(cell + 0.6), int(cell + 0.6)
                    )
        painter.end()


class _LoginWorker(QObject):
    qr_ready = Signal(str)
    status = Signal(str)
    success = Signal(dict)
    failed = Signal(str)

    def __init__(self, cookie_path: str):
        super().__init__()
        self.cookie_path = cookie_path
        self._stop_event = threading.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self):
        login = None
        try:
            from app.source.bili_login import BiliQRLogin, LoginCancelled, cookies_to_netscape

            login = BiliQRLogin()
            result = login.login(
                on_qr=lambda url: self.qr_ready.emit(url),
                on_status=lambda msg: self.status.emit(msg),
                stop_event=self._stop_event,
            )
            cookies_to_netscape(result.cookies, self.cookie_path)
            self.success.emit(result.cookies)
        except LoginCancelled:
            # 用户已关闭窗口，静默退出；不要发 failed 覆盖界面状态
            pass
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            # 必须在本线程内关闭 curl 会话，绝不能让 Curl.__del__ 在线程
            # 退出阶段被 GC 触发（那是日志里另一条崩溃栈）。
            if login is not None:
                login.close()


# 线程还在退出、但窗口已经关闭的对话框。持有强引用，避免 Python GC
# 在登录线程结束前把 QWidget/QThread 一起回收（Qt 会 qFatal 或访问冲突）。
_KEEP_ALIVE: set["QRLoginDialog"] = set()


def shutdown_pending_logins(timeout_ms: int = 3000) -> None:
    """应用退出前尽力停止仍在收尾的登录线程。"""
    for dialog in list(_KEEP_ALIVE):
        try:
            if dialog._stop_worker(timeout_ms=timeout_ms):
                dialog._cleanup()
        except Exception:
            _KEEP_ALIVE.discard(dialog)


class QRLoginDialog(QFrame):
    def __init__(self, cookie_path: str, parent=None, start_worker: bool = True):
        super().__init__(parent)
        self.cookie_path = cookie_path
        self.setWindowTitle("StudyFloat 扫码登录")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setFixedSize(340, 520)
        self._result = False
        self._centered = False
        self._drag_pos = None
        self._disposed = False
        self._retired = False
        self._loop = None

        shell = QVBoxLayout(self)
        # 卡片铺满窗口：外层留白会在窗口边缘露出一圈色差 padding，且不可交互
        shell.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("window")
        card.setAttribute(Qt.WA_StyledBackground, True)
        shell.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(9)
        header.addWidget(BrandMark(18), 0, Qt.AlignVCenter)
        title = QLabel("扫码登录")
        title.setObjectName("dialogTitle")
        header.addWidget(title, 0, Qt.AlignVCenter)
        header.addStretch(1)
        close = GlyphButton("close")
        close.clicked.connect(self.close)
        header.addWidget(close, 0, Qt.AlignTop)
        layout.addLayout(header)
        layout.addSpacing(14)

        tip = QLabel("用手机 B站 App 扫描二维码并确认")
        tip.setObjectName("qrTip")
        tip.setAlignment(Qt.AlignCenter)
        layout.addWidget(tip)
        layout.addSpacing(16)

        qr_box = QFrame()
        qr_box.setObjectName("qrBox")
        qr_box.setFixedSize(236, 236)
        qr_layout = QVBoxLayout(qr_box)
        qr_layout.setContentsMargins(12, 12, 12, 12)
        self.qr = _QRWidget()
        qr_layout.addWidget(self.qr)
        layout.addWidget(qr_box, 0, Qt.AlignHCenter)

        layout.addSpacing(16)
        self.status = QLabel("正在生成二维码…")
        self.status.setObjectName("qrStatus")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addSpacing(6)
        note = QLabel("登录态仅保存在本机，不会上传")
        note.setObjectName("note")
        note.setAlignment(Qt.AlignCenter)
        layout.addWidget(note)
        layout.addStretch(1)

        layout.addWidget(Hairline())
        layout.addSpacing(14)
        cancel = QPushButton("取消")
        cancel.setObjectName("ghost")
        cancel.setFixedHeight(34)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.close)
        layout.addWidget(cancel)

        self._apply_style()
        apply_opaque_shell(self, card)

        self._thread = QThread(self)
        self._worker = _LoginWorker(cookie_path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        # Qt 官方推荐的生命周期：线程结束时让 worker 在自己线程里 deleteLater，
        # 避免跨线程析构 QObject。
        self._thread.finished.connect(self._worker.deleteLater)
        self._worker.qr_ready.connect(self.qr.set_url)
        self._worker.status.connect(self._set_status)
        self._worker.success.connect(self._on_success)
        self._worker.failed.connect(self._on_failed)
        if start_worker:
            self._thread.start()

    def _apply_style(self) -> None:
        apply_theme(self)
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QFrame#window {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #14110F, stop:0.45 #0E0C0B, stop:1 #0B0A09);
                border: 1px solid #302A24;
                border-radius: 8px;
            }}
            QLabel#dialogTitle {{ color: {TEXT}; font-size: 15px; font-weight: 600; }}
            QLabel#qrTip {{ color: {DIM}; font-size: 11px; }}
            QLabel#qrStatus {{ color: {DIM}; font-size: 11px; }}
            QFrame#qrBox {{
                background: #FFFFFF; border: 1px solid #3A332B;
                border-radius: 12px;
            }}
            """
        )

    def _set_status(self, text: str) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {DIM}; font-size: 11px;")

    def exec(self):
        import PySide6.QtCore as _c

        loop = _c.QEventLoop()
        self._loop = loop
        self._result = False
        self.show()
        self.raise_()
        self.activateWindow()
        loop.exec()
        return self._result

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if self._centered:
            return
        self._centered = True
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.move(
                avail.left() + (avail.width() - self.width()) // 2,
                avail.top() + (avail.height() - self.height()) // 2,
            )

    def mousePressEvent(self, event):  # noqa: N802
        # 整窗可拖：输入控件之外的区域（标题、说明、卡片空隙）都能移动窗口
        if event.button() == Qt.LeftButton:
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _finish(self, accepted: bool) -> None:
        self._result = accepted
        self.hide()
        loop = getattr(self, "_loop", None)
        if loop and loop.isRunning():
            loop.quit()

    def _stop_worker(self, timeout_ms: int = 3000) -> bool:
        """请求登录线程停止，并确认它已经退出。

        只调 quit() 不够：quit 只是让事件循环退出，若线程正阻塞在网络请求
        里，run() 不会返回；此时若窗口被销毁，QThread 会在运行中被析构，
        Qt 直接 qFatal（进程闪退）。因此这里先置取消事件，再等待；
        等待超时就进入"保活到线程结束"状态，绝不提前销毁窗口。
        """
        worker = self._worker
        if worker is not None:
            try:
                worker.request_stop()
            except RuntimeError:
                # worker 的 C++ 对象可能已随线程结束被 deleteLater 删除，
                # 但停止事件是纯 Python 对象，方法本身仍然可用。
                pass
        thread = self._thread
        if thread is None:
            return True
        if thread.isRunning():
            thread.quit()
            if not thread.wait(timeout_ms):
                self._retire_until_finished()
                return False
        return True

    def _retire_until_finished(self) -> None:
        """线程未停时保活窗口，等 thread.finished 后再真正删除。"""
        _KEEP_ALIVE.add(self)
        thread = self._thread
        if thread is None:
            return
        if not self._retired:
            self._retired = True
            thread.finished.connect(self._on_thread_finished)
        # 极端竞态：连接前线程刚好结束，finished 信号已经发过，不会再来了。
        if not thread.isRunning():
            self._on_thread_finished()

    def _on_thread_finished(self) -> None:
        _KEEP_ALIVE.discard(self)
        if self._disposed:
            self._cleanup()

    def dispose(self) -> None:
        """窗口使用完毕后的确定性释放入口。"""
        self._disposed = True
        thread = self._thread
        if thread is not None and thread.isRunning():
            self._retire_until_finished()
            return
        self._cleanup()

    def _cleanup(self) -> None:
        if getattr(self, "_cleaned", False):
            return
        self._cleaned = True
        thread = self._thread
        if thread is not None:
            if self._retired:
                try:
                    thread.finished.disconnect(self._on_thread_finished)
                except (RuntimeError, TypeError):
                    pass
            self._thread = None
        self._worker = None
        self._loop = None
        _KEEP_ALIVE.discard(self)
        retire(self)

    def _on_success(self, cookies: dict) -> None:
        self.status.setText("登录成功")
        self.status.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: 600;")
        self._stop_worker()
        self._finish(True)

    def _on_failed(self, message: str) -> None:
        self.status.setText(f"登录失败：{message}")
        self.status.setStyleSheet(f"color: {DANGER}; font-size: 11px;")
        self._stop_worker()
        self._finish(False)

    def closeEvent(self, event):  # noqa: N802
        self._stop_worker()
        self._finish(False)
        super().closeEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
