"""US1 调整工厂测试：按名创建、未注册名报错、param_schema 暴露（FR-006）。"""

from __future__ import annotations

import pytest

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
from pylightroom.core.errors import AdjustmentError

ALL_NAMES = {
    "brightness": BrightnessAdjustment,
    "contrast": ContrastAdjustment,
    "saturation": SaturationAdjustment,
    "sharpness": SharpnessAdjustment,
    "temperature": TemperatureAdjustment,
    "histogram_equalization": HistogramEqualizationAdjustment,
    "crop": CropAdjustment,
    "rotate": RotateAdjustment,
}

SAMPLE_PARAMS = {
    "brightness": {"factor": 1.3},
    "contrast": {"factor": 0.9},
    "saturation": {"factor": 1.2},
    "sharpness": {"factor": 1.1},
    "temperature": {"factor": 1.4},
    "histogram_equalization": {"factor": 1.5},
    "crop": {"box": (0, 0, 8, 8)},
    "rotate": {"angle": 45},
}


class TestCreateByRegisteredName:
    @pytest.mark.parametrize("name", list(ALL_NAMES))
    def test_create_returns_correct_subclass(self, name):
        instance = AdjustmentFactory.create(name, SAMPLE_PARAMS[name])
        assert isinstance(instance, ALL_NAMES[name])
        assert isinstance(instance, BaseAdjustment)

    def test_created_instance_usable(self, rgb_image):
        adjustment = AdjustmentFactory.create("brightness", {"factor": 1.3})
        out = adjustment.apply(rgb_image, adjustment.params)
        assert out.size == rgb_image.size


class TestUnknownName:
    def test_unknown_type_raises_with_reason(self):
        with pytest.raises(AdjustmentError, match="vignette"):
            AdjustmentFactory.create("vignette", {})

    def test_error_is_unknown_type_variant(self):
        try:
            AdjustmentFactory.create("nonexistent", {})
        except AdjustmentError as exc:
            assert "unknown" in str(exc).lower() or "未知" in str(exc)
        else:
            pytest.fail("未注册名必须抛 AdjustmentError")


class TestParamSchemaExposure:
    def test_all_eight_registered(self):
        for name in ALL_NAMES:
            assert name in AdjustmentFactory.registered_names(), (
                f"{name} 应已注册"
            )

    def test_factor_schema_contract(self):
        schema = BrightnessAdjustment.param_schema["factor"]
        assert schema["min"] == 0.0
        assert schema["max"] == 2.0
        assert schema["default"] == 1.0

    @pytest.mark.parametrize(
        "name", ["brightness", "contrast", "saturation", "sharpness", "temperature", "histogram_equalization"]
    )
    def test_color_like_schemas_use_0_2_scale(self, name):
        rule = ALL_NAMES[name].param_schema["factor"]
        assert (rule["min"], rule["max"], rule["default"]) == (0.0, 2.0, 1.0)

    def test_geometry_schemas_use_natural_units(self):
        assert "box" in CropAdjustment.param_schema
        assert "angle" in RotateAdjustment.param_schema
