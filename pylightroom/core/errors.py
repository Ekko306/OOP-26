"""引擎异常体系（contracts/core-api.md §7）。

五类格式化异常均继承公共基类 EngineError；触发条件：
- AssetError      不支持格式、文件损坏、RAW 解码失败（含路径与原因）
- AdjustmentError 未注册调整名、参数越界/非法
- HistoryError    空栈撤销/空栈重做
- SidecarError    JSON 损坏、未知指令类型、版本不识别
- ExportError     渲染或写出失败（保证无半成品）
"""

from __future__ import annotations


class EngineError(Exception):
    """引擎异常公共基类：统一携带 message、可选 path 与 reason。"""

    def __init__(
        self,
        message: str,
        *,
        path: object = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.path = str(path) if path is not None else None
        self.reason = reason


class AssetError(EngineError):
    """图像资产加载/解码失败（不支持格式、损坏、RAW 失败等）。"""


class AdjustmentError(EngineError):
    """调整指令错误（未注册名、参数越界/非法、序列化数据非法）。"""


class HistoryError(EngineError):
    """历史操作错误（空栈撤销、空重做栈重做）。"""


class SidecarError(EngineError):
    """Sidecar 参数文件错误（JSON 损坏、未知指令类型、版本不识别、无关联原图）。"""


class ExportError(EngineError):
    """导出失败（渲染或写出失败；保证不留半成品）。"""
