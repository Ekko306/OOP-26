"""引擎对外事件回调协议（contracts/core-api.md §6，准则 I）。

引擎对外通知的唯一出口：渲染完成、进度、错误三类事件。
仅传递原始数据与消息对象（task_id/stage/fraction/image_bytes/message），
禁止任何 UI 组件或框架对象穿越。引擎侧为可选注入，None 时静默（FR-024）。
"""

from __future__ import annotations

from typing import Protocol


class EngineEvents(Protocol):
    """结构化 duck-typing 协议：由桥接层实现并注入引擎。"""

    def on_progress(self, task_id: str, stage: str, fraction: float) -> None:
        """渲染/导出进度通知。fraction ∈ [0.0, 1.0]。"""
        ...

    def on_render_complete(self, task_id: str, image_bytes: bytes) -> None:
        """某级预览渲染完成通知，携带 PNG 编码的图像字节。"""
        ...

    def on_error(self, task_id: str, message: str) -> None:
        """任务失败通知，携带人类可读原因。"""
        ...
