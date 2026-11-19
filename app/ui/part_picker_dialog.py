"""分P选择对话框：列出合辑的所有分P，让用户选一个再播放。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app.source.bilibili_parts import PartInfo


def _fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return ""
    m, s = divmod(seconds, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class PartPickerDialog(QDialog):
    """模态对话框：显示合辑分P列表，选中后 selected_part 非 None。"""

    def __init__(self, parts: list[PartInfo], title: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择分P")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setModal(True)
        self.resize(560, 420)
        self.selected_part: PartInfo | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"《{title}》共有 {len(parts)} 个分P，请选择要播放的："))
        self.list = QListWidget()
        for part in parts:
            dur = _fmt_duration(part.duration)
            label = f"P{part.page}  {part.title}" + (f"   [{dur}]" if dur else "")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, part)
            self.list.addItem(item)
        if parts:
            self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list)

        row = QVBoxLayout()
        play = QPushButton("播放选中分P")
        play.clicked.connect(self._accept)
        row.addWidget(play)
        layout.addLayout(row)

    def _on_double_click(self, item: QListWidgetItem):
        self._accept()

    def _accept(self):
        item = self.list.currentItem()
        if item is not None:
            self.selected_part = item.data(Qt.UserRole)
            self.accept()
