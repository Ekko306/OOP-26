"""几何类调整策略：裁剪与旋转（自然单位参数，Clarifications Q1 例外条款）。

- 裁剪：box=(left, top, right, bottom) 像素；须在图界内且宽高>0，越界拒绝
- 旋转：angle 单位为度，正值顺时针，任意实数；expand 语义画布自适应
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from pylightroom.core.adjustments.base import BaseAdjustment
from pylightroom.core.errors import AdjustmentError


class CropAdjustment(BaseAdjustment):
    """裁剪：像素框校验后 crop；越界/宽高≤0 抛 AdjustmentError。"""

    name = "crop"
    param_schema = {"box": {"default": None}}

    def _coerce(self, key: str, value: Any) -> Any:
        if key != "box":
            return value
        if isinstance(value, (list, tuple)) and len(value) == 4:
            try:
                left, top, right, bottom = (float(v) for v in value)
            except (TypeError, ValueError) as exc:
                raise AdjustmentError(f"'crop': box 含非数值元素: {value!r}") from exc
        else:
            raise AdjustmentError(
                f"'crop': box 必须为 (left, top, right, bottom) 四元组，得到 {value!r}"
            )
        if not (right > left and bottom > top):
            raise AdjustmentError(
                f"'crop': box 宽高必须 >0（得到 right-left={right - left}, "
                f"bottom-top={bottom - top}）"
            )
        return (left, top, right, bottom)

    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        left, top, right, bottom = params["box"]
        width, height = image.size
        if left < 0 or top < 0 or right > width or bottom > height:
            raise AdjustmentError(
                f"'crop': 裁剪框 {params['box']} 超出图像边界 "
                f"{width}x{height}（Edge Cases：拒绝并报参数错误）"
            )
        return image.crop((int(left), int(top), int(right), int(bottom)))


class RotateAdjustment(BaseAdjustment):
    """旋转：角度正值顺时针（PIL rotate 逆时针故取负），expand 画布自适应。"""

    name = "rotate"
    param_schema = {"angle": {"default": 0.0}}

    def _coerce(self, key: str, value: Any) -> Any:
        if key != "angle":
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AdjustmentError(f"'rotate': angle 必须为数值（度），得到 {value!r}")
        return float(value)

    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        angle = params["angle"]
        # PIL rotate 正值逆时针；本契约正值顺时针 → 取负；expand 反映新画布尺寸
        rotated = image.rotate(
            -angle,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor=(255, 255, 255),
        )
        return rotated.convert("RGB")
