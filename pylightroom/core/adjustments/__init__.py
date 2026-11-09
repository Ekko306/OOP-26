"""调整策略族（继承体系一）：内置 8 类策略在此统一注册（T016）。"""

from __future__ import annotations

from pylightroom.core.adjustments.base import BaseAdjustment
from pylightroom.core.adjustments.basic import (
    BrightnessAdjustment,
    ContrastAdjustment,
    SaturationAdjustment,
    SharpnessAdjustment,
)
from pylightroom.core.adjustments.color import (
    HistogramEqualizationAdjustment,
    TemperatureAdjustment,
)
from pylightroom.core.adjustments.factory import AdjustmentFactory
from pylightroom.core.adjustments.geometry import CropAdjustment, RotateAdjustment

__all__ = [
    "AdjustmentFactory",
    "BaseAdjustment",
    "BrightnessAdjustment",
    "ContrastAdjustment",
    "SaturationAdjustment",
    "SharpnessAdjustment",
    "TemperatureAdjustment",
    "HistogramEqualizationAdjustment",
    "CropAdjustment",
    "RotateAdjustment",
]

# 内置注册：新增子类请在此（或运行期）调用 AdjustmentFactory.register()
AdjustmentFactory.register(BrightnessAdjustment)
AdjustmentFactory.register(ContrastAdjustment)
AdjustmentFactory.register(SaturationAdjustment)
AdjustmentFactory.register(SharpnessAdjustment)
AdjustmentFactory.register(TemperatureAdjustment)
AdjustmentFactory.register(HistogramEqualizationAdjustment)
AdjustmentFactory.register(CropAdjustment)
AdjustmentFactory.register(RotateAdjustment)
