"""US5 直方图测试：RGB 三通道 256 bin（FR-023，D6）。"""

from __future__ import annotations

import pytest
from PIL import Image

from pylightroom.core.histogram import HistogramCalculator


class TestHistogramContract:
    def test_output_format(self, rgb_image):
        result = HistogramCalculator.compute(rgb_image)
        assert set(result) == {"r", "g", "b"}
        for channel in result.values():
            assert len(channel) == 256

    def test_solid_color_peaks(self):
        image = Image.new("RGB", (16, 16), (200, 100, 50))
        result = HistogramCalculator.compute(image)
        assert result["r"].index(max(result["r"])) == 200
        assert result["g"].index(max(result["g"])) == 100
        assert result["b"].index(max(result["b"])) == 50

    def test_counts_sum_to_pixel_count(self, rgb_image):
        n = rgb_image.size[0] * rgb_image.size[1]
        result = HistogramCalculator.compute(rgb_image)
        for name, channel in result.items():
            assert sum(channel) == n, f"{name} 通道计数总和应等于像素数"

    def test_non_rgb_input_converted(self):
        gray = Image.new("L", (8, 8), 128)
        result = HistogramCalculator.compute(gray)
        assert set(result) == {"r", "g", "b"}, "非 RGB 输入须统一转换"
