from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import Config
from app.ui.settings_dialog import SettingsDialog


class Launcher(QWidget):
    """Minimal URL input window. Emits play_requested when the user clicks Play."""

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
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://www.bilibili.com/video/BV...")
        self.url.returnPressed.connect(self._emit_play)
        layout.addWidget(self.url)
        self.error = QLabel("")
        self.error.setStyleSheet("color: #c62828;")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        row = QHBoxLayout()
        play = QPushButton("播放")
        play.clicked.connect(self._emit_play)
        settings = QPushButton("设置")
        settings.clicked.connect(self._open_settings)
        row.addWidget(play)
        row.addWidget(settings)
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
