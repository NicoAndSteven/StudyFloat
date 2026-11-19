from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import Config
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import (
    BG,
    ERROR,
    PANEL,
    PANEL_ALT,
    PRIMARY_END,
    PRIMARY_START,
    SUCCESS,
    TEXT,
    TEXT_DIM,
    TEXT_FAINT,
    apply_theme,
    style_primary_button,
    style_secondary_button,
)


class _Logo(QWidget):
    """渐变圆角 S 图标。"""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 9, 9)
        from PySide6.QtGui import QLinearGradient, QColor, QFont

        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0, QColor(PRIMARY_START))
        grad.setColorAt(1, QColor(PRIMARY_END))
        painter.fillPath(path, grad)
        painter.setPen(Qt.white)
        font = QFont()
        font.setBold(True)
        font.setPointSize(13)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, "S")
        painter.end()


class _TitleBar(QFrame):
    """自绘标题栏：可拖动，右侧最小化/关闭。"""

    def __init__(self, parent_window: QWidget):
        super().__init__()
        self._window = parent_window
        self.setFixedHeight(44)
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(10)

        logo = _Logo()
        logo.setFixedSize(30, 30)
        layout.addWidget(logo)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        title = QLabel("StudyFloat")
        title.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: 700;")
        sub = QLabel("独立悬浮播放器")
        sub.setStyleSheet(f"color: {TEXT_FAINT}; font-size: 10px;")
        brand.addWidget(title)
        brand.addWidget(sub)
        layout.addLayout(brand)
        layout.addStretch(1)

        for text, slot in (("─", parent_window.showMinimized), ("✕", parent_window.close)):
            btn = QPushButton(text)
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.ArrowCursor)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: transparent; color: {TEXT_DIM};
                    border: none; border-radius: 6px; font-size: 13px;
                }}
                QPushButton:hover {{ background: {PANEL_ALT}; color: {TEXT}; }}
                """
            )
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    def mousePressEvent(self, event):
        self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if hasattr(self, "_drag_pos") and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._window.move(self._window.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()


class Launcher(QWidget):
    """极简启动器：输入链接 → 播放 / 扫码登录 / 设置。"""

    play_requested = Signal(str)
    login_requested = Signal()
    login_status = Signal(str, bool)  # message, is_error

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.setWindowTitle("StudyFloat")
        self.setFixedWidth(460)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            f"""
            QFrame#card {{
                background: {PANEL};
                border: 1px solid #343846;
                border-radius: 14px;
            }}
            """
        )
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 0, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(_TitleBar(self))

        hint = QLabel("Bilibili 视频链接 / BV 号")
        hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        layout.addWidget(hint)

        self.url = QLineEdit()
        self.url.setPlaceholderText("粘贴链接或 BV 号…")
        self.url.setMinimumHeight(38)
        self.url.returnPressed.connect(self._emit_play)
        layout.addWidget(self.url)

        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color: {ERROR}; font-size: 11px;")
        layout.addWidget(self.error)

        self.login_label = QLabel("")
        self.login_label.setWordWrap(True)
        self.login_label.setStyleSheet(f"color: {TEXT_FAINT}; font-size: 11px;")
        layout.addWidget(self.login_label)

        row = QHBoxLayout()
        row.setSpacing(8)
        play = QPushButton("▶  播放")
        play.setMinimumHeight(38)
        style_primary_button(play)
        play.clicked.connect(self._emit_play)
        settings = QPushButton("设置")
        settings.setMinimumHeight(38)
        style_secondary_button(settings)
        settings.clicked.connect(self._open_settings)
        login = QPushButton("扫码登录")
        login.setMinimumHeight(38)
        style_secondary_button(login)
        login.clicked.connect(lambda: self.login_requested.emit())
        row.addWidget(play, 2)
        row.addWidget(login, 1)
        row.addWidget(settings, 1)
        layout.addLayout(row)

        apply_theme(self)
        # apply_theme 的通用规则会覆盖卡片背景，重新强调卡片
        card.setStyleSheet(
            f"""
            QFrame#card {{
                background: {PANEL};
                border: 1px solid #343846;
                border-radius: 14px;
            }}
            """
        )
        self.url.setFocus()

    def show_error(self, message: str):
        self.error.setText(message)
        self.error.setStyleSheet(f"color: {ERROR}; font-size: 11px;")

    def clear_error(self):
        self.error.setText("")

    def show_login_status(self, message: str, is_error: bool = False):
        self.login_label.setText(message)
        self.login_label.setStyleSheet(
            f"color: {ERROR if is_error else SUCCESS}; font-size: 11px;"
        )

    def _emit_play(self):
        self.clear_error()
        self.play_requested.emit(self.url.text())

    def _open_settings(self):
        SettingsDialog(self.config, self).exec()
