"""扫码登录对话框：显示二维码 + 后台轮询登录状态。"""
from __future__ import annotations

import threading

import qrcode
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from app.source.bili_login import BiliQRLogin, cookies_to_netscape


class _QRWidget(QWidget):
    """用 QPainter 直接绘制 qrcode 布尔矩阵，无图片/IO 依赖。"""

    def __init__(self):
        super().__init__()
        self._matrix: list[list[bool]] = []
        self.setFixedSize(240, 240)
        self.setStyleSheet("background: white;")

    def set_url(self, url: str):
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
                    painter.drawRect(int(c * cell), int(r * cell),
                                     int(cell + 0.6), int(cell + 0.6))
        painter.end()


class _LoginWorker(QObject):
    qr_ready = Signal(str)
    status = Signal(str)
    success = Signal(dict)
    failed = Signal(str)

    def __init__(self, cookie_path: str):
        super().__init__()
        self.cookie_path = cookie_path

    def run(self):
        try:
            login = BiliQRLogin()
            result = login.login(
                on_qr=lambda url: self.qr_ready.emit(url),
                on_status=lambda msg: self.status.emit(msg),
            )
            cookies_to_netscape(result.cookies, self.cookie_path)
            self.success.emit(result.cookies)
        except Exception as exc:
            self.failed.emit(str(exc))


class QRLoginDialog(QDialog):
    """模态对话框：显示二维码，扫码成功后自动保存 cookies.txt 并关闭。"""

    def __init__(self, cookie_path: str, parent=None):
        super().__init__(parent)
        self.cookie_path = cookie_path
        self.setWindowTitle("StudyFloat 扫码登录")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.qr = _QRWidget()
        self.status = QLabel("正在生成二维码…")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.qr)
        layout.addWidget(self.status)

        self._thread = QThread(self)
        self._worker = _LoginWorker(cookie_path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.qr_ready.connect(self.qr.set_url)
        self._worker.status.connect(self.status.setText)
        self._worker.success.connect(self._on_success)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_success(self, cookies: dict):
        self.status.setText("登录成功！")
        self._thread.quit()
        self.accept()

    def _on_failed(self, message: str):
        self.status.setText(f"登录失败：{message}")
        self._thread.quit()
        self.reject()

    def closeEvent(self, event):
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        super().closeEvent(event)
