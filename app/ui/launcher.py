"""启动器 —— 一张「投放窗口」，只做一件事：把链接交给播放器。

版式：
    标题栏（品牌 + 窗口按钮）
    字段标签 + Enter 提示
    链接输入（右侧内嵌「粘贴」）
    一行状态 / 错误
    主操作「开始播放」
    细线 + 底部状态与两个低频动作
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import Config
from app.qt_lifecycle import retire
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import (
    ACCENT,
    DANGER,
    DIM,
    FAINT,
    LINE,
    SURFACE,
    TEXT,
    apply_opaque_shell,
    apply_theme,
)
from app.ui.widgets import BrandMark, GlyphButton, Hairline, StatusDot


class _UrlField(QLineEdit):
    """链接输入框，右侧内嵌「粘贴」。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("urlInput")
        self.setFixedHeight(46)
        self.setPlaceholderText("https://www.bilibili.com/video/BV…")
        self.setClearButtonEnabled(False)
        self.paste = QPushButton("粘贴", self)
        self.paste.setObjectName("inlineAction")
        self.paste.setFixedSize(44, 24)
        self.paste.setCursor(Qt.PointingHandCursor)
        self.paste.setFocusPolicy(Qt.NoFocus)
        self.paste.clicked.connect(self._paste_clipboard)

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text().strip()
        if text:
            self.setText(text)
            self.setFocus()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.paste.move(self.width() - self.paste.width() - 11, 11)


class _TitleBar(QFrame):
    """可拖动标题栏。优先交给系统做窗口移动，避免手算坐标的迟滞。"""

    def __init__(self, window):
        super().__init__()
        self._window = window
        self._drag_pos = None
        self.setFixedHeight(52)
        self.setCursor(Qt.OpenHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        brand_mark = BrandMark(22)
        brand_mark.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(brand_mark, 0, Qt.AlignVCenter)
        row.addSpacing(10)

        brand = QVBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(1)
        title = QLabel("StudyFloat")
        title.setObjectName("wordmark")
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        caption = QLabel("桌面悬浮播放器")
        caption.setObjectName("brandCaption")
        caption.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        brand.addWidget(title)
        brand.addWidget(caption)
        row.addLayout(brand, 0)
        row.addStretch(1)

        minimize = GlyphButton("min")
        minimize.clicked.connect(window.showMinimized)
        close = GlyphButton("close")
        close.clicked.connect(window.close)
        row.addWidget(minimize)
        row.addWidget(close, 0, Qt.AlignRight)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._window.raise_()
            self._window.activateWindow()
            handle = self._window.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
            # 少数平台不支持系统移动时退回手动拖动
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._window.move(self._window.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_pos = None
        event.accept()


class Launcher(QWidget):
    play_requested = Signal(str)
    login_requested = Signal()
    login_status = Signal(str, bool)

    WIDTH = 460
    STATUS_WIDTH = 224

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self._status_full = "未登录 · 公开视频可直接播放"
        self._dialog = None

        self.setWindowTitle("StudyFloat")
        self.setFixedWidth(self.WIDTH)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        shell = QVBoxLayout(self)
        # 卡片必须铺满窗口：外层留白会露出一条色差 padding，
        # 而且那圈区域接收不到标题栏的拖动事件（无法点击拖动）。
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        card = QFrame()
        card.setObjectName("window")
        # QFrame 在透明顶层上不会自动绘制样式表背景；不开这个属性，
        # 真实桌面上整张卡片是透明的，鼠标也会穿透到桌面。
        card.setAttribute(Qt.WA_StyledBackground, True)
        shell.addWidget(card)

        content = QVBoxLayout(card)
        content.setContentsMargins(22, 8, 22, 18)
        content.setSpacing(0)

        content.addWidget(_TitleBar(self))
        content.addSpacing(12)

        label_row = QHBoxLayout()
        label_row.setContentsMargins(0, 0, 0, 0)
        label_row.setSpacing(0)
        field_label = QLabel("视频链接 / BV 号")
        field_label.setObjectName("fieldLabel")
        key_hint = QLabel("Enter 开始播放")
        key_hint.setObjectName("hint")
        label_row.addWidget(field_label, 0, Qt.AlignVCenter)
        label_row.addStretch(1)
        label_row.addWidget(key_hint, 0, Qt.AlignVCenter)
        content.addLayout(label_row)
        content.addSpacing(9)

        self.url = _UrlField()
        self.url.returnPressed.connect(self._emit_play)
        content.addWidget(self.url)
        content.addSpacing(4)

        self.message = QLabel("")
        self.message.setObjectName("messageInfo")
        self.message.setWordWrap(True)
        self.message.setFixedHeight(18)
        self.message.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        content.addWidget(self.message)

        content.addSpacing(8)
        self.play_btn = QPushButton("开始播放")
        self.play_btn.setObjectName("primary")
        self.play_btn.setFixedHeight(44)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self._emit_play)
        content.addWidget(self.play_btn)

        content.addSpacing(16)
        content.addWidget(Hairline())
        content.addSpacing(10)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(0)
        self.dot = StatusDot(FAINT)
        self.status = QLabel(self._status_full)
        self.status.setObjectName("statusText")
        self.status.setFixedWidth(self.STATUS_WIDTH)
        footer.addWidget(self.dot, 0, Qt.AlignVCenter)
        footer.addSpacing(7)
        footer.addWidget(self.status, 0, Qt.AlignVCenter)
        footer.addStretch(1)

        self.login_btn = QPushButton("扫码登录")
        self.login_btn.setObjectName("textBtn")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setFixedHeight(28)
        self.login_btn.setMinimumWidth(64)
        self.login_btn.clicked.connect(lambda: self._open_settings("account"))
        sep = QLabel("·")
        sep.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setObjectName("textBtn")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setFixedHeight(28)
        self.settings_btn.setMinimumWidth(48)
        self.settings_btn.clicked.connect(lambda: self._open_settings("account"))
        footer.addWidget(self.login_btn, 0, Qt.AlignVCenter)
        footer.addWidget(sep, 0, Qt.AlignVCenter)
        footer.addWidget(self.settings_btn, 0, Qt.AlignVCenter)
        content.addLayout(footer)

        self._apply_style()
        self._elide_status()
        self.layout().activate()
        self.setFixedHeight(self.sizeHint().height())
        apply_opaque_shell(self, card)
        self.url.setFocus()

    # ------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802
        # 整窗可拖：点在标题、标签、卡片空白处（未被子控件消费的点击）
        # 都能移动窗口；输入框和按钮自己消化点击，不会误触。
        if event.button() == Qt.LeftButton:
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    def _apply_style(self) -> None:
        apply_theme(self)
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QFrame#window {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #171412, stop:0.34 #12100E, stop:1 #0B0A09);
                border: 1px solid #302A24;
                border-radius: 8px;
            }}
            QLineEdit#urlInput {{
                background: {SURFACE};
                color: {TEXT};
                border: 1px solid {LINE};
                border-radius: 10px;
                padding: 0 66px 0 14px;
                font-family: Consolas;
                font-size: 12px;
                selection-background-color: {ACCENT};
                selection-color: #1B1206;
            }}
            QLineEdit#urlInput:hover {{ border-color: #3A332B; }}
            QLineEdit#urlInput:focus {{ border-color: {ACCENT}; background: #171411; }}
            QLabel#messageInfo {{ color: {DIM}; font-size: 11px; }}
            QLabel#messageError {{ color: {DANGER}; font-size: 11px; }}
            """
        )

    # ------------------------------------------------------------------
    def _elide_status(self) -> None:
        metrics = QFontMetrics(self.status.font())
        self.status.setText(
            metrics.elidedText(self._status_full, Qt.ElideRight, self.STATUS_WIDTH)
        )

    def _set_message(self, text: str, tone: str) -> None:
        self.message.setText(text)
        self.message.setObjectName("messageError" if tone == "error" else "messageInfo")
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)

    def show_error(self, text: str) -> None:
        self._set_message(text, "error")

    def show_info(self, text: str) -> None:
        self._set_message(text, "info")

    def clear_error(self) -> None:
        self._set_message("", "info")

    def show_login_status(self, message: str, is_error: bool = False) -> None:
        self._status_full = message
        self._elide_status()
        self.dot.set_color(DANGER if is_error else ACCENT)

    # ------------------------------------------------------------------
    def _emit_play(self) -> None:
        self.clear_error()
        self.play_requested.emit(self.url.text())

    def _open_settings(self, page: str = "account") -> None:
        dialog = SettingsDialog(self.config)
        dialog.set_page(page)
        dialog.login_state_changed.connect(self._on_settings_login)
        self._dialog = dialog
        try:
            dialog.exec()
        finally:
            # SettingsDialog 里包含扫码窗口的启动按钮；显式释放，别等 GC。
            self._dialog = None
            retire(dialog)

    def _on_settings_login(self, ok: bool) -> None:
        if ok:
            self.show_login_status("已登录，播放时自动使用登录态")
        else:
            self.show_login_status("扫码未完成，可稍后重试", is_error=True)
