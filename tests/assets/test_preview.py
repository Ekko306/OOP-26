"""US3 多级预览测试：thumb/medium/full 三级分辨率（FR-010，research D5）。"""

from __future__ import annotations

import pytest

from pylightroom.core.assets.factory import AssetFactory


@pytest.fixture
def large_jpeg(tmp_path, gradient_image):
    """大于 1024px 的样图，保证三级尺寸差异可见。"""
    img = gradient_image.resize((2048, 1024))
    p = tmp_path / "large.jpg"
    img.save(p, "JPEG", quality=90)
    return p


class TestThreeLevelPreview:
    def test_returns_three_levels(self, jpeg_sample):
        asset = AssetFactory.create(jpeg_sample)
        previews = asset.thumbnail()
        assert set(previews) == {"thumb", "medium", "full"}

    def test_sizes_increase_by_level(self, large_jpeg):
        previews = AssetFactory.create(large_jpeg).thumbnail()
        thumb, medium, full = previews["thumb"], previews["medium"], previews["full"]
        assert max(thumb.size) <= 256, "缩略级 ≤256px（D5）"
        assert max(medium.size) <= 1024, "中等级 ≤1024px（D5）"
        assert full.size == (2048, 1024), "全图级为原尺寸"
        assert thumb.size[0] < medium.size[0] < full.size[0], "尺寸逐级递增"

    def test_small_image_full_equals_original(self, jpeg_sample):
        asset = AssetFactory.create(jpeg_sample)
        original = asset.load()
        previews = asset.thumbnail()
        assert previews["full"] is original, "全图级直接复用解码缓存"
        assert previews["thumb"].size == (64, 48), "小图不放大"
