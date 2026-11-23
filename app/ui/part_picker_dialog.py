"""分P选择窗口 —— 一份可扫读的「课程目录」。

版式：标题区（合辑名 + 计数）→ 全宽列表 → 底栏动作。
列表行由委托自绘：P 编号 / 标题 / 时长分三列，当前项一条黄铜竖线 + 微亮底色。
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
)

from app.source.bilibili_parts import PartInfo
from app.ui.theme import (
    ACCENT,
    DANGER,
    DIM,
    FAINT,
    LINE,
    TEXT,
    apply_opaque_shell,
    apply_theme,
)
from app.ui.widgets import GlyphButton

ROW_H = 52


def _fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return ""
    m, s = divmod(seconds, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class _ElidedLabel(QLabel):
    """单行标题，按实际宽度省略，不让长合辑名把窗口撑开。"""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._full = text
        self.setMinimumWidth(120)
        self.setFixedHeight(26)
        self.setText(text)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self._update_elide()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        metrics = QFontMetrics(self.font())
        self.setText(metrics.elidedText(self._full, Qt.ElideRight, max(60, self.width() - 4)))


class _PartDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):  # noqa: N802
        return QSize(0, ROW_H)

    def paint(self, painter: QPainter, option, index):  # noqa: N802
        part: PartInfo = index.data(Qt.UserRole)
        if part is None:
            return

        rect = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)

        if selected:
            painter.fillRect(rect, QColor("#1C1712"))
            painter.fillRect(QRectF(rect.left(), rect.top(), 2, rect.height()), QColor(ACCENT))
        elif hover:
            painter.fillRect(rect, QColor("#151310"))

        # 序号 P1
        index_font = QFont("Consolas")
        index_font.setPixelSize(10)
        painter.setFont(index_font)
        painter.setPen(QColor(ACCENT if selected else FAINT))
        painter.drawText(
            QRectF(rect.left() + 18, rect.top(), 34, rect.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"P{part.page}",
        )

        # 标题
        title_font = QFont()
        title_font.setPixelSize(12)
        title_font.setWeight(QFont.DemiBold if selected else QFont.Normal)
        painter.setFont(title_font)
        painter.setPen(QColor(TEXT if selected else "#D9D2C7"))
        title_rect = QRectF(
            rect.left() + 56, rect.top(), rect.width() - 56 - 92, rect.height()
        )
        elided = QFontMetrics(title_font).elidedText(
            part.title or f"第 {part.page} 个分P", Qt.ElideRight, int(title_rect.width())
        )
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)

        # 时长
        dur = _fmt_duration(part.duration)
        if dur:
            dur_font = QFont("Consolas")
            dur_font.setPixelSize(10)
            painter.setFont(dur_font)
            painter.setPen(QColor(DIM if selected else FAINT))
            painter.drawText(
                QRectF(rect.right() - 84, rect.top(), 60, rect.height()),
                Qt.AlignRight | Qt.AlignVCenter,
                dur,
            )

        # 行间细线（当前项不画，保持块面完整）
        if not selected:
            painter.setPen(QPen(QColor("#211D19"), 1))
            painter.drawLine(rect.left() + 18, rect.bottom(), rect.right() - 18, rect.bottom())

        painter.restore()


class PartPickerDialog(QFrame):
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
        self.setFixedSize(640, 620)
        self.selected_part: PartInfo | None = None
        self._result = None
        self._centered = False
        self._drag_pos = None

        shell = QVBoxLayout(self)
        # 卡片铺满窗口，与启动器/设置一致：不留不可交互的色差 padding
        shell.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("window")
        card.setAttribute(Qt.WA_StyledBackground, True)
        shell.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 16)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(7)
        eyebrow = QLabel(f"课程合辑 · 共 {len(parts)} 个分P")
        eyebrow.setObjectName("eyebrow")
        self._title = _ElidedLabel(title or "选择要播放的分P")
        self._title.setObjectName("partsTitle")
        text.addWidget(eyebrow)
        text.addWidget(self._title)
        header.addLayout(text, 1)
        close = GlyphButton("close")
        close.clicked.connect(self._on_cancel)
        header.addWidget(close, 0, Qt.AlignTop)
        layout.addLayout(header)
        layout.addSpacing(18)

        self.list = QListWidget()
        self.list.setObjectName("parts")
        self.list.setItemDelegate(_PartDelegate(self.list))
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setUniformItemSizes(True)
        self.list.setMouseTracking(True)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.itemActivated.connect(self._accept)

        for part in parts:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, part)
            self.list.addItem(item)

        if parts:
            target = (
                highlight_page
                if highlight_page in {p.page for p in parts}
                else parts[0].page
            )
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole).page == target:
                    self.list.setCurrentRow(i)
                    break
        layout.addWidget(self.list, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 14, 0, 0)
        footer.setSpacing(8)
        hint = QLabel("双击或 Enter 直接播放")
        hint.setObjectName("note")
        footer.addWidget(hint, 0, Qt.AlignVCenter)
        footer.addStretch(1)

        cancel = QPushButton("取消")
        cancel.setObjectName("ghost")
        cancel.setFixedSize(76, 34)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self._on_cancel)

        play = QPushButton("播放选中")
        play.setObjectName("primary")
        play.setFixedSize(112, 34)
        play.setCursor(Qt.PointingHandCursor)
        play.clicked.connect(self._accept)

        footer.addWidget(cancel, 0, Qt.AlignVCenter)
        footer.addWidget(play, 0, Qt.AlignVCenter)
        layout.addLayout(footer)

        self._apply_style()
        self.list.setFocus()
        apply_opaque_shell(self, card)

    def _apply_style(self) -> None:
        apply_theme(self)
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QFrame#window {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #14110F, stop:0.40 #0E0C0B, stop:1 #0B0A09);
                border: 1px solid #302A24;
                border-radius: 8px;
            }}
            QLabel#partsTitle {{ color: {TEXT}; font-size: 17px; font-weight: 600; }}
            QListWidget#parts {{
                background: transparent; border: none;
                border-top: 1px solid {LINE};
                border-bottom: 1px solid {LINE};
                outline: none;
            }}
            QListWidget#parts::item {{ border: none; background: transparent; }}
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
        self.list.setFocus()
        loop.exec()
        return self._result

    def mousePressEvent(self, event):  # noqa: N802
        # 整窗可拖：列表和按钮自己消化点击，其余区域都能移动窗口
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

    def _finish(self, accepted: bool) -> None:
        self._result = accepted
        self.hide()
        loop = getattr(self, "_loop", None)
        if loop and loop.isRunning():
            loop.quit()

    def _accept(self) -> None:
        item = self.list.currentItem()
        if item is not None:
            self.selected_part = item.data(Qt.UserRole)
            self._finish(True)

    def _on_cancel(self) -> None:
        self.selected_part = None
        self._finish(False)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)
