"""US3 栅格资产测试：JPEG/PNG/BMP/WebP 统一加载（FR-007/008/011）。"""

from __future__ import annotations

import pytest

from pylightroom.core.assets.factory import AssetFactory
from pylightroom.core.assets.raster import (
    BmpAsset,
    JpegAsset,
    PngAsset,
    WebPAsset,
)
from pylightroom.core.errors import AssetError


@pytest.mark.parametrize(
    "fixture_name,asset_cls,fmt",
    [
        ("jpeg_sample", JpegAsset, "JPEG"),
        ("png_sample", PngAsset, "PNG"),
        ("bmp_sample", BmpAsset, "BMP"),
        ("webp_sample", WebPAsset, "WEBP"),
    ],
)
class TestUnifiedLoading:
    def test_load_returns_rgb(self, fixture_name, asset_cls, fmt, request):
        path = request.getfixturevalue(fixture_name)
        asset = AssetFactory.create(path)
        assert isinstance(asset, asset_cls)
        image = asset.load()
        assert image.mode == "RGB", "统一内存表示（FR-008）"
        assert image.size == (64, 48)

    def test_metadata_present(self, fixture_name, asset_cls, fmt, request):
        path = request.getfixturevalue(fixture_name)
        asset = AssetFactory.create(path)
        asset.load()
        assert asset.format == fmt
        assert asset.path == path
        assert "size" in asset.exif and asset.exif["size"] == (64, 48)

    def test_load_is_cached(self, fixture_name, asset_cls, fmt, request):
        path = request.getfixturevalue(fixture_name)
        asset = AssetFactory.create(path)
        first = asset.load()
        second = asset.load()
        assert first is second, "load 结果须缓存"


class TestPngTransparency:
    def test_transparent_composited_on_white(self, png_transparent_sample):
        asset = AssetFactory.create(png_transparent_sample)
        image = asset.load()
        assert image.mode == "RGB", "PNG 透明通道须合成白底（core-api §4）"
        px = image.load()
        assert px[8, 8] == (255, 0, 0), "不透明区域保持原色"
        assert px[24, 8] == (255, 255, 255), "透明区域合成白底"


class TestFactoryErrors:
    def test_unsupported_extension_raises(self, tmp_path):
        bogus = tmp_path / "photo.tiff"
        bogus.write_bytes(b"II*\x00")
        with pytest.raises(AssetError, match="unsupported"):
            AssetFactory.create(bogus)

    def test_unsupported_extension_no_extension(self, tmp_path):
        plain = tmp_path / "noext"
        plain.write_bytes(b"data")
        with pytest.raises(AssetError):
            AssetFactory.create(plain)

    def test_corrupted_file_raises_with_path_and_reason(self, corrupted_file):
        asset = AssetFactory.create(corrupted_file)
        with pytest.raises(AssetError) as excinfo:
            asset.load()
        assert str(corrupted_file) in str(excinfo.value), "异常须含路径"
        assert excinfo.value.path == str(corrupted_file)
        assert excinfo.value.reason, "异常须含原因"
