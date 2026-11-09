"""极大分辨率边界测试：≈8000×6000 加载/三级预览/导出可完成，低分预览先行（Spec Edge Cases/FR-018）。

样图由 numpy 程序化生成（避免逐像素循环耗时），模块级夹具仅构造一次。
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pylightroom.core.assets.base import MEDIUM_SIZE, THUMB_SIZE
from pylightroom.core.assets.factory import AssetFactory
from pylightroom.core.pipeline import ImageProcessor

WIDTH, HEIGHT = 8000, 6000


class LargeImageEvents:
    """轻量事件记录器：仅捕获完成回调顺序与 thumb/full 就绪状态。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.task_order: list[str] = []
        self.thumb_done = threading.Event()
        self.full_done = threading.Event()

    def on_progress(self, task_id: str, stage: str, fraction: float) -> None:
        pass

    def on_render_complete(self, task_id: str, image_bytes: bytes) -> None:
        with self._lock:
            self.task_order.append(task_id)
        if task_id.startswith("preview-thumb"):
            self.thumb_done.set()
        elif task_id.startswith("preview-full"):
            self.full_done.set()

    def on_error(self, task_id: str, message: str) -> None:
        pass


@pytest.fixture(scope="module")
def large_jpeg(tmp_path_factory) -> Path:
    """程序化构造 8000×6000 渐变样图。"""
    xs = np.linspace(0, 255, WIDTH, dtype=np.uint8)
    ys = np.linspace(0, 255, HEIGHT, dtype=np.uint8)
    arr = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    arr[..., 0] = np.tile(xs, (HEIGHT, 1))
    arr[..., 1] = ys[:, None]
    arr[..., 2] = 128
    path = tmp_path_factory.mktemp("large") / "large.jpg"
    Image.fromarray(arr, "RGB").save(path, "JPEG", quality=85)
    return path


class TestLargeResolution:
    def test_load_and_three_level_previews(self, large_jpeg):
        """加载可完成；三级预览不放大且尺寸递增（FR-010/Edge Cases）。"""
        asset = AssetFactory.create(large_jpeg)
        image = asset.load()
        assert image.size == (WIDTH, HEIGHT)
        assert image.mode == "RGB"
        levels = asset.thumbnail()
        assert set(levels) == {"thumb", "medium", "full"}
        assert max(levels["thumb"].size) <= THUMB_SIZE
        assert max(levels["medium"].size) <= MEDIUM_SIZE
        assert levels["full"].size == (WIDTH, HEIGHT)
        assert max(levels["thumb"].size) < max(levels["medium"].size) < max(levels["full"].size)

    def test_low_res_preview_not_blocked_by_full(self, large_jpeg):
        """update_adjustment 返回时低分预览已就绪、全图尚未完成（FR-018/SC-005）。"""
        events = LargeImageEvents()
        processor = ImageProcessor(events=events)
        processor.open(large_jpeg)
        processor.update_adjustment("brightness", {"factor": 1.2})
        assert events.thumb_done.is_set(), "低分预览应同步先行完成"
        assert not events.full_done.is_set(), "全图渲染不得阻塞低分预览先行返回"
        # 高分级后台补齐：medium → full 顺序完成（宽裕超时，Q3 无硬性时间指标）
        assert events.full_done.wait(timeout=180), "全图后台渲染超时未完成"
        order = [task_id.rsplit("-v", 1)[0] for task_id in events.task_order]
        assert order == ["preview-thumb", "preview-medium", "preview-full"]

    def test_export_large_image(self, large_jpeg, tmp_path):
        """全图导出可完成，尺寸如实保留，Sidecar 写到原图关联路径（FR-019）。"""
        processor = ImageProcessor()
        processor.open(large_jpeg)
        processor.update_adjustment("brightness", {"factor": 1.2})
        target = tmp_path / "large_out.jpg"
        processor.export(target, "jpeg")
        assert target.is_file()
        with Image.open(target) as result:
            result.load()
            assert result.size == (WIDTH, HEIGHT)
        assert large_jpeg.with_suffix(".json").is_file(), "导出须持久化原图关联 Sidecar"
