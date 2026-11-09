"""US5 门面与预览管线测试：全流程、空栈=原图、缓存失效、低分先行（FR-016–FR-018, SC-005）。"""

from __future__ import annotations

import threading

import pytest

from pylightroom.core.errors import AdjustmentError, AssetError
from pylightroom.core.pipeline import ImageProcessor
from tests.conftest import assert_pixel_equal


class EventsRecorder:
    """线程安全的引擎事件记录器。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.progress: list[tuple[str, str, float]] = []
        self.completed: list[tuple[str, bytes]] = []
        self.errors: list[tuple[str, str]] = []

    def on_progress(self, task_id: str, stage: str, fraction: float) -> None:
        with self._lock:
            self.progress.append((task_id, stage, fraction))

    def on_render_complete(self, task_id: str, image_bytes: bytes) -> None:
        with self._lock:
            self.completed.append((task_id, image_bytes))

    def on_error(self, task_id: str, message: str) -> None:
        with self._lock:
            self.errors.append((task_id, message))


@pytest.fixture
def processor(jpeg_sample) -> ImageProcessor:
    processor = ImageProcessor()
    processor.open(jpeg_sample)
    return processor


@pytest.fixture
def recorder() -> EventsRecorder:
    return EventsRecorder()


def wait_background(processor: ImageProcessor, timeout: float = 5.0) -> None:
    thread = getattr(processor, "_bg_thread", None)
    if thread is not None:
        thread.join(timeout=timeout)


class TestOpenAndRender:
    def test_open_sample(self, processor):
        assert processor.version == 0

    def test_open_unsupported_format_raises(self, tmp_path):
        bogus = tmp_path / "x.tiff"
        bogus.write_bytes(b"II*")
        processor = ImageProcessor()
        with pytest.raises(AssetError):
            processor.open(bogus)

    def test_render_empty_stack_equals_original(self, processor, jpeg_sample):
        """空指令栈渲染结果必须与原图一致（FR-016）。"""
        from pylightroom.core.assets.factory import AssetFactory

        original = AssetFactory.create(jpeg_sample).load()
        assert_pixel_equal(processor.render("full"), original)

    @pytest.mark.parametrize("level", ["thumb", "medium", "full"])
    def test_render_levels(self, processor, level):
        image = processor.render(level)
        assert image.mode == "RGB"


class TestUpdateAdjustment:
    def test_unknown_name_raises(self, processor):
        with pytest.raises(AdjustmentError):
            processor.update_adjustment("vignette", {"factor": 1.2})

    def test_out_of_range_raises(self, processor):
        with pytest.raises(AdjustmentError):
            processor.update_adjustment("brightness", {"factor": 2.5})

    def test_update_then_render_matches_manual(self, processor, jpeg_sample):
        from pylightroom.core.adjustments.basic import BrightnessAdjustment
        from pylightroom.core.assets.factory import AssetFactory

        processor.update_adjustment("brightness", {"factor": 1.3})
        base = AssetFactory.create(jpeg_sample).load()
        expected = BrightnessAdjustment({"factor": 1.3}).apply(base, {"factor": 1.3})
        assert_pixel_equal(processor.render("full"), expected)


class TestUndoRedoViaFacade:
    def test_undo_restores_original(self, processor, jpeg_sample):
        from pylightroom.core.assets.factory import AssetFactory

        processor.update_adjustment("brightness", {"factor": 1.3})
        processor.undo()
        original = AssetFactory.create(jpeg_sample).load()
        assert_pixel_equal(processor.render("full"), original)

    def test_undo_empty_raises(self, processor):
        with pytest.raises(Exception):  # HistoryError
            processor.undo()

    def test_redo_restores_after_undo(self, processor, jpeg_sample):
        from pylightroom.core.adjustments.basic import BrightnessAdjustment
        from pylightroom.core.assets.factory import AssetFactory

        processor.update_adjustment("brightness", {"factor": 1.3})
        processor.undo()
        processor.redo()
        base = AssetFactory.create(jpeg_sample).load()
        expected = BrightnessAdjustment({"factor": 1.3}).apply(base, {"factor": 1.3})
        assert_pixel_equal(processor.render("full"), expected)

    def test_facade_does_not_expose_stack(self, processor):
        """门面约束：不暴露内部栈结构（core-api §1/§8）。"""
        public = {name for name in vars(processor) if not name.startswith("_")}
        assert not any("stack" in name or "instruction" in name for name in public)
        assert not hasattr(processor, "instructions")


class TestPreviewCacheInvalidation:
    def test_same_version_hits_cache(self, processor):
        first = processor.render("medium")
        second = processor.render("medium")
        assert first is second, "同版本同级别须命中缓存（FR-017）"

    def test_version_change_invalidates(self, processor):
        old = processor.render("medium")
        processor.update_adjustment("brightness", {"factor": 1.3})
        new = processor.render("medium")
        assert new is not old, "版本不匹配必须失效重渲染（FR-017）"


class TestProgressiveOrdering:
    def test_low_res_callback_before_full(self, jpeg_sample, recorder):
        """低分预览回调先于全图回调到达（SC-005 顺序性，Q3 无硬性时间指标）。"""
        processor = ImageProcessor(events=recorder)
        processor.open(jpeg_sample)
        processor.update_adjustment("brightness", {"factor": 1.3})
        wait_background(processor)
        completed_ids = [task_id for task_id, _bytes in recorder.completed]
        assert len(completed_ids) == 3, "thumb/medium/full 各一次回调"
        assert completed_ids[0].startswith("preview-thumb"), "低分先行（同步产出）"
        assert completed_ids[-1].startswith("preview-full"), "全图随后替换"

    def test_progress_events_ordered(self, jpeg_sample, recorder):
        processor = ImageProcessor(events=recorder)
        processor.open(jpeg_sample)
        processor.update_adjustment("contrast", {"factor": 1.2})
        wait_background(processor)
        fractions = [fraction for _task_id, _stage, fraction in recorder.progress]
        assert fractions == sorted(fractions), "进度按序送达（事件场景 2）"

    def test_no_events_injected_is_silent(self, jpeg_sample):
        """回调未注入时静默不报错（FR-024）。"""
        processor = ImageProcessor(events=None)
        processor.open(jpeg_sample)
        processor.update_adjustment("brightness", {"factor": 1.4})
        wait_background(processor)  # 不应抛任何异常

    def test_merge_via_facade(self, jpeg_sample):
        processor = ImageProcessor()
        processor.open(jpeg_sample)
        processor.update_adjustment("brightness", {"factor": 1.2})
        processor.update_adjustment("brightness", {"factor": 1.5})
        session = processor._session
        assert len(session.instructions) == 1, "同类调整经门面同样合并"
        assert session.instructions[0].params["factor"] == 1.5
