"""PyLightroom 核心引擎层公共导出面（contracts/core-api.md）。

上层只允许依赖本包导出的契约名称（准则 IV）。
本包导入时执行架构红线自检：导入链中不得出现任何界面框架（reflex）。
"""

from __future__ import annotations

import sys

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


def _check_no_ui_framework() -> None:
    """红线自检钩子：导入本包后 sys.modules 不得含界面框架（准则 I）。"""
    offenders = sorted(m for m in sys.modules if m.split(".")[0] == "reflex")
    if offenders:
        raise EngineError(
            "架构红线违规：core 导入链中出现界面框架 " + ", ".join(offenders)
        )


_check_no_ui_framework()


def __getattr__(name: str):  # PEP 562 惰性导出，避免包导入即拉起全部子模块
    if name == "ImageProcessor":
        from pylightroom.core.pipeline import ImageProcessor

        return ImageProcessor
    if name == "PreviewCache":
        from pylightroom.core.pipeline import PreviewCache

        return PreviewCache
    if name == "AdjustmentFactory":
        from pylightroom.core.adjustments.factory import AdjustmentFactory

        return AdjustmentFactory
    if name == "AssetFactory":
        from pylightroom.core.assets.factory import AssetFactory

        return AssetFactory
    if name == "BaseAdjustment":
        from pylightroom.core.adjustments.base import BaseAdjustment

        return BaseAdjustment
    if name == "BaseImageAsset":
        from pylightroom.core.assets.base import BaseImageAsset

        return BaseImageAsset
    if name == "EditSession":
        from pylightroom.core.history import EditSession

        return EditSession
    if name == "SidecarFile":
        from pylightroom.core.persistence import SidecarFile

        return SidecarFile
    if name == "HistogramCalculator":
        from pylightroom.core.histogram import HistogramCalculator

        return HistogramCalculator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
