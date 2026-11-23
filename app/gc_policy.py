"""只在 Qt 主线程执行 Python 循环 GC。

CPython 的自动循环 GC 会在**任意分配对象的线程**里触发。解析线程里
yt-dlp / curl_cffi 会大量分配，很容易在那里触发一次 full GC；如果此时
主线程遗留了不可达的 QWidget 引用环（例如已关闭的扫码/分P窗口），
PySide 就会在错误的线程里销毁 Qt 对象，表现为进程直接消失
（Windows 事件日志：Qt6Core.dll 0xc0000005，栈在
QBindingStorage::clear；或 Qt 的 qFatal → ucrtbase 0xc0000409）。

策略：关闭自动循环 GC，改由一个主线程 QTimer 按原阈值手动回收。
引用计数仍然即时生效，只是"引用环"统一在主线程处理。
"""
from __future__ import annotations

import gc

from PySide6.QtCore import QObject, QTimer, Slot

# 与 CPython 默认阈值一致：gen0 700、gen1 10、gen2 10。
GEN0_THRESHOLD = 700
GEN1_THRESHOLD = 10
GEN2_THRESHOLD = 10


class MainThreadGC(QObject):
    """自动 GC 的替代品：所有 ``gc.collect()`` 都发生在主线程。"""

    def __init__(self, parent=None, interval_ms: int = 2000):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.collect_if_needed)

    def start(self) -> None:
        gc.disable()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    @Slot()
    def collect_if_needed(self) -> None:
        gen0, gen1, gen2 = gc.get_count()
        if gen0 > GEN0_THRESHOLD or gen1 > GEN1_THRESHOLD or gen2 > GEN2_THRESHOLD:
            gc.collect()

    def collect_now(self) -> None:
        """在明确安全的主线程时点主动回收（如窗口关闭后）。"""
        gc.collect()
