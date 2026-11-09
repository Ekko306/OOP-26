"""组合根：单一引擎会话（ImageProcessor 与 Presenter 的绑定）。

state 层各 State 经 get_session() 取用同一会话；set_session() 仅供测试
注入替身（contracts/state-api.md §4：UI 不得直接引用本模块）。
单用户单会话语义：进程内至多一个打开的编辑会话。
"""

from __future__ import annotations

import threading

from pylightroom.core import ImageProcessor

from pylightroom.state.presenter import Presenter


class EngineSession:
    """处理器与事件翻译器的单一绑定。"""

    def __init__(
        self,
        processor: ImageProcessor | None = None,
        presenter: Presenter | None = None,
    ) -> None:
        self.presenter = presenter if presenter is not None else Presenter()
        self.processor = (
            processor if processor is not None else ImageProcessor(events=self.presenter)
        )


_session: EngineSession | None = None
_session_lock = threading.Lock()


def get_session() -> EngineSession:
    """返回进程内唯一会话；首次调用时创建（处理器注入 presenter）。"""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = EngineSession()
    return _session


def set_session(session: EngineSession | None) -> None:
    """替换/清空当前会话；仅供测试注入替身使用。"""
    global _session
    with _session_lock:
        _session = session
