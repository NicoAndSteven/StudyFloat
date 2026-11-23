"""离屏渲染 UI 截图，用来做视觉验收（不弹窗、不依赖桌面分辨率）。

用法：
    .\\.venv\\Scripts\\python.exe tools\\render_ui.py --out demo_out
    .\\.venv\\Scripts\\python.exe tools\\render_ui.py --only settings --page playback
    .\\.venv\\Scripts\\python.exe tools\\render_ui.py --only parts

原理：用真实 windows 平台插件渲染（offscreen 插件的中文字体会出豆腐块），
窗口挪到屏幕外再 widget.grab()，最后合成到一块中性背景上。
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QFrame  # noqa: E402

from app.config import Config  # noqa: E402
from app.source.bilibili_parts import PartInfo  # noqa: E402
from app.ui.launcher import Launcher  # noqa: E402
from app.ui.part_picker_dialog import PartPickerDialog  # noqa: E402
from app.ui.qr_login_dialog import QRLoginDialog  # noqa: E402
from app.ui.settings_dialog import SettingsDialog  # noqa: E402
from app.ui.theme import app_font  # noqa: E402

PAD = 48


def _backdrop(w: int, h: int) -> QImage:
    """中性冷灰桌面：暖色窗口在上面才看得出是暖的。"""
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    base = QLinearGradient(0, 0, 0, h)
    base.setColorAt(0, QColor("#2B2D31"))
    base.setColorAt(0.55, QColor("#212327"))
    base.setColorAt(1, QColor("#181A1D"))
    p.fillRect(0, 0, w, h, base)

    glow = QRadialGradient(QPointF(w * 0.5, h * 0.42), max(w, h) * 0.6)
    glow.setColorAt(0, QColor(255, 248, 235, 14))
    glow.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, h, glow)
    p.end()
    return img


def render(widget, out: Path, flat: bool = False, focus=None) -> None:
    widget.move(-6000, -6000)
    if hasattr(widget, "_centered"):
        widget._centered = True
    if flat:
        for child in widget.findChildren(QFrame):
            if child.graphicsEffect() is not None:
                child.setGraphicsEffect(None)
    widget.show()
    app = QApplication.instance()
    for _ in range(5):
        app.processEvents()
    if focus is not None:
        focus.setFocus()
        app.processEvents()

    shot: QPixmap = widget.grab()
    dpr = shot.devicePixelRatio() or 1.0
    w = int((shot.width() / dpr + PAD * 2) * dpr)
    h = int((shot.height() / dpr + PAD * 2) * dpr)
    canvas = _backdrop(w, h)
    canvas.setDevicePixelRatio(dpr)
    p = QPainter(canvas)
    p.drawPixmap(PAD, PAD, shot)
    p.end()
    canvas.save(str(out))
    print(f"{out}  {shot.width() / dpr:.0f}x{shot.height() / dpr:.0f}")


def _sample_parts() -> list[PartInfo]:
    titles = [
        "课程导论：这门课解决什么问题",
        "环境搭建与第一个练习",
        "核心概念一：从现象到模型",
        "核心概念二：边界条件与常见误区",
        "案例拆解：一次完整的推演",
        "进阶技巧：把结论落到具体动作",
        "作业讲解与答疑",
        "阶段复盘：把零散知识串成线",
    ]
    return [
        PartInfo(page=i + 1, cid=1000 + i, title=t, duration=780 + i * 60)
        for i, t in enumerate(titles)
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="demo_out")
    ap.add_argument(
        "--only",
        choices=["all", "launcher", "settings", "parts", "qr"],
        default="all",
    )
    ap.add_argument(
        "--page",
        choices=["account", "playback", "window", "all"],
        default="all",
        help="settings 只渲染某一页；默认三页都出",
    )
    ap.add_argument("--logged-in", action="store_true", help="伪造已登录状态")
    ap.add_argument("--flat", action="store_true", help="去掉投影，用于检查文字锐度")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    app.setFont(app_font())

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    tmp = None
    if args.logged_in:
        tmp = tempfile.mkdtemp()
        Path(tmp, "qr_cookies.txt").write_text("# fake\n", encoding="utf-8")
        os.chdir(tmp)
        suffix = "_logged"
    else:
        suffix = ""

    config = Config(cookie_path=r"C:\Users\Coco\cookies.txt" if args.logged_in else "")

    if args.only in ("all", "launcher"):
        launcher = Launcher(config)
        render(launcher, out / f"launcher{suffix}.png", args.flat)

    if args.only in ("all", "settings"):
        pages = ["account", "playback", "window"] if args.page == "all" else [args.page]
        for page in pages:
            dlg = SettingsDialog(config)
            dlg.set_page(page)
            dlg.cookie.clearFocus()
            render(dlg, out / f"settings_{page}{suffix}.png", args.flat, focus=dlg)

    if args.only in ("all", "parts"):
        picker = PartPickerDialog(_sample_parts(), "示例课程：从入门到独立完成", highlight_page=3)
        render(picker, out / "parts.png", args.flat)

    if args.only in ("all", "qr"):
        qr = QRLoginDialog("", start_worker=False)
        qr.qr.set_url("https://passport.bilibili.com/h5-app/universal-login?qrcode_key=demo")
        qr.status.setText("等待手机确认…")
        render(qr, out / "qr.png", args.flat)

    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
