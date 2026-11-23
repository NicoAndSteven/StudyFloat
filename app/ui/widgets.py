"""跨窗口共用的小部件：品牌标、窗口按钮、开关、分段、滑杆行。

这些控件全部自绘，避免依赖字体里的符号（✕ / ▶ 在不同机器上宽度和基线都不一样）。
"""
from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import (
    ACCENT,
    ACCENT_INK,
    ACCENT_PRESS,
    BG,
    DIM,
    FAINT,
    LINE,
    SURFACE,
    SURFACE_2,
    SURFACE_3,
    TEXT,
)


class BrandMark(QWidget):
    """22–24px 品牌标：黄铜渐变方块 + 墨色 S。"""

    def __init__(self, size: int = 22, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self._size, self._size)
        path = QPainterPath()
        path.addRoundedRect(rect, self._size * 0.27, self._size * 0.27)

        grad = QLinearGradient(0, 0, 0, self._size)
        grad.setColorAt(0, QColor("#E9BA71"))
        grad.setColorAt(1, QColor(ACCENT_PRESS))
        p.fillPath(path, grad)
        p.setPen(QPen(QColor(255, 255, 255, 45), 1))
        p.drawPath(path)

        p.setPen(QColor(ACCENT_INK))
        font = QFont()
        font.setFamilies(["Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei UI"])
        font.setPixelSize(max(10, int(self._size * 0.5)))
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, "S")
        p.end()


class GlyphButton(QAbstractButton):
    """最小化 / 关闭：用 1.2px 线条画，不用字体符号。"""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._hover = False
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip("最小化" if kind == "min" else "关闭")

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(SURFACE_3))
            p.drawRoundedRect(QRectF(1, 1, 28, 28), 8, 8)

        p.setPen(QPen(QColor(TEXT if self._hover else DIM), 1.2))
        if self._kind == "min":
            p.drawLine(11, 15, 19, 15)
        else:
            p.drawLine(11, 11, 19, 19)
            p.drawLine(19, 11, 11, 19)
        p.end()


class Hairline(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hairline")
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


class StatusDot(QWidget):
    """8px 状态点。登录 / 成功用黄铜，异常用珊瑚色 —— 不引入第二种绿。"""

    def __init__(self, color: str = FAINT, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(8, 8)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QRectF(0, 0, 8, 8))
        p.end()


class ToggleSwitch(QAbstractButton):
    """40×22 开关，旋钮有 150ms 滑动。轨道 ON 才着色。"""

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knobPos", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, value: float) -> None:
        self._pos = value
        self.update()

    knobPos = Property(float, _get_pos, _set_pos)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)

        track = QRectF(0, 0, 40, 22)
        p.setBrush(QColor(ACCENT if self.isChecked() else "#2B2620"))
        p.drawRoundedRect(track, 11, 11)

        x = 3.0 + self._pos * 18.0
        p.setBrush(QColor("#F7F2E8"))
        p.drawEllipse(QRectF(x, 3, 16, 16))

        if self.hasFocus():
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(220, 168, 90, 120), 1))
            p.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5), 10.5, 10.5)
        p.end()


class SegmentedControl(QFrame):
    """分段选择：选中态是抬起的深色块 + 细边，不用彩色块。"""

    changed = Signal(str)

    def __init__(self, options: list[str], current: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("segmented")
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        row = QHBoxLayout(self)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)
        for option in options:
            btn = QPushButton(option)
            btn.setObjectName("segment")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(26)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._group.addButton(btn)
            self._buttons[option] = btn
            row.addWidget(btn)
            btn.clicked.connect(lambda _=False, value=option: self.changed.emit(value))
        self.setFixedHeight(32)
        self.setValue(current)

    def sizeHint(self):  # noqa: N802
        return QSize(248, 32)

    def setValue(self, value: str) -> None:
        btn = self._buttons.get(value)
        if btn is not None:
            btn.setChecked(True)

    def value(self) -> str:
        checked = self._group.checkedButton()
        return checked.text() if checked else ""


class SliderField(QWidget):
    """滑杆 + 定宽数值。数值列定宽，保证多行滑杆右端齐平。"""

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        formatter,
        width: int = 190,
        parent=None,
    ):
        super().__init__(parent)
        self._formatter = formatter

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.setFixedSize(width, 24)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.setFocusPolicy(Qt.StrongFocus)

        self.value_label = QLabel(formatter(value))
        self.value_label.setObjectName("monoValue")
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setFixedWidth(48)

        row.addWidget(self.slider)
        row.addWidget(self.value_label)
        self.setFixedWidth(width + 12 + 48)
        self.slider.valueChanged.connect(self._on_change)

    def _on_change(self, value: int) -> None:
        self.value_label.setText(self._formatter(value))

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, value: int) -> None:  # noqa: N802
        self.slider.setValue(value)


class FieldRow(QFrame):
    """设置行：左标题 + 一行灰说明，右端控件落在同一条轨道上。"""

    def __init__(self, title: str, desc: str, control: QWidget, parent=None):
        super().__init__(parent)
        self.setFixedHeight(68)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(4)
        self._title = QLabel(title)
        self._title.setObjectName("rowTitle")
        self._desc = QLabel(desc)
        self._desc.setObjectName("rowDesc")
        text.addWidget(self._title)
        text.addWidget(self._desc)

        row.addLayout(text, 1)
        row.addWidget(control, 0, Qt.AlignVCenter)

    def set_desc(self, text: str) -> None:
        self._desc.setText(text)
