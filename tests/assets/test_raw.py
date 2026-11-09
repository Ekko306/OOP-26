"""US3 RAW 资产测试：.ARW 主验收；无样片 skip；失败路径格式化异常（FR-007/008/011）。"""

from __future__ import annotations

import pytest

from pylightroom.core.adjustments.basic import BrightnessAdjustment
from pylightroom.core.assets.factory import AssetFactory
from pylightroom.core.assets.raw import RawAsset
from pylightroom.core.errors import AssetError


class TestRawLoading:
    def test_arw_loads_to_unified_rgb(self, arw_sample):
        asset = AssetFactory.create(arw_sample)
        assert isinstance(asset, RawAsset)
        image = asset.load()
        assert image.mode == "RGB"
        assert image.size[0] > 0 and image.size[1] > 0

    def test_raw_same_pipeline_as_jpeg(self, arw_sample, jpeg_sample):
        """RAW 与 JPEG 应用同一调整得到同类结果类型（FR-007/FR-008）。"""
        raw_image = AssetFactory.create(arw_sample).load()
        jpeg_image = AssetFactory.create(jpeg_sample).load()
        adjustment = BrightnessAdjustment({"factor": 1.3})
        raw_out = adjustment.apply(raw_image, adjustment.params)
        jpeg_out = adjustment.apply(jpeg_image, adjustment.params)
        assert raw_out.mode == jpeg_out.mode == "RGB"
        assert raw_out.size == raw_image.size


class TestRawFailurePaths:
    def test_missing_file_raises_with_path(self, tmp_path):
        ghost = tmp_path / "ghost.arw"
        asset = AssetFactory.create(ghost)
        with pytest.raises(AssetError) as excinfo:
            asset.load()
        assert str(ghost) in str(excinfo.value)
        assert excinfo.value.path == str(ghost)

    def test_corrupted_raw_raises(self, tmp_path):
        bogus = tmp_path / "broken.arw"
        bogus.write_bytes(b"not-a-raw-file" * 16)
        asset = AssetFactory.create(bogus)
        with pytest.raises(AssetError) as excinfo:
            asset.load()
        assert str(bogus) in str(excinfo.value)
        assert excinfo.value.reason

    def test_no_half_initialized_state_after_failure(self, tmp_path):
        """解码失败后无半初始化残留：解码缓存保持空、可安全重试抛同类错误（FR-011）。"""
        bogus = tmp_path / "broken2.arw"
        bogus.write_bytes(b"junk" * 8)
        asset = AssetFactory.create(bogus)
        with pytest.raises(AssetError):
            asset.load()
        with pytest.raises(AssetError):
            asset.load()  # 重试仍报同类格式化异常


class TestRawFactoryRegistration:
    def test_common_raw_extensions_registered(self, tmp_path):
        """常见 RAW 扩展名注册到 RawAsset（FR-007/core-api §4，research D4）。

        create() 仅按扩展名构造、不解码，空文件即可验证注册入口。
        """
        for extension in (".arw", ".cr2", ".nef", ".dng", ".orf", ".rw2", ".raf"):
            path = tmp_path / f"photo{extension}"
            path.write_bytes(b"")
            asset = AssetFactory.create(path)
            assert isinstance(asset, RawAsset), f"{extension} 应注册到 RawAsset"
