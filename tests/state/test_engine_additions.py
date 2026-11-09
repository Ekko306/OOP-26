"""T003：引擎增量测试（先失败后实现）。

覆盖：
- ImageProcessor.current_params()：只读查询，自栈顶向下首次命中生效（research D1）
- AdjustmentFactory.registered_schemas()：参数模式深拷贝（research D1）
- 红线自检语义修正（research D2）：仅「core 导入链新引入 reflex」才抛 EngineError
"""

from __future__ import annotations

import importlib
import io
import sys
import time
import types

import pytest
from PIL import Image

from pylightroom.core import AdjustmentFactory, ImageProcessor
from pylightroom.core.errors import AssetError, EngineError


# ---------------------------------------------------------------------------
# current_params（D1：撤销后滑块同步所需的只读增量）
# ---------------------------------------------------------------------------


@pytest.fixture
def processor(png_sample) -> ImageProcessor:
    processor = ImageProcessor()
    processor.open(png_sample)
    return processor


class TestCurrentParams:
    def test_not_opened_returns_empty(self):
        assert ImageProcessor().current_params() == {}

    def test_single_instruction_params(self, processor):
        processor.update_adjustment("brightness", {"factor": 1.3})
        assert processor.current_params() == {"brightness": {"factor": 1.3}}

    def test_same_segment_merge_takes_merged_value(self, processor):
        """同段同类合并（FR-015）：栈顶合并后的参数即当前生效值。"""
        processor.update_adjustment("brightness", {"factor": 1.2})
        processor.update_adjustment("brightness", {"factor": 1.5})
        assert processor.current_params() == {"brightness": {"factor": 1.5}}
        assert processor.version == 2  # 合并同样推进版本

    def test_multiple_segments_same_name_takes_top(self, processor):
        """多段同名：自栈顶向下首次命中者生效（D1）。"""
        processor.update_adjustment("brightness", {"factor": 0.5})
        processor.update_adjustment("contrast", {"factor": 1.4})
        processor.update_adjustment("brightness", {"factor": 1.8})
        assert processor.current_params() == {
            "contrast": {"factor": 1.4},
            "brightness": {"factor": 1.8},
        }

    def test_undo_removes_and_redo_restores(self, processor):
        processor.update_adjustment("contrast", {"factor": 1.6})
        assert "contrast" in processor.current_params()
        processor.undo()
        assert processor.current_params() == {}
        processor.redo()
        assert processor.current_params() == {"contrast": {"factor": 1.6}}

    def test_returns_copy_not_live_reference(self, processor):
        """返回副本：外部修改不得影响指令栈参数。"""
        processor.update_adjustment("brightness", {"factor": 1.1})
        params = processor.current_params()
        params["brightness"]["factor"] = 9.9
        assert processor.current_params() == {"brightness": {"factor": 1.1}}


# ---------------------------------------------------------------------------
# registered_schemas（D1：滑块刻度唯一来源）
# ---------------------------------------------------------------------------


class TestRegisteredSchemas:
    def test_contains_all_registered_names(self):
        schemas = AdjustmentFactory.registered_schemas()
        assert set(schemas) == set(AdjustmentFactory.registered_names())

    def test_factor_schema_shape(self):
        rule = AdjustmentFactory.registered_schemas()["brightness"]["factor"]
        assert rule == {"min": 0.0, "max": 2.0, "default": 1.0}

    def test_geometric_schema_has_default(self):
        """几何参数为自然单位（可无 min/max），但必含 default（base.py 契约）。"""
        schemas = AdjustmentFactory.registered_schemas()
        assert "default" in schemas["crop"]["box"]
        assert "default" in schemas["rotate"]["angle"]

    def test_returns_deep_copy(self):
        first = AdjustmentFactory.registered_schemas()
        first["brightness"]["factor"]["default"] = 999.0
        first["brightness"]["factor"]["min"] = -1.0
        second = AdjustmentFactory.registered_schemas()
        assert second["brightness"]["factor"]["default"] == 1.0
        assert second["brightness"]["factor"]["min"] == 0.0


# ---------------------------------------------------------------------------
# refresh_previews（引擎增量三：US1 打开后渐进推送所需，research D8）
# ---------------------------------------------------------------------------


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _Collector:
    """收集全部引擎回调的测试替身。"""

    def __init__(self) -> None:
        self.progress: list[str] = []
        self.completed: dict[str, bytes] = {}
        self.errors: list[str] = []

    def on_progress(self, task_id: str, stage: str, fraction: float) -> None:
        self.progress.append(task_id)

    def on_render_complete(self, task_id: str, image_bytes: bytes) -> None:
        self.completed[task_id] = image_bytes

    def on_error(self, task_id: str, message: str) -> None:
        self.errors.append(message)


class TestRefreshPreviews:
    def test_requires_open(self):
        with pytest.raises(AssetError):
            ImageProcessor().refresh_previews()

    def test_pushes_three_levels_for_current_version(self, png_sample):
        collector = _Collector()
        processor = ImageProcessor(events=collector)
        processor.open(png_sample)
        processor.refresh_previews()
        # thumb 同步先行：调用返回时已完成（progress 首事件 + complete 在场）
        assert collector.progress[0] == "preview-thumb-v0"
        assert collector.completed["preview-thumb-v0"] == _png_bytes(
            processor.render("thumb")
        )
        # medium/full 由后台线程补齐
        for _ in range(100):
            if len(collector.completed) >= 3:
                break
            time.sleep(0.05)
        assert set(collector.completed) == {
            "preview-thumb-v0",
            "preview-medium-v0",
            "preview-full-v0",
        }
        assert collector.errors == []


# ---------------------------------------------------------------------------
# 红线自检语义（D2）：core 导入链增量检测
# ---------------------------------------------------------------------------


def _purge_pylightroom_modules() -> dict:
    """弹出全部 pylightroom 模块强制全新导入；返回备份供恢复。"""
    saved = {
        key: value
        for key, value in sys.modules.items()
        if key == "pylightroom" or key.startswith("pylightroom.")
    }
    for key in saved:
        del sys.modules[key]
    return saved


class TestRedLineCheckSemantics:
    def test_preexisting_reflex_module_allows_core_import(self, monkeypatch):
        """进程先有 reflex（桥接层先 import Reflex 再 import core）→ 正常不炸。"""
        monkeypatch.setitem(sys.modules, "reflex", types.ModuleType("reflex"))
        saved = _purge_pylightroom_modules()
        try:
            fresh = importlib.import_module("pylightroom.core")
            assert fresh.ImageProcessor is not None  # 惰性导出差集检测同样放行
        finally:
            sys.modules.update(saved)

    def test_lazy_chain_newly_introduced_reflex_raises(self, monkeypatch):
        """core 导入链「新」引入 reflex → EngineError（import_module 注入等价手段）。

        前序用例（如 test_develop_state）可能已把真 reflex 导入进程；
        先弹出全部 reflex 模块使其重新成为「新引入」（差集可观测）。
        """
        import pylightroom.core as core

        for name in [
            existing
            for existing in sys.modules
            if existing == "reflex" or existing.startswith("reflex.")
        ]:
            monkeypatch.delitem(sys.modules, name, raising=False)

        real_import_module = importlib.import_module

        def injecting_import_module(name, *args, **kwargs):
            if name.startswith("pylightroom.core."):
                monkeypatch.setitem(sys.modules, "reflex", types.ModuleType("reflex"))
            return real_import_module(name, *args, **kwargs)

        monkeypatch.setattr(importlib, "import_module", injecting_import_module)
        with pytest.raises(EngineError):
            core.HistogramCalculator  # 触发惰性导入 → 差集检测命中

    def test_check_flags_reflex_new_in_diff(self, monkeypatch):
        """差集判定直测：快照后新出现的 reflex 即违规。"""
        import pylightroom.core as core

        before = {
            name
            for name in sys.modules
            if not (name == "reflex" or name.startswith("reflex."))
        }
        monkeypatch.setitem(sys.modules, "reflex", types.ModuleType("reflex"))
        with pytest.raises(EngineError):
            core._check_no_ui_framework(before)

    def test_check_passes_when_reflex_preexisting(self, monkeypatch):
        import pylightroom.core as core

        monkeypatch.setitem(sys.modules, "reflex", types.ModuleType("reflex"))
        core._check_no_ui_framework(set(sys.modules))  # 快照已含 reflex → 不抛
