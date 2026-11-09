"""HistogramCalculator：RGB 三通道直方图统计（FR-023，D6）。

输出 {"r","g","b"} 各 256 bin 计数数组，UI 绘图可直接消费。
"""

from __future__ import annotations

from PIL import Image


class HistogramCalculator:
    @staticmethod
    def compute(image: Image.Image) -> dict[str, list[int]]:
        """输入任意模式图像，统一转 RGB 后按通道拆分 768 bin。"""
        hist = image.convert("RGB").histogram()
        return {
            "r": hist[0:256],
            "g": hist[256:512],
            "b": hist[512:768],
        }
