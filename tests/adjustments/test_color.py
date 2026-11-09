"""US1 色彩类调整测试：色温与直方图均衡（FR-005）。"""

from __future__ import annotations

import pytest

from pylightroom.core.adjustments.color import (
    HistogramEqualizationAdjustment,
    TemperatureAdjustment,
)
from pylightroom.core.errors import AdjustmentError
from tests.conftest import assert_pixel_equal, mean_channel_values


class TestTemperature:
    def test_warm_shift_raises_red_lowers_blue(self, rgb_image):
        r0, _g0, b0 = mean_channel_values(rgb_image)
        out = TemperatureAdjustment({"factor": 1.5}).apply(rgb_image, {"factor": 1.5})
        r1, _g1, b1 = mean_channel_values(out)
        assert r1 > r0, "factor>1 应偏暖（R 通道均值上升）"
        assert b1 < b0, "factor>1 应偏暖（B 通道均值下降）"

    def test_cool_shift_raises_blue_lowers_red(self, rgb_image):
        r0, _g0, b0 = mean_channel_values(rgb_image)
        out = TemperatureAdjustment({"factor": 0.5}).apply(rgb_image, {"factor": 0.5})
        r1, _g1, b1 = mean_channel_values(out)
        assert b1 > b0, "factor<1 应偏冷（B 通道均值上升）"
        assert r1 < r0, "factor<1 应偏冷（R 通道均值下降）"

    def test_neutral_factor_identity(self, rgb_image):
        out = TemperatureAdjustment({"factor": 1.0}).apply(rgb_image, {"factor": 1.0})
        assert_pixel_equal(out, rgb_image, "factor=1.0 应为中性输出")

    def test_direction_monotonic(self, rgb_image):
        means = []
        for factor in (0.5, 1.0, 1.5):
            out = TemperatureAdjustment({"factor": factor}).apply(
                rgb_image, {"factor": factor}
            )
            means.append(mean_channel_values(out)[0])
        assert means[0] < means[1] < means[2], "R 通道应随 factor 单调上升"

    @pytest.mark.parametrize("factor", [-0.1, 2.1])
    def test_out_of_range_raises(self, factor):
        with pytest.raises(AdjustmentError):
            TemperatureAdjustment({"factor": factor})

    def test_round_trip(self, rgb_image):
        adjustment = TemperatureAdjustment({"factor": 1.4})
        original = adjustment.apply(rgb_image, adjustment.params)
        rebuilt = TemperatureAdjustment.deserialize(adjustment.serialize())
        assert_pixel_equal(
            rebuilt.apply(rgb_image, rebuilt.params), original, "往返无损（SC-002）"
        )


class TestHistogramEqualization:
    def test_factor_1_not_enabled(self, gradient_image):
        out = HistogramEqualizationAdjustment({"factor": 1.0}).apply(
            gradient_image, {"factor": 1.0}
        )
        assert_pixel_equal(out, gradient_image, "factor=1.0 不启用均衡")

    @staticmethod
    def _std(image):
        hist = image.convert("L").histogram()
        n = sum(hist)
        mean = sum(v * c for v, c in enumerate(hist)) / n
        return (sum(((v - mean) ** 2) * c for v, c in enumerate(hist)) / n) ** 0.5

    def test_factor_above_1_enhances_contrast(self, gradient_image):
        # 构造低对比度输入（值域压缩至 100–155），CLAHE 均衡后应扩展动态范围
        from PIL import Image

        low_contrast = Image.eval(gradient_image, lambda v: 100 + (v * 55) // 255)
        before = self._std(low_contrast)
        out = HistogramEqualizationAdjustment({"factor": 1.5}).apply(
            low_contrast, {"factor": 1.5}
        )
        assert self._std(out) > before, "factor>1 应增强对比度"

    def test_luminance_only_preserves_channel_ordering(self, rgb_image):
        """仅亮度通道均衡：RGB 通道间相对次序（色调结构）不被破坏（FR-005）。"""
        r0, g0, b0 = mean_channel_values(rgb_image)
        order_before = (r0 > g0, g0 > b0)
        out = HistogramEqualizationAdjustment({"factor": 1.8}).apply(
            rgb_image, {"factor": 1.8}
        )
        r1, g1, b1 = mean_channel_values(out)
        order_after = (r1 > g1, g1 > b1)
        assert order_after == order_before, "R>G>B 的相对次序应保持（无色偏）"

    @pytest.mark.parametrize("factor", [-0.1, 2.1])
    def test_out_of_range_raises(self, factor):
        with pytest.raises(AdjustmentError):
            HistogramEqualizationAdjustment({"factor": factor})

    def test_round_trip(self, rgb_image):
        adjustment = HistogramEqualizationAdjustment({"factor": 1.6})
        original = adjustment.apply(rgb_image, adjustment.params)
        rebuilt = HistogramEqualizationAdjustment.deserialize(adjustment.serialize())
        assert_pixel_equal(rebuilt.apply(rgb_image, rebuilt.params), original)
