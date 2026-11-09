"""US1 几何类调整测试：裁剪与旋转（自然单位参数）。"""

from __future__ import annotations

import pytest
from PIL import Image

from pylightroom.core.adjustments.geometry import CropAdjustment, RotateAdjustment
from pylightroom.core.errors import AdjustmentError
from tests.conftest import assert_pixel_equal


class TestCrop:
    def test_valid_crop_size_and_pixels(self, rgb_image):
        box = (4, 6, 36, 30)
        out = CropAdjustment({"box": box}).apply(rgb_image, {"box": box})
        assert out.size == (32, 24)
        assert_pixel_equal(out, rgb_image.crop(box), "裁剪结果须与手工 crop 一致")

    def test_out_of_bounds_raises(self, rgb_image):
        adjustment = CropAdjustment({"box": (0, 0, 100, 100)})
        with pytest.raises(AdjustmentError):
            adjustment.apply(rgb_image, adjustment.params)

    def test_zero_width_raises(self):
        with pytest.raises(AdjustmentError):
            CropAdjustment({"box": (10, 10, 10, 20)})

    def test_zero_height_raises(self):
        with pytest.raises(AdjustmentError):
            CropAdjustment({"box": (10, 10, 20, 10)})

    def test_inverted_box_raises(self):
        with pytest.raises(AdjustmentError):
            CropAdjustment({"box": (20, 20, 10, 10)})

    def test_box_wrong_shape_raises(self):
        with pytest.raises(AdjustmentError):
            CropAdjustment({"box": (1, 2, 3)})

    def test_box_non_numeric_raises(self):
        with pytest.raises(AdjustmentError):
            CropAdjustment({"box": ("a", 0, 10, 10)})

    def test_boundary_box_executes(self, rgb_image):
        """边界值：整幅图像框应正常执行（Edge Cases）。"""
        box = (0, 0, rgb_image.size[0], rgb_image.size[1])
        out = CropAdjustment({"box": box}).apply(rgb_image, {"box": box})
        assert out.size == rgb_image.size

    def test_round_trip(self, rgb_image):
        adjustment = CropAdjustment({"box": (2, 2, 20, 18)})
        original = adjustment.apply(rgb_image, adjustment.params)
        rebuilt = CropAdjustment.deserialize(adjustment.serialize())
        assert rebuilt.params["box"] == (2, 2, 20, 18)
        assert_pixel_equal(rebuilt.apply(rgb_image, rebuilt.params), original)


class TestRotate:
    def test_rotate_90_clockwise_size_swapped(self, rgb_image):
        out = RotateAdjustment({"angle": 90}).apply(rgb_image, {"angle": 90})
        assert out.size == (rgb_image.size[1], rgb_image.size[0])

    def test_rotate_90_matches_pil_clockwise(self, rgb_image):
        out = RotateAdjustment({"angle": 90}).apply(rgb_image, {"angle": 90})
        expected = rgb_image.transpose(Image.Transpose.ROTATE_270)  # PIL 顺时针 90°
        assert_pixel_equal(out, expected, "正值角度应顺时针旋转")

    def test_rotate_45_canvas_expands(self, rgb_image):
        out = RotateAdjustment({"angle": 45}).apply(rgb_image, {"angle": 45})
        w, h = rgb_image.size
        assert out.size[0] > w - 2 and out.size[1] > h - 2, "45° 旋转画布应扩大"

    def test_rotate_360_size_preserved(self, rgb_image):
        out = RotateAdjustment({"angle": 360}).apply(rgb_image, {"angle": 360})
        assert out.size == rgb_image.size

    def test_rotate_negative_is_counterclockwise(self, rgb_image):
        cw90 = RotateAdjustment({"angle": 90}).apply(rgb_image, {"angle": 90})
        ccw270 = RotateAdjustment({"angle": -270}).apply(rgb_image, {"angle": -270})
        assert cw90.size == ccw270.size

    def test_any_real_angle_allowed(self):
        adjustment = RotateAdjustment({"angle": -123.5})
        assert adjustment.params["angle"] == -123.5

    def test_angle_non_numeric_raises(self):
        with pytest.raises(AdjustmentError):
            RotateAdjustment({"angle": "90"})

    def test_round_trip(self, rgb_image):
        adjustment = RotateAdjustment({"angle": 30})
        original = adjustment.apply(rgb_image, adjustment.params)
        rebuilt = RotateAdjustment.deserialize(adjustment.serialize())
        assert_pixel_equal(rebuilt.apply(rgb_image, rebuilt.params), original)
