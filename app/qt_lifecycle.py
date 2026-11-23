"""Qt 对象延迟销毁时的 Python 保活。

``QObject.deleteLater()`` 只是把 C++ 删除排进事件队列；如果 Python 包装
对象在事件处理前就被 GC，PySide 可能立即 delete 同一个 C++ 对象，随后
DeferredDelete 再访问已释放内存。这里用一个模块级集合持有包装对象，直到
``destroyed`` 信号真正到达才放手。
"""
from __future__ import annotations

from PySide6.QtCore import QObject

_PENDING: set[QObject] = set()


def retire(obj: QObject | None) -> None:
    """请求 deleteLater，并保证销毁完成前 Python 包装不会被回收。"""
    if obj is None:
        return
    _PENDING.add(obj)

    def _done(*_args, _obj=obj) -> None:
        _PENDING.discard(_obj)

    try:
        obj.destroyed.connect(_done)
        obj.deleteLater()
    except RuntimeError:
        # C++ 对象已经销毁（例如父对象先走一步），包装对象可以直接放手。
        _PENDING.discard(obj)


def pending_count() -> int:
    return len(_PENDING)
