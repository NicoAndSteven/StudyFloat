from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from app.config import Config

SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]


class SettingsDialog(QDialog):
    """Minimal settings window: cookie, default speed/volume, window preset and flags."""

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
        self.borderless = QCheckBox("无边框")
        self.borderless.setChecked(config.borderless)
        form.addRow(self.ontop)
        form.addRow(self.borderless)

        save = QPushButton("保存")
        save.clicked.connect(self._save)
        form.addRow(save)

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
        self.accept()
