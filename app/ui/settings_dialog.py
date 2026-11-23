"""设置窗口 —— 双栏偏好面板（左导航 + 右页面）。

设计约束（改样式前先读）：
1. **左栏是导航，不是装饰。** 三项：账号 / 播放 / 窗口，每项两行字（中文 + 拉丁小标），
   选中项只有一条 2px 黄铜竖线和一层微亮底色。
2. **右栏一条控件轨道。** 所有输入、滑杆、分段、开关的右边缘对齐到内容区右边界。
3. **一页只放一类事。** 账号页 = 登录态 + Cookie；播放页 = 两个滑杆；窗口页 = 预设 + 两个开关。
4. **黄铜只给激活态。** 主按钮、选中导航线、滑杆已填充段、开关 ON。
5. **footer 固定。** 保存 / 取消 / 恢复默认永远贴底，不随页面滚动。

Qt 样式坑：不要在容器子控件上再 setStyleSheet，否则该子树会成为新的样式根，
标签颜色回退成系统浅色。统一走 objectName + 这里的规则。
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import Config
from app.ui.theme import (
    ACCENT,
    ACCENT_INK,
    BG,
    DANGER,
    DIM,
    FAINT,
    LINE,
    SURFACE,
    SURFACE_2,
    TEXT,
    apply_opaque_shell,
    apply_theme,
)
from app.ui.widgets import (
    BrandMark,
    FieldRow,
    GlyphButton,
    Hairline,
    SegmentedControl,
    SliderField,
    StatusDot,
    ToggleSwitch,
)

WIN_W, WIN_H = 712, 476  # 原 760×520 去掉四周 24/20px 外壳留白后的卡片尺寸
RAIL_W = 200
PANE_PAD = 30


# ---------------------------------------------------------------------------
# 左栏导航项
# ---------------------------------------------------------------------------
class _NavItem(QWidget):
    clicked = Signal()

    def __init__(self, title: str, caption: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._caption = caption
        self._selected = False
        self._hover = False
        self.setFixedHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

        self._title_font = QFont()
        self._title_font.setPixelSize(12)
        self._title_font.setWeight(QFont.DemiBold)
        self._caption_font = QFont()
        self._caption_font.setPixelSize(8)
        self._caption_font.setWeight(QFont.DemiBold)
        self._caption_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.4)

    def set_selected(self, value: bool) -> None:
        self._selected = value
        self.update()

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._selected:
            p.fillRect(self.rect(), QColor("#1A1510"))
            p.fillRect(0, 10, 2, self.height() - 20, QColor(ACCENT))
        elif self._hover:
            p.fillRect(self.rect(), QColor("#12100D"))

        p.setFont(self._title_font)
        p.setPen(QColor(TEXT if self._selected else DIM))
        p.drawText(
            QRectF(20, 8, self.width() - 26, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._title,
        )

        p.setFont(self._caption_font)
        p.setPen(QColor(ACCENT if self._selected else FAINT))
        p.drawText(
            QRectF(20, 27, self.width() - 26, 14),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._caption.upper(),
        )
        p.end()


# ---------------------------------------------------------------------------
# 尺寸预设控件
# ---------------------------------------------------------------------------
class _PresetField(QWidget):
    changed = Signal(str)

    def __init__(self, current: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.segment = SegmentedControl(["微型", "小型", "标准", "大型"], current)
        self.segment.setFixedWidth(248)
        self.segment.changed.connect(self._on_change)
        layout.addWidget(self.segment, 0, Qt.AlignRight)

    def _on_change(self, value: str) -> None:
        self.changed.emit(value)

    def value(self) -> str:
        return self.segment.value()

    def setValue(self, value: str) -> None:  # noqa: N802
        self.segment.setValue(value)
        self._on_change(value)


# ---------------------------------------------------------------------------
# 设置窗口
# ---------------------------------------------------------------------------
class SettingsDialog(QFrame):
    login_requested = Signal()
    login_state_changed = Signal(bool)

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("StudyFloat 设置")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setFixedSize(WIN_W, WIN_H)
        self._result = False
        self._centered = False
        self._drag_pos = None

        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        window = QFrame()
        window.setObjectName("window")
        window.setAttribute(Qt.WA_StyledBackground, True)
        shell.addWidget(window)

        root = QHBoxLayout(window)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_rail())
        root.addWidget(self._build_pane(), 1)

        self._close_btn = GlyphButton("close", self)
        self._close_btn.move(WIN_W - 20 - 30, 20)
        self._close_btn.clicked.connect(self._on_cancel)
        self._close_btn.raise_()

        self._nav_items[0].set_selected(True)
        self._stack.setCurrentIndex(0)

        self._refresh_login_state()
        self._apply_style()
        self.setFocusPolicy(Qt.StrongFocus)
        self.cookie.returnPressed.connect(self._save)
        apply_opaque_shell(self, window)

    # ------------------------------------------------------------------
    # 左栏
    # ------------------------------------------------------------------
    def _build_rail(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("rail")
        rail.setFixedWidth(RAIL_W)

        layout = QVBoxLayout(rail)
        layout.setContentsMargins(22, 22, 18, 18)
        layout.setSpacing(0)

        brand = QHBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(10)
        brand.addWidget(BrandMark(24), 0, Qt.AlignVCenter)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        name = QLabel("StudyFloat")
        name.setObjectName("wordmark")
        caption = QLabel("FLOATING PLAYER")
        caption.setObjectName("railCaption")
        text.addWidget(name)
        text.addWidget(caption)
        brand.addLayout(text, 1)
        layout.addLayout(brand)
        layout.addSpacing(30)

        self._nav_items: list[_NavItem] = []
        for index, (title, caption) in enumerate(
            [("账号", "Account"), ("播放", "Playback"), ("窗口", "Window")]
        ):
            item = _NavItem(title, caption)
            item.clicked.connect(lambda i=index: self.set_page_index(i))
            layout.addWidget(item)
            self._nav_items.append(item)

        layout.addStretch(1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(2, 0, 0, 0)
        bottom.setSpacing(7)
        self._rail_dot = StatusDot(FAINT)
        self._rail_status = QLabel("未登录")
        self._rail_status.setObjectName("statusText")
        bottom.addWidget(self._rail_dot, 0, Qt.AlignVCenter)
        bottom.addWidget(self._rail_status, 0, Qt.AlignVCenter)
        bottom.addStretch(1)
        layout.addLayout(bottom)
        layout.addSpacing(8)

        version = QLabel("v5 · 本地绿色版")
        version.setObjectName("railVersion")
        layout.addWidget(version)
        return rail

    # ------------------------------------------------------------------
    # 右栏
    # ------------------------------------------------------------------
    def _build_pane(self) -> QFrame:
        pane = QFrame()
        pane.setObjectName("pane")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(PANE_PAD, 26, PANE_PAD, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_account_page())
        self._stack.addWidget(self._build_playback_page())
        self._stack.addWidget(self._build_window_page())
        layout.addWidget(self._stack, 1)

        layout.addWidget(Hairline())
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 14, 0, 16)
        footer.setSpacing(8)
        note = QLabel("配置保存在 config.json")
        note.setObjectName("note")
        footer.addWidget(note, 0, Qt.AlignVCenter)
        footer.addStretch(1)

        reset = QPushButton("恢复默认")
        reset.setObjectName("textBtn")
        reset.setFixedHeight(34)
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self._reset_defaults)

        cancel = QPushButton("取消")
        cancel.setObjectName("ghost")
        cancel.setFixedSize(76, 34)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self._on_cancel)

        save = QPushButton("保存")
        save.setObjectName("primary")
        save.setFixedSize(100, 34)
        save.setCursor(Qt.PointingHandCursor)
        save.setDefault(True)
        save.clicked.connect(self._save)

        footer.addWidget(reset, 0, Qt.AlignVCenter)
        footer.addSpacing(6)
        footer.addWidget(cancel, 0, Qt.AlignVCenter)
        footer.addWidget(save, 0, Qt.AlignVCenter)
        layout.addLayout(footer)
        return pane

    def _page_shell(self, eyebrow: str, title: str, desc: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tag = QLabel(eyebrow)
        tag.setObjectName("eyebrow")
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        sub = QLabel(desc)
        sub.setObjectName("pageDesc")
        sub.setWordWrap(True)

        layout.addWidget(tag)
        layout.addSpacing(8)
        layout.addWidget(heading)
        layout.addSpacing(7)
        layout.addWidget(sub)
        layout.addSpacing(24)
        return page, layout

    def _build_account_page(self) -> QWidget:
        page, layout = self._page_shell(
            "ACCOUNT", "账号与登录", "扫码登录后可播放更高清晰度；公开视频无需登录。"
        )

        panel = QFrame()
        panel.setObjectName("statusPanel")
        panel.setFixedHeight(100)
        panel_layout = QHBoxLayout(panel)
        panel_layout.setContentsMargins(18, 15, 18, 15)
        panel_layout.setSpacing(16)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(5)
        label = QLabel("当前登录态")
        label.setObjectName("panelLabel")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._panel_dot = StatusDot(FAINT)
        self._panel_status = QLabel("未登录")
        self._panel_status.setObjectName("panelStatus")
        row.addWidget(self._panel_dot, 0, Qt.AlignVCenter)
        row.addWidget(self._panel_status, 0, Qt.AlignVCenter)
        row.addStretch(1)
        self._panel_note = QLabel("扫码登录后自动保存，无需手动导出 Cookie")
        self._panel_note.setObjectName("note")
        info.addWidget(label)
        info.addLayout(row)
        info.addWidget(self._panel_note)
        panel_layout.addLayout(info, 1)

        self.login_btn = QPushButton("扫码登录")
        self.login_btn.setObjectName("primary")
        self.login_btn.setFixedSize(100, 34)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._open_qr_login)
        panel_layout.addWidget(self.login_btn, 0, Qt.AlignVCenter)
        layout.addWidget(panel)

        layout.addSpacing(20)

        cookie_box = QWidget()
        cookie_row = QHBoxLayout(cookie_box)
        cookie_row.setContentsMargins(0, 0, 0, 0)
        cookie_row.setSpacing(8)
        self.cookie = QLineEdit(self.config.cookie_path)
        self.cookie.setObjectName("cookieInput")
        self.cookie.setPlaceholderText("未设置（可选）")
        self.cookie.setFixedSize(200, 34)
        self.cookie.setClearButtonEnabled(False)
        browse = QPushButton("浏览")
        browse.setObjectName("small")
        browse.setFixedSize(62, 34)
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._pick_cookie)
        cookie_row.addWidget(self.cookie)
        cookie_row.addWidget(browse)
        cookie_box.setFixedWidth(270)

        layout.addWidget(FieldRow("Cookie 文件", "可选 · Netscape 格式", cookie_box))
        layout.addWidget(Hairline())
        layout.addSpacing(12)
        note = QLabel("扫码登录态优先于手动 Cookie；文件只在本机读取，不会上传。")
        note.setObjectName("note")
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _build_playback_page(self) -> QWidget:
        page, layout = self._page_shell(
            "PLAYBACK", "播放", "控制每次打开视频时的初始状态，播放中仍可用快捷键调整。"
        )

        self.speed = SliderField(
            50, 200, round(self.config.default_speed * 100), lambda v: f"{v / 100:.2f}×"
        )
        layout.addWidget(FieldRow("默认倍速", "打开视频时自动应用", self.speed))
        layout.addWidget(Hairline())

        self.volume = SliderField(0, 100, self.config.default_volume, lambda v: f"{v}%")
        layout.addWidget(FieldRow("默认音量", "不影响系统音量", self.volume))

        layout.addSpacing(22)
        note = QLabel("快捷键 · 播放窗口内生效")
        note.setObjectName("note")
        layout.addWidget(note)
        layout.addSpacing(12)
        layout.addLayout(self._shortcut_grid())
        layout.addStretch(1)
        return page

    def _shortcut_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(34)
        grid.setVerticalSpacing(8)
        items = [
            ("空格", "播放 / 暂停"),
            ("← →", "快退 / 快进 5 秒"),
            ("[ ]", "倍速"),
            ("m", "静音"),
            ("f", "全屏"),
            ("Esc", "退出全屏"),
        ]
        for i, (keys, desc) in enumerate(items):
            cell = QWidget()
            row = QHBoxLayout(cell)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(9)
            keycap = QLabel(keys)
            keycap.setObjectName("keycap")
            keycap.setFixedHeight(22)
            keycap.setAlignment(Qt.AlignCenter)
            text = QLabel(desc)
            text.setObjectName("shortcutDesc")
            row.addWidget(keycap, 0, Qt.AlignVCenter)
            row.addWidget(text, 0, Qt.AlignVCenter)
            row.addStretch(1)
            grid.addWidget(cell, i // 2, i % 2)
        return grid

    def _build_window_page(self) -> QWidget:
        page, layout = self._page_shell(
            "WINDOW", "窗口", "决定浮动播放窗口的大小，以及它与其他窗口的层级关系。"
        )

        self.preset = _PresetField(self.config.window_preset)
        self.preset_row = FieldRow("尺寸预设", self._preset_desc(), self.preset)
        self.preset.changed.connect(
            lambda value: self.preset_row.set_desc(self._preset_desc(value))
        )
        layout.addWidget(self.preset_row)
        layout.addWidget(Hairline())

        self.ontop = ToggleSwitch(self.config.always_on_top)
        layout.addWidget(FieldRow("始终置顶", "播放时保持在终端、浏览器上方", self.ontop))
        layout.addWidget(Hairline())

        self.borderless = ToggleSwitch(self.config.borderless)
        layout.addWidget(FieldRow("无边框模式", "隐藏系统标题栏，画面更干净", self.borderless))

        layout.addSpacing(16)
        note = QLabel("关闭播放器时会记住最后的窗口位置和尺寸。")
        note.setObjectName("note")
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------
    # 样式
    # ------------------------------------------------------------------
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
            QFrame#rail {{
                background: #090807;
                border: none;
                border-right: 1px solid #221E19;
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
            }}
            QFrame#pane {{ background: transparent; border: none; }}
            QStackedWidget {{ background: transparent; }}

            QLabel#railCaption {{
                color: {FAINT}; font-size: 8px; font-weight: 600;
                letter-spacing: 1.4px;
            }}
            QLabel#railVersion {{ color: {FAINT}; font-size: 9.5px; }}

            QFrame#statusPanel {{
                background: {SURFACE};
                border: 1px solid {LINE};
                border-radius: 12px;
            }}
            QLabel#panelLabel {{
                color: {FAINT}; font-size: 9.5px; font-weight: 600;
                letter-spacing: 1.4px;
            }}
            QLabel#panelStatus {{ color: {TEXT}; font-size: 14px; font-weight: 600; }}
            QLabel#panelBadge {{
                color: {FAINT}; font-size: 9.5px;
                background: {SURFACE_2};
                border: 1px solid {LINE};
                border-radius: 6px;
            }}

            QLineEdit#cookieInput {{ font-size: 11px; }}
            QLabel#keycap {{
                color: {TEXT}; background: {SURFACE_2};
                border: 1px solid {LINE}; border-radius: 5px;
                font-family: Consolas; font-size: 10px;
                padding: 0 7px;
            }}
            QLabel#shortcutDesc {{ color: {DIM}; font-size: 11px; }}
            """
        )

    # ------------------------------------------------------------------
    # 数据与动作
    # ------------------------------------------------------------------
    def set_page_index(self, index: int) -> None:
        index = max(0, min(index, len(self._nav_items) - 1))
        for i, item in enumerate(self._nav_items):
            item.set_selected(i == index)
        self._stack.setCurrentIndex(index)

    def set_page(self, name: str) -> None:
        names = {"account": 0, "playback": 1, "window": 2}
        self.set_page_index(names.get(name, 0))

    def _preset_desc(self, value: str | None = None) -> str:
        from app.window.geometry import PRESETS

        size = PRESETS.get(value or self.config.window_preset, PRESETS["标准"])
        return f"下次播放时生效 · {size[0]} × {size[1]}"

    def _refresh_login_state(self) -> bool:
        logged_in = False
        try:
            from app.paths import QR_COOKIE_FILE, data_path

            logged_in = data_path(QR_COOKIE_FILE).is_file()
        except Exception:
            pass

        self._rail_status.setText("已登录" if logged_in else "未登录")
        self._rail_dot.set_color(ACCENT if logged_in else FAINT)
        self._panel_status.setText("已登录" if logged_in else "未登录")
        self._panel_dot.set_color(ACCENT if logged_in else FAINT)
        self._panel_note.setText(
            "登录态有效，掉线后重新扫码即可"
            if logged_in
            else "扫码登录后自动保存，约 30 天有效"
        )
        self.login_btn.setText("重新扫码" if logged_in else "扫码登录")
        return logged_in

    def _open_qr_login(self) -> None:
        from app.paths import QR_COOKIE_FILE, data_path
        from app.ui.qr_login_dialog import QRLoginDialog

        dialog = QRLoginDialog(str(data_path(QR_COOKIE_FILE)))
        try:
            accepted = bool(dialog.exec())
        finally:
            dialog.dispose()
        if accepted:
            self._refresh_login_state()
            self.login_state_changed.emit(True)

    def _pick_cookie(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Cookie 文件", "", "Text files (*.txt)"
        )
        if path:
            self.cookie.setText(path)

    def _reset_defaults(self) -> None:
        self.cookie.setText("")
        self.speed.setValue(100)
        self.volume.setValue(100)
        self.preset.setValue("标准")
        self.ontop.setChecked(True)
        self.borderless.setChecked(True)

    def _save(self) -> None:
        self.config.cookie_path = self.cookie.text().strip()
        self.config.default_speed = self.speed.value() / 100
        self.config.default_volume = self.volume.value()
        self.config.window_preset = self.preset.value()
        self.config.always_on_top = self.ontop.isChecked()
        self.config.borderless = self.borderless.isChecked()
        self.config.save()
        self._finish(True)

    def _on_cancel(self) -> None:
        self._finish(False)

    # ------------------------------------------------------------------
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

    def _finish(self, accepted: bool) -> None:
        self._result = accepted
        self.hide()
        loop = getattr(self, "_loop", None)
        if loop and loop.isRunning():
            loop.quit()

    # ------------------------------------------------------------------
    # 无边框拖动与定位
    # ------------------------------------------------------------------
    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if self._centered:
            return
        self._centered = True
        self.setFocus()
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.move(
                avail.left() + (avail.width() - self.width()) // 2,
                avail.top() + (avail.height() - self.height()) // 2,
            )

    def mousePressEvent(self, event):  # noqa: N802
        # 整窗可拖：导航/控件之外的空白区域都能移动窗口
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

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)
