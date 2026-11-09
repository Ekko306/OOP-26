"""US1 基础调整策略测试：亮度/对比度/饱和度/锐度（FR-002/003/004，SC-002）。"""

from __future__ import annotations

import pytest
from PIL import Image, ImageFilter

from pylightroom.core.adjustments.basic import (
    BrightnessAdjustment,
    ContrastAdjustment,
    SaturationAdjustment,
    SharpnessAdjustment,
)
from pylightroom.core.errors import AdjustmentError
from tests.conftest import assert_pixel_equal, mean_channel_values


class TestNeutralIdentity:
    @pytest.mark.parametrize(
        "cls", [BrightnessAdjustment, ContrastAdjustment, SaturationAdjustment, SharpnessAdjustment]
    )
    def test_factor_1_output_identical_to_original(self, rgb_image, cls):
        adjusted = cls({"factor": 1.0}).apply(rgb_image, {"factor": 1.0})
        assert_pixel_equal(adjusted, rgb_image, f"{cls.name} factor=1.0 应输出与原图一致")

    @pytest.mark.parametrize(
        "cls", [BrightnessAdjustment, ContrastAdjustment, SaturationAdjustment, SharpnessAdjustment]
    )
    def test_apply_does_not_mutate_input(self, rgb_image, cls):
        snapshot = rgb_image.copy()
        cls({"factor": 1.6}).apply(rgb_image, {"factor": 1.6})
        assert_pixel_equal(rgb_image, snapshot, f"{cls.name} 禁止原地修改输入（FR-012）")


class TestDirectionality:
    def test_brightness_increase_means_brighter(self, rgb_image):
        before = sum(mean_channel_values(rgb_image))
        after = sum(
            mean_channel_values(
                BrightnessAdjustment({"factor": 1.5}).apply(rgb_image, {"factor": 1.5})
            )
        )
        assert after > before

    def test_brightness_decrease_means_darker(self, rgb_image):
        before = sum(mean_channel_values(rgb_image))
        after = sum(
            mean_channel_values(
                BrightnessAdjustment({"factor": 0.5}).apply(rgb_image, {"factor": 0.5})
            )
        )
        assert after < before

    @staticmethod
    def _std(image: Image.Image) -> float:
        gray = image.convert("L")
        hist = gray.histogram()
        n = sum(hist)
        mean = sum(v * c for v, c in enumerate(hist)) / n
        var = sum(((v - mean) ** 2) * c for v, c in enumerate(hist)) / n
        return var**0.5

    def test_contrast_increase_expands_range(self, gradient_image):
        before = self._std(gradient_image)
        after = self._std(
            ContrastAdjustment({"factor": 1.5}).apply(gradient_image, {"factor": 1.5})
        )
        assert after > before

    def test_saturation_increase_amplifies_channel_gap(self, rgb_image):
        r, g, b = mean_channel_values(rgb_image)
        spread_before = max(r, g, b) - min(r, g, b)
        out = SaturationAdjustment({"factor": 1.6}).apply(rgb_image, {"factor": 1.6})
        r2, g2, b2 = mean_channel_values(out)
        spread_after = max(r2, g2, b2) - min(r2, g2, b2)
        assert spread_after > spread_before

    def test_sharpness_enhances_edges(self, rgb_image):
        blurred = rgb_image.filter(ImageFilter.GaussianBlur(3))
        before = self._std(blurred)
        after = self._std(
            SharpnessAdjustment({"factor": 2.0}).apply(blurred, {"factor": 2.0})
        )
        assert after > before


class TestParamValidation:
    @pytest.mark.parametrize("factor", [-0.1, 2.1, "x", None])
    def test_out_of_range_factor_raises(self, factor):
        with pytest.raises(AdjustmentError):
            BrightnessAdjustment({"factor": factor})

    @pytest.mark.parametrize(
        "cls", [BrightnessAdjustment, ContrastAdjustment, SaturationAdjustment, SharpnessAdjustment]
    )
    def test_boundary_values_execute(self, rgb_image, cls):
        for factor in (0.0, 2.0):
            out = cls({"factor": factor}).apply(rgb_image, {"factor": factor})
            assert out.size == rgb_image.size

    def test_default_params_mean_neutral(self, rgb_image):
        adjustment = BrightnessAdjustment({})
        assert adjustment.params["factor"] == 1.0
        assert_pixel_equal(
            adjustment.apply(rgb_image, adjustment.params), rgb_image
        )

    def test_unknown_param_rejected(self):
        with pytest.raises(AdjustmentError):
            BrightnessAdjustment({"factor": 1.2, "exposure": 1.0})


class TestRoundTrip:
    @pytest.mark.parametrize(
        "cls,factor",
        [
            (BrightnessAdjustment, 1.3),
            (ContrastAdjustment, 0.9),
            (SaturationAdjustment, 1.4),
            (SharpnessAdjustment, 1.7),
        ],
    )
    def test_serialize_deserialize_apply_pixel_identical(self, rgb_image, cls, factor):
        original = cls({"factor": factor}).apply(rgb_image, {"factor": factor})
        data = cls({"factor": factor}).serialize()
        assert data == {"type": cls.name, "params": {"factor": factor}}
        rebuilt = cls.deserialize(data)
        assert isinstance(rebuilt, cls)
        rerendered = rebuilt.apply(rgb_image, rebuilt.params)
        assert_pixel_equal(rerendered, original, f"{cls.name} 序列化往返必须无损（SC-002）")


class TestMerge:
    def test_same_class_merge_last_value_wins(self):
        first = BrightnessAdjustment({"factor": 1.2})
        second = BrightnessAdjustment({"factor": 1.5})
        assert first.merge(second) is True
        assert first.params["factor"] == 1.5

    def test_merge_semantics_equivalent_to_single_apply(self, rgb_image):
        single = BrightnessAdjustment({"factor": 1.5}).apply(rgb_image, {"factor": 1.5})
        # 会话语义：栈顶 [B1.2] 合并后一条 B1.5 → 栈变为 [B1.5]，渲染须等价于仅应用 B1.5
        merger = BrightnessAdjustment({"factor": 1.2})
        merger.merge(BrightnessAdjustment({"factor": 1.5}))
        merged = merger.apply(rgb_image, merger.params)
        assert_pixel_equal(merged, single, "合并结果须等价于后一条单独应用（FR-004）")

    def test_different_class_not_merged(self):
        assert BrightnessAdjustment({"factor": 1.2}).merge(
            ContrastAdjustment({"factor": 1.5})
        ) is False
