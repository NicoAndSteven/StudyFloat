from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.config import Config
from app.ui.theme import TEXT, TEXT_DIM, apply_theme, style_primary_button, style_secondary_button

SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]


def _section(title: str) -> QLabel:
    label = QLabel(title)
    label.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700; padding-top: 6px;")
    return label


class SettingsDialog(QFrame):
    """设置窗口：Cookie、默认倍速/音量、窗口预设与开关。深色统一样式。"""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("StudyFloat 设置")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setFixedSize(460, 430)
        self._result = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(8)

        head = QLabel("设置")
        head.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 700;")
        layout.addWidget(head)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        self.cookie = QLineEdit(config.cookie_path)
        self.cookie.setPlaceholderText("可选，Netscape 格式 cookies.txt")
        cookie_btn = QPushButton("选择文件")
        cookie_btn.setMinimumHeight(32)
        style_secondary_button(cookie_btn)
        cookie_btn.clicked.connect(self._pick_cookie)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.cookie, 1)
        row.addWidget(cookie_btn)
        form.addRow(QLabel("Cookie 文件"), row)

        self.speed = QDoubleSpinBox()
        self.speed.setDecimals(2)
        self.speed.setSingleStep(0.25)
        self.speed.setRange(0.5, 2.0)
        self.speed.setValue(config.default_speed)
        form.addRow("默认倍速", self.speed)

        self.volume = QSpinBox()
        self.volume.setRange(0, 100)
        self.volume.setValue(config.default_volume)
        form.addRow("默认音量", self.volume)

        self.preset = QComboBox()
        self.preset.addItems(["微型", "小型", "标准", "大型", "自定义"])
        self.preset.setCurrentText(config.window_preset)
        form.addRow("窗口预设", self.preset)

        self.ontop = QCheckBox("窗口置顶")
        self.ontop.setChecked(config.always_on_top)
        self.borderless = QCheckBox("无边框窗口")
        self.borderless.setChecked(config.borderless)
        form.addRow(self.ontop)
        form.addRow(self.borderless)
        layout.addLayout(form)

        layout.addStretch(1)
        row = QHBoxLayout()
        row.setSpacing(8)
        note = QLabel("设置保存在程序目录")
        note.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        row.addWidget(note)
        row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setMinimumHeight(36)
        style_secondary_button(cancel)
        cancel.clicked.connect(self._on_cancel)
        save = QPushButton("保存")
        save.setMinimumHeight(36)
        style_primary_button(save)
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        layout.addLayout(row)

        apply_theme(self)
        card.setStyleSheet(
            """
            QFrame#card {
                background: #20232b;
                border: 1px solid #343846;
                border-radius: 14px;
            }
            """
        )

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

    def _finish(self, accepted: bool):
        self._result = accepted
        self.hide()
        loop = getattr(self, "_loop", None)
        if loop and loop.isRunning():
            loop.quit()

    def _pick_cookie(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Cookie 文件", "", "Text files (*.txt)")
        if path:
            self.cookie.setText(path)

    def _save(self):
        self.config.cookie_path = self.cookie.text().strip()
        self.config.default_speed = self.speed.value()
        self.config.default_volume = self.volume.value()
        self.config.window_preset = self.preset.currentText()
        self.config.always_on_top = self.ontop.isChecked()
        self.config.borderless = self.borderless.isChecked()
        self.config.save()
        self._finish(True)

    def _on_cancel(self):
        self._finish(False)
