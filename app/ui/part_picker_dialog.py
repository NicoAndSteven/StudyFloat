"""分P选择对话框：列出合辑的所有分P，让用户选一个再播放。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app.source.bilibili_parts import PartInfo
from app.ui.theme import (
    PRIMARY_START,
    TEXT,
    TEXT_DIM,
    TEXT_FAINT,
    apply_theme,
    style_primary_button,
    style_secondary_button,
)


def _fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return ""
    m, s = divmod(seconds, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class PartPickerDialog(QFrame):
    """分P选择窗口：显示合辑分P列表，选中后 selected_part 非 None。

    非模态 + 置顶 + 屏幕居中，避免被置顶的启动器遮住。
    """

    def __init__(
        self,
        parts: list[PartInfo],
        title: str = "",
        highlight_page: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("选择分P")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setFixedSize(600, 480)
        self.selected_part: PartInfo | None = None
        self._result = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QLabel("选择要播放的分P")
        header.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 700;")
        layout.addWidget(header)
        sub = QLabel(
            f"《{title}》共 {len(parts)} 个分P" if title else f"共 {len(parts)} 个分P"
        )
        sub.setStyleSheet(f"color: {TEXT_FAINT}; font-size: 11px;")
        layout.addWidget(sub)

        self.list = QListWidget()
        for part in parts:
            dur = _fmt_duration(part.duration)
            label = f"P{part.page}   {part.title}" + (f"    [{dur}]" if dur else "")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, part)
            self.list.addItem(item)
        if parts:
            # 默认高亮 URL 请求的 P，找不到则第一项
            target = highlight_page if highlight_page in {p.page for p in parts} else parts[0].page
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole).page == target:
                    self.list.setCurrentRow(i)
                    break
        self.list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        hint = QLabel("双击分P可直接播放")
        hint.setStyleSheet(f"color: {TEXT_FAINT}; font-size: 11px;")
        row.addWidget(hint)
        row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setMinimumHeight(36)
        style_secondary_button(cancel)
        cancel.clicked.connect(self._on_cancel)
        play = QPushButton("▶  播放选中")
        play.setMinimumHeight(36)
        style_primary_button(play)
        play.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(play)
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

    # --- 模态式 exec 兼容：用 QFrame 模拟 QDialog.exec 的阻塞行为 ---
    def exec(self):
        """阻塞显示，返回 True 表示用户确认（对齐 QDialog.exec 接口）。"""
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

    def _on_double_click(self, item: QListWidgetItem):
        self._accept()

    def _accept(self):
        item = self.list.currentItem()
        if item is not None:
            self.selected_part = item.data(Qt.UserRole)
            self._finish(True)

    def _on_cancel(self):
        self.selected_part = None
        self._finish(False)
