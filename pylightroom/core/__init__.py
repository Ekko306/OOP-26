"""PyLightroom 核心引擎层公共导出面（contracts/core-api.md）。

上层只允许依赖本包导出的契约名称（准则 IV）。
本包导入时执行架构红线自检（research D2 语义）：仅当 reflex 在「core
导入链本次执行期间」被新引入时抛 EngineError——桥接层先 import Reflex
再导入 core 属正常分层，不触发红线；core 自身不得依赖界面框架（grep
断言另行覆盖）。
"""

from __future__ import annotations

import importlib
import sys

_snapshot_before_core_chain = set(sys.modules)  # core 导入链执行前快照（D2）

from pylightroom.core.errors import (
    AdjustmentError,
    AssetError,
    EngineError,
    ExportError,
    HistoryError,
    SidecarError,
)
from pylightroom.core.events import EngineEvents

__all__ = [
    "ImageProcessor",
    "AdjustmentFactory",
    "AssetFactory",
    "BaseAdjustment",
    "BaseImageAsset",
    "EditSession",
    "SidecarFile",
    "PreviewCache",
    "HistogramCalculator",
    "EngineEvents",
    "EngineError",
    "AssetError",
    "AdjustmentError",
    "HistoryError",
    "SidecarError",
    "ExportError",
]


def _check_no_ui_framework(before: set[str]) -> None:
    """红线自检钩子（D2）：core 导入链增量检测。

    `before` 为导入链执行前的 sys.modules 快照；仅差集中「新出现」的
    界面框架（reflex）才判定违规——进程内先有 Reflex 再导入 core 放行。
    """
    offenders = sorted(
        name
        for name in sys.modules
        if (name == "reflex" or name.startswith("reflex.")) and name not in before
    )
    if offenders:
        raise EngineError(
            "架构红线违规：core 导入链中新引入界面框架 " + ", ".join(offenders)
        )


_check_no_ui_framework(_snapshot_before_core_chain)

_LAZY_EXPORTS = {
    "ImageProcessor": "pylightroom.core.pipeline",
    "PreviewCache": "pylightroom.core.pipeline",
    "AdjustmentFactory": "pylightroom.core.adjustments.factory",
    "AssetFactory": "pylightroom.core.assets.factory",
    "BaseAdjustment": "pylightroom.core.adjustments.base",
    "BaseImageAsset": "pylightroom.core.assets.base",
    "EditSession": "pylightroom.core.history",
    "SidecarFile": "pylightroom.core.persistence",
    "HistogramCalculator": "pylightroom.core.histogram",
}


def __getattr__(name: str):  # PEP 562 惰性导出，避免包导入即拉起全部子模块
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    before = set(sys.modules)
    module = importlib.import_module(module_path)
    _check_no_ui_framework(before)  # 惰性导入链同样做增量检测（D2）
    return getattr(module, name)
