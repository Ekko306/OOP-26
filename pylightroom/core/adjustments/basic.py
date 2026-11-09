"""基础调整策略：亮度/对比度/饱和度/锐度（Pillow ImageEnhance 因子直通，research D3）。

刻度 0.0–2.0，1.0 中性（ImageEnhance 原生语义），FR-002。
"""

from __future__ import annotations

from PIL import Image, ImageEnhance

from pylightroom.core.adjustments.base import BaseAdjustment

_FACTOR_SCHEMA = {"factor": {"min": 0.0, "max": 2.0, "default": 1.0}}


class BrightnessAdjustment(BaseAdjustment):
    """亮度：factor 直通 ImageEnhance.Brightness。"""

    name = "brightness"
    param_schema = _FACTOR_SCHEMA

    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        return ImageEnhance.Brightness(image).enhance(params["factor"])


class ContrastAdjustment(BaseAdjustment):
    """对比度：factor 直通 ImageEnhance.Contrast。"""

    name = "contrast"
    param_schema = _FACTOR_SCHEMA

    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        return ImageEnhance.Contrast(image).enhance(params["factor"])


class SaturationAdjustment(BaseAdjustment):
    """饱和度：factor 直通 ImageEnhance.Color。"""

    name = "saturation"
    param_schema = _FACTOR_SCHEMA

    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        return ImageEnhance.Color(image).enhance(params["factor"])


class SharpnessAdjustment(BaseAdjustment):
    """锐度：factor 直通 ImageEnhance.Sharpness。"""

    name = "sharpness"
    param_schema = _FACTOR_SCHEMA

    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        return ImageEnhance.Sharpness(image).enhance(params["factor"])
