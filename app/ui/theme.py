"""StudyFloat 设计系统 —— 暖夜色 + 单一黄铜强调色。

改样式前先读这四条约束，别退回「蓝黑 + 薄荷绿 + 全加粗」：

1. **底色是暖黑，不是蓝黑。** 面只靠三级明度区分（BG / SURFACE / SURFACE_2），
   不用彩色块分区，也不给卡片叠卡片。
2. **只有一个强调色。** 黄铜 #DCA85A 只出现在：主按钮、当前项标记、滑杆已填充段、
   开关 ON、输入框聚焦边框。其余一律中性色。
3. **字重只有两档。** 400 正文 / 600 标题。不要整页加粗 —— 全加粗等于没有层级。
4. **圆角只有三档。** 窗口 16 / 面板 12 / 控件 10（小按钮 8）。

Qt 样式坑：不要在容器子控件上再 setStyleSheet，那会把该子树当成新的样式根，
标签颜色会回退成系统浅色。统一走 objectName + 这里的规则。
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainterPath, QPalette, QRegion

# ---------------------------------------------------------------------------
# 色板
# ---------------------------------------------------------------------------
BG = "#0C0B0A"           # 窗口最底
BG_TOP = "#131110"       # 窗口顶部（给一点纵深）
SURFACE = "#141210"      # 面板 / 输入框
SURFACE_2 = "#1A1714"    # 抬起的控件
SURFACE_3 = "#221D18"    # 分段选中 / 悬停
LINE = "#2A2521"          # 细线 / 边框
LINE_2 = "#3A332B"        # 悬停边框
TEXT = "#F2EDE4"          # 主文字（暖白，不用纯白）
DIM = "#A89F92"           # 次要文字
FAINT = "#8D8375"         # 说明 / 微标签
ACCENT = "#DCA85A"        # 黄铜
ACCENT_HOVER = "#EBBB74"
ACCENT_PRESS = "#C6903F"
ACCENT_INK = "#1B1206"    # 强调色上的文字
DANGER = "#E27C68"
SELECTED = "#241D14"      # 当前项底色

# 兼容旧命名（其他模块可能还引用）
PRIMARY_START = ACCENT
PRIMARY_END = ACCENT_PRESS
PANEL = SURFACE
PANEL_ALT = SURFACE_2
PANEL_HOVER = SURFACE_3
BORDER = LINE
BORDER_SOFT = "#221E19"
PRIMARY_DARK = ACCENT_INK
TEXT_FAINT = FAINT
TEXT_DIM = DIM
SUCCESS = ACCENT
ERROR = DANGER


def app_font() -> QFont:
    """全局字体：Win11 用 Segoe UI Variable，Win10 回退 Segoe UI，中文走雅黑。"""
    font = QFont()
    font.setFamilies(
        ["Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei"]
    )
    font.setPixelSize(13)
    font.setHintingPreference(QFont.PreferFullHinting)
    return font


def base_qss() -> str:
    """所有窗口共用的基础规则。窗口自身的渐变/圆角再往后拼。"""
    return f"""
        * {{ outline: none; }}
        QWidget {{ color: {TEXT}; font-size: 12px; }}
        QLabel {{ background: transparent; }}

        QFrame#hairline {{ background: {LINE}; border: none; }}
        QFrame#rule {{ background: #211D19; border: none; }}

        QLabel#wordmark {{ color: {TEXT}; font-size: 15px; font-weight: 600; }}
        QLabel#brandCaption {{ color: {DIM}; font-size: 10px; }}
        QLabel#eyebrow {{
            color: {FAINT}; font-size: 9.5px; font-weight: 600;
            letter-spacing: 1.6px;
        }}
        QLabel#pageTitle {{ color: {TEXT}; font-size: 22px; font-weight: 500; }}
        QLabel#pageDesc {{ color: {DIM}; font-size: 11.5px; }}
        QLabel#fieldLabel {{ color: {DIM}; font-size: 11px; }}
        QLabel#hint {{ color: {FAINT}; font-size: 10px; }}
        QLabel#rowTitle {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
        QLabel#rowDesc {{ color: {FAINT}; font-size: 11px; }}
        QLabel#note {{ color: {FAINT}; font-size: 10.5px; }}
        QLabel#monoValue {{
            color: {TEXT}; font-family: Consolas; font-size: 11px;
        }}
        QLabel#statusText {{ color: {FAINT}; font-size: 10.5px; }}
        QLabel#message {{ font-size: 11px; }}

        QPushButton {{
            background: transparent; border: none; color: {DIM};
        }}
        QPushButton#primary {{
            background: {ACCENT}; color: {ACCENT_INK};
            border: none; border-radius: 10px;
            font-size: 13px; font-weight: 600;
            padding: 0 18px;
        }}
        QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
        QPushButton#primary:pressed {{ background: {ACCENT_PRESS}; }}
        QPushButton#primary:disabled {{ background: {SURFACE_3}; color: {FAINT}; }}

        QPushButton#ghost {{
            background: transparent; color: {DIM};
            border: 1px solid {LINE}; border-radius: 9px;
            font-size: 11.5px; padding: 0 14px;
        }}
        QPushButton#ghost:hover {{ color: {TEXT}; border-color: {LINE_2}; background: {SURFACE}; }}
        QPushButton#ghost:pressed {{ background: {SURFACE_2}; }}

        QPushButton#textBtn {{
            background: transparent; border: none; color: {DIM};
            font-size: 11.5px; padding: 0 4px;
        }}
        QPushButton#textBtn:hover {{ color: {ACCENT}; }}
        QPushButton#textBtn:pressed {{ color: {ACCENT_PRESS}; }}

        QPushButton#small {{
            background: transparent; color: {DIM};
            border: 1px solid {LINE}; border-radius: 8px;
            font-size: 11px; padding: 0 12px;
        }}
        QPushButton#small:hover {{ color: {TEXT}; border-color: {LINE_2}; background: {SURFACE}; }}
        QPushButton#small:pressed {{ background: {SURFACE_2}; }}

        QPushButton#inlineAction {{
            background: transparent; border: none; color: {FAINT};
            font-size: 10px; padding: 0 6px;
        }}
        QPushButton#inlineAction:hover {{ color: {ACCENT}; }}

        QFrame#segmented {{
            background: {SURFACE}; border: 1px solid {LINE};
            border-radius: 10px;
        }}
        QPushButton#segment {{
            background: transparent; color: {DIM};
            border: none; border-radius: 7px;
            font-size: 11.5px; padding: 0 10px;
        }}
        QPushButton#segment:hover {{ color: {TEXT}; }}
        QPushButton#segment:checked {{
            background: {SURFACE_3}; color: {TEXT}; font-weight: 600;
        }}

        QLineEdit {{
            background: {SURFACE}; color: {TEXT};
            border: 1px solid {LINE}; border-radius: 9px;
            padding: 0 12px; font-size: 12px;
            selection-background-color: {ACCENT}; selection-color: {ACCENT_INK};
        }}
        QLineEdit:hover {{ border-color: {LINE_2}; }}
        QLineEdit:focus {{ border-color: {ACCENT}; background: #171411; }}
        QLineEdit::placeholder {{ color: {FAINT}; }}
        QLineEdit#bareInput {{
            background: transparent; border: none; border-radius: 0;
            padding: 0; font-size: 12.5px;
        }}
        QLineEdit#monoInput {{
            font-family: Consolas; font-size: 11.5px;
        }}

        QSlider {{ background: transparent; border: none; }}
        QSlider::groove:horizontal {{
            height: 3px; background: {LINE}; border-radius: 1.5px;
        }}
        QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 1.5px; }}
        QSlider::add-page:horizontal {{ background: {LINE}; border-radius: 1.5px; }}
        QSlider::handle:horizontal {{
            width: 12px; height: 12px; margin: -5px 0;
            border-radius: 6px; background: {TEXT}; border: 1px solid {BG};
        }}
        QSlider::handle:horizontal:hover {{ background: #ffffff; }}

        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
        QScrollBar::handle:vertical {{
            background: #3A332B; border-radius: 4px; min-height: 28px;
        }}
        QScrollBar::handle:vertical:hover {{ background: #4A4238; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

        QToolTip {{
            background: {SURFACE_2}; color: {TEXT};
            border: 1px solid {LINE}; padding: 5px 8px;
        }}
    """


def apply_theme(widget) -> None:
    """构造末尾调用一次：把基础规则挂到窗口根上。"""
    if not widget.objectName():
        widget.setObjectName("root")
    widget.setStyleSheet(base_qss())


def _apply_native_round_corners(widget) -> bool:
    """Windows 11 原生圆角：由 DWM 裁切，边缘带抗锯齿，不产生 mask 毛边。"""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        dwmapi = ctypes.windll.dwmapi
        dwmapi.DwmSetWindowAttribute.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint,
        ]
        dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        result = dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(int(widget.winId())),
            33,  # DWMWA_WINDOW_CORNER_PREFERENCE
            ctypes.byref(preference),
            ctypes.sizeof(preference),
        )
        return result == 0
    except Exception:
        return False


def apply_opaque_shell(widget, card, radius: int = 8) -> None:
    """把无边框窗口做成不透明 + 圆角。

    Windows 上 ``WA_TranslucentBackground`` 会让子 QFrame 的样式表背景
    在真实桌面合成时丢失，整张卡片变成透明且鼠标穿透。这里改为：
    - 顶层自己填暖黑底（保证有像素、可命中鼠标）；
    - Win11 优先用 DWM 原生圆角（抗锯齿边缘），失败才退回 QRegion mask。
    """
    widget.setAttribute(Qt.WA_TranslucentBackground, False)
    widget.setAttribute(Qt.WA_NoSystemBackground, False)
    widget.setAutoFillBackground(True)

    # QFrame 顶层会被 QSS 解析成系统浅色 #efefef，palette 设置不生效；
    # 显式给顶层写一条背景规则，避免卡片四周露出一圈白色 padding。
    widget.setObjectName("opaqueShell")
    shell_rule = f"QWidget#opaqueShell {{ background: {BG}; border: none; }}"
    if shell_rule not in widget.styleSheet():
        widget.setStyleSheet(widget.styleSheet() + "\n" + shell_rule + "\n")

    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    widget.setPalette(palette)

    layout = widget.layout()
    if layout is not None:
        layout.activate()

    def sync_mask() -> None:
        # Win11 原生圆角由 DWM 合成，边缘是抗锯齿的；mask 仅作旧系统兜底。
        if _apply_native_round_corners(widget):
            widget.clearMask()
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(widget.rect()), radius, radius)
        widget.setMask(QRegion(path.toFillPolygon().toPolygon()))

    sync_mask()
    widget._sync_opaque_mask = sync_mask  # type: ignore[attr-defined]
    QTimer.singleShot(0, sync_mask)
