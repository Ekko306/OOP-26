"""桥接层（State）：Reflex 状态定义、事件转发、把引擎结果转成 UI 可消费的数据。

本层是唯一允许同时 import Reflex（界面框架）与 pylightroom.core（核心引擎）的层，
只做「胶水」：参数转换 + 引擎调用 + 状态回写，不含任何业务规则（准则 I）。
公共导出面走 PEP 562 惰性导出（与 core/__init__ 风格一致，001）。
"""

from __future__ import annotations

__all__: list[str] = ["DevelopState", "FileState"]


def __getattr__(name: str):  # PEP 562 惰性导出：仅按需拉起 Reflex
    if name == "DevelopState":
        from pylightroom.state.develop_state import DevelopState

        return DevelopState
    if name == "FileState":
        from pylightroom.state.file_state import FileState

        return FileState
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
