"""色彩类调整策略：色温（BGR 增益）与直方图均衡（仅亮度通道 CLAHE）。

- 色温：factor>1 偏暖（增 R 减 B），factor<1 偏冷；1.0 中性（research D3）
- 直方图均衡：RGB → YCrCb → 仅 Y 通道 CLAHE → 转回；禁止 RGB 分通道均衡
  （FR-005，准则技术栈约束）；factor=1.0 不启用，>1 映射 clipLimit 逐级增强
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from pylightroom.core.adjustments.base import BaseAdjustment
from pylightroom.core.errors import AdjustmentError

_FACTOR_SCHEMA = {"factor": {"min": 0.0, "max": 2.0, "default": 1.0}}

# 色温增益强度：factor 偏离 1.0 的部分映射到最大 40% 的通道增益偏移
_TEMP_GAIN_SCALE = 0.4


class TemperatureAdjustment(BaseAdjustment):
    """色温：factor → R/B 通道反向增益（OpenCV/numpy 矩阵实现）。"""

    name = "temperature"
    param_schema = _FACTOR_SCHEMA

    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        offset = params["factor"] - 1.0
        if offset == 0.0:
            return image.copy()
        r_gain = 1.0 + _TEMP_GAIN_SCALE * offset
        b_gain = 1.0 - _TEMP_GAIN_SCALE * offset
        arr = np.asarray(image.convert("RGB"), dtype=np.float32)
        arr[:, :, 0] *= r_gain
        arr[:, :, 2] *= b_gain
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")


class HistogramEqualizationAdjustment(BaseAdjustment):
    """直方图均衡：仅亮度通道 CLAHE，clipLimit 由 factor 映射。"""

    name = "histogram_equalization"
    param_schema = _FACTOR_SCHEMA

    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        factor = params["factor"]
        if factor <= 1.0:
            return image.copy()  # 1.0 中性：不启用
        rgb = np.asarray(image.convert("RGB"))
        ycrcb = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
        clahe = cv2.createCLAHE(clipLimit=self._clip_limit(factor), tileGridSize=(8, 8))
        ycrcb[:, :, 0] = clahe.apply(ycrcb[:, :, 0])
        equalized = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)
        return Image.fromarray(equalized, mode="RGB")

    @staticmethod
    def _clip_limit(factor: float) -> float:
        # factor ∈ (1.0, 2.0] → clipLimit ∈ (0, 16]；1.0 恒为 0（不启用）
        return round((factor - 1.0) * 16.0, 4)
