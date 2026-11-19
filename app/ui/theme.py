"""StudyFloat 统一样式：深色现代简约。

所有窗口共用这套配色/组件 QSS，避免样式漂移。
"""
from __future__ import annotations

# 主题色
BG = "#16181d"
PANEL = "#20232b"
PANEL_ALT = "#262a35"
BORDER = "#343846"
PRIMARY_START = "#3b82f6"
PRIMARY_END = "#06b6d4"
TEXT = "#e8e8ec"
TEXT_DIM = "#9aa0ac"
TEXT_FAINT = "#6f7480"
SUCCESS = "#4ade80"
ERROR = "#f87171"

# 主按钮（渐变蓝）—— QSS 用 qlineargradient 模拟现代渐变
BTN_PRIMARY = f"""
    QPushButton {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {PRIMARY_START}, stop:1 {PRIMARY_END});
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #4f92f7, stop:1 #22c9e0);
    }}
    QPushButton:pressed {{ background: {PRIMARY_START}; }}
    QPushButton:disabled {{ background: #3a3f4b; color: #7c8290; }}
"""

BTN_SECONDARY = f"""
    QPushButton {{
        background: {PANEL_ALT};
        color: #c8ccd6;
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 8px 12px;
    }}
    QPushButton:hover {{ background: #303544; border-color: #4a5060; }}
    QPushButton:pressed {{ background: {PANEL}; }}
"""

INPUT = f"""
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {PANEL_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {PRIMARY_START};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {PRIMARY_START};
    }}
    QLineEdit::placeholder {{ color: {TEXT_FAINT}; }}
"""

CHECKBOX = f"""
    QCheckBox {{ color: {TEXT}; spacing: 8px; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {BORDER};
        border-radius: 4px;
        background: {PANEL_ALT};
    }}
    QCheckBox::indicator:checked {{
        background: {PRIMARY_START};
        border-color: {PRIMARY_START};
    }}
"""

LIST = f"""
    QListWidget {{
        background: {PANEL_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 4px;
    }}
    QListWidget::item {{ padding: 7px 9px; border-radius: 6px; }}
    QListWidget::item:hover {{ background: #2f3442; }}
    QListWidget::item:selected {{ background: {PRIMARY_START}; color: #ffffff; }}
"""

LABEL_DIM = f"QLabel {{ color: {TEXT_DIM}; }}"
LABEL_TEXT = f"QLabel {{ color: {TEXT}; }}"

# 窗口外框
WINDOW = f"""
    QWidget#root, QDialog#root {{
        background: {BG};
    }}
"""


def apply_theme(widget) -> None:
    """给窗口套用统一深色主题（在构造末尾调用）。"""
    widget.setStyleSheet(
        f"""
        * {{ font-family: "Microsoft YaHei UI", "Segoe UI", system-ui; font-size: 12px; }}
        QWidget {{ background: {BG}; color: {TEXT}; }}
        QLabel {{ color: {TEXT}; }}
        QDialog {{ background: {BG}; }}
        QCheckBox {{ color: {TEXT}; spacing: 8px; }}
        QCheckBox::indicator {{
            width: 16px; height: 16px;
            border: 1px solid {BORDER}; border-radius: 4px; background: {PANEL_ALT};
        }}
        QCheckBox::indicator:checked {{ background: {PRIMARY_START}; border-color: {PRIMARY_START}; }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background: {PANEL_ALT}; color: {TEXT};
            border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 10px;
            selection-background-color: {PRIMARY_START};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border-color: {PRIMARY_START};
        }}
        QLineEdit::placeholder {{ color: {TEXT_FAINT}; }}
        QListWidget {{
            background: {PANEL_ALT}; color: {TEXT};
            border: 1px solid {BORDER}; border-radius: 10px; padding: 4px;
        }}
        QListWidget::item {{ padding: 7px 9px; border-radius: 6px; }}
        QListWidget::item:hover {{ background: #2f3442; }}
        QListWidget::item:selected {{ background: {PRIMARY_START}; color: #ffffff; }}
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: #3a4050; border-radius: 4px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """
    )


def style_primary_button(button) -> None:
    button.setStyleSheet(BTN_PRIMARY)


def style_secondary_button(button) -> None:
    button.setStyleSheet(BTN_SECONDARY)
