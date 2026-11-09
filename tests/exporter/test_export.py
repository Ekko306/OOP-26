"""US5 导出测试：像素一致、原图关联 Sidecar、失败无半成品（FR-019/FR-020/FR-021, SC-004）。"""

from __future__ import annotations

import json

import pytest

from pylightroom.core.adjustments.basic import BrightnessAdjustment, ContrastAdjustment
from pylightroom.core.assets.factory import AssetFactory
from pylightroom.core.errors import ExportError
from pylightroom.core.exporter import Exporter
from pylightroom.core.pipeline import ImageProcessor
from tests.conftest import assert_pixel_equal


@pytest.fixture
def processor(jpeg_sample) -> ImageProcessor:
    processor = ImageProcessor()
    processor.open(jpeg_sample)
    return processor


class TestExportPixels:
    def test_png_export_matches_manual_chain(self, processor, jpeg_sample, tmp_path):
        """成品像素 = 逐条手工应用结果（SC-004，FR-019）。"""
        processor.update_adjustment("brightness", {"factor": 1.3})
        processor.update_adjustment("contrast", {"factor": 0.9})
        out = tmp_path / "out.png"
        Exporter.export(processor, out, "png")
        base = AssetFactory.create(jpeg_sample).load()
        step1 = BrightnessAdjustment({"factor": 1.3}).apply(base, {"factor": 1.3})
        expected = ContrastAdjustment({"factor": 0.9}).apply(step1, {"factor": 0.9})
        assert_pixel_equal(AssetFactory.create(out).load(), expected)

    def test_jpeg_export(self, processor, tmp_path):
        out = tmp_path / "out.jpg"
        processor.update_adjustment("saturation", {"factor": 1.2})
        Exporter.export(processor, out, "jpeg")
        assert out.is_file()
        assert AssetFactory.create(out).load().mode == "RGB"

    def test_uppercase_format_accepted(self, processor, tmp_path):
        out = tmp_path / "out.png"
        Exporter.export(processor, out, "PNG")
        assert out.is_file()

    def test_unknown_format_raises(self, processor, tmp_path):
        with pytest.raises(ExportError):
            Exporter.export(processor, tmp_path / "out.gif", "gif")


class TestSidecarOnExport:
    def test_sidecar_written_beside_original_not_product(
        self, processor, jpeg_sample, tmp_path
    ):
        """原图关联 Sidecar 写出（sample.jpg → sample.json），成品名 Sidecar 不存在（FR-019/FR-021）。"""
        processor.update_adjustment("brightness", {"factor": 1.3})
        out = tmp_path / "out.png"
        Exporter.export(processor, out, "png")
        sidecar = jpeg_sample.with_suffix(".json")
        assert sidecar.is_file(), "原图关联 Sidecar 必须写出"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert data["image_path"] == str(jpeg_sample)
        assert data["instructions"][0]["type"] == "brightness"
        assert not out.with_suffix(".json").exists(), "成品自身不生成 Sidecar"

    def test_original_file_untouched(self, processor, jpeg_sample, tmp_path):
        before = jpeg_sample.read_bytes()
        Exporter.export(processor, tmp_path / "out.png", "png")
        assert jpeg_sample.read_bytes() == before, "原图永不写入（FR-012/FR-021）"


class TestExportFailure:
    def test_unwritable_target_no_half_product(self, processor, monkeypatch, tmp_path):
        """异常注入：写出失败 → ExportError 且无半成品、无临时文件残留（FR-020）。"""
        processor.update_adjustment("brightness", {"factor": 1.3})
        out = tmp_path / "out.png"
        out.write_bytes(b"keep-me")  # 预置旧成品

        import pylightroom.core.exporter as exporter_module

        def boom(*_args, **_kwargs):
            raise OSError("injected write failure")

        monkeypatch.setattr(exporter_module.os, "replace", boom)
        with pytest.raises(ExportError) as excinfo:
            Exporter.export(processor, out, "png")
        assert str(out) in str(excinfo.value) or excinfo.value.path
        assert out.read_bytes() == b"keep-me", "旧成品不被破坏"
        leftovers = [p.name for p in tmp_path.iterdir() if ".tmp" in p.name]
        assert leftovers == [], "无临时文件残留"

    def test_nonexistent_target_dir_raises_clean(self, processor, tmp_path):
        out = tmp_path / "no_such_dir" / "out.png"
        with pytest.raises(ExportError):
            Exporter.export(processor, out, "png")
        assert not out.parent.exists() or not any(out.parent.iterdir())
