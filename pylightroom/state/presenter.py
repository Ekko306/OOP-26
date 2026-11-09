"""Presenter：引擎事件 → 桥接状态的事件翻译器（纯 Python，内部模块）。

引擎回调的唯一消费者与桥接层的线程边界：高分回调来自后台 daemon 线程，
全部可变状态由 threading.Condition 的锁保护；「版本新者胜」丢弃乱序旧帧；
data URL 即时编码（research D5）。

仅 import pylightroom.core 与标准库，不含 Reflex（contracts/state-api.md §4：
UI 与测试以外的代码不得引用本模块）。
"""

from __future__ import annotations

import base64
import re
import threading
import time
from typing import NamedTuple

_TASK_PATTERN = re.compile(r"^preview-(thumb|medium|full)-v(\d+)$")


class PreviewResult(NamedTuple):
    """单级预览结果（不可变值对象，层间仅传递原始数据）。"""

    version: int
    image_bytes: bytes
    data_url: str


class Presenter:
    """实现引擎 EngineEvents 协议；线程安全的预览结果信箱。"""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._results: dict[str, PreviewResult] = {}
        self._error: str | None = None
        self._error_version: int = -1
        self._busy: bool = False

    # ------------------------------------------------------------------
    # EngineEvents 协议实现（回调可能来自后台线程）
    # ------------------------------------------------------------------
    def on_progress(self, task_id: str, stage: str, fraction: float) -> None:
        with self._condition:
            self._busy = True

    def on_render_complete(self, task_id: str, image_bytes: bytes) -> None:
        parsed = _TASK_PATTERN.match(task_id)
        if parsed is None:
            return  # 无法解析的 task_id：不触碰结果容器
        level, version = parsed.group(1), int(parsed.group(2))
        data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode(
            "ascii"
        )
        with self._condition:
            existing = self._results.get(level)
            if existing is None or version > existing.version:  # 新者胜
                self._results[level] = PreviewResult(version, image_bytes, data_url)
            if level == "full":
                self._busy = False
            self._condition.notify_all()

    def on_error(self, task_id: str, message: str) -> None:
        parsed = _TASK_PATTERN.match(task_id)
        with self._condition:
            if parsed is None:
                self._error = message  # 仅记录消息，不影响结果容器
            else:
                version = int(parsed.group(2))
                if version >= self._error_version:  # 新 version 错误覆盖旧错误
                    self._error = message
                    self._error_version = version
                if parsed.group(1) == "full":
                    self._busy = False
            self._condition.notify_all()

    # ------------------------------------------------------------------
    # 供桥接处理器消费的信箱接口
    # ------------------------------------------------------------------
    @property
    def busy(self) -> bool:
        with self._condition:
            return self._busy

    @property
    def error_message(self) -> str:
        with self._condition:
            return self._error or ""

    @property
    def error_version(self) -> int:
        """最近错误所属版本（桥接层按版本门控回显，避免旧错复现）。"""
        with self._condition:
            return self._error_version

    def latest(self, level: str) -> PreviewResult | None:
        with self._condition:
            return self._results.get(level)

    def wait_for(self, level: str, version: int, timeout: float) -> bool:
        """有界等待指定级别的 ≥ version 结果（research D4，Condition 非轮询）。

        命中返回 True；超时或对应版本的错误到达返回 False。
        """
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                result = self._results.get(level)
                if result is not None and result.version >= version:
                    return True
                if self._error is not None and self._error_version >= version:
                    return False
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)

    def reset(self) -> None:
        """清空全部结果、错误与忙碌标志（切换会话时调用）。"""
        with self._condition:
            self._results.clear()
            self._error = None
            self._error_version = -1
            self._busy = False
            self._condition.notify_all()
