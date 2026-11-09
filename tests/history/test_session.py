"""US2 非破坏性会话测试：有序栈、同类合并、撤销/重做、版本号（FR-012–FR-015, FR-017）。"""

from __future__ import annotations

import pytest

from pylightroom.core.adjustments.basic import BrightnessAdjustment, ContrastAdjustment
from pylightroom.core.adjustments.geometry import RotateAdjustment
from pylightroom.core.errors import HistoryError
from pylightroom.core.history import EditSession


@pytest.fixture
def session() -> EditSession:
    return EditSession()


class TestAppendOrdering:
    def test_append_two_adjustments_keeps_order(self, session):
        session.append(BrightnessAdjustment({"factor": 1.2}))
        session.append(ContrastAdjustment({"factor": 1.5}))
        assert [a.name for a in session.instructions] == ["brightness", "contrast"]
        assert session.instructions[0].params["factor"] == 1.2

    def test_different_type_not_merged(self, session):
        session.append(BrightnessAdjustment({"factor": 1.2}))
        session.append(ContrastAdjustment({"factor": 1.5}))
        assert len(session.instructions) == 2


class TestSameTypeMerge:
    def test_same_type_merges_into_single_record(self, session):
        session.append(BrightnessAdjustment({"factor": 1.2}))
        session.append(BrightnessAdjustment({"factor": 1.5}))
        assert len(session.instructions) == 1, "同类相邻调整入栈前必须合并（FR-015）"
        assert session.instructions[0].params["factor"] == 1.5, "后值覆盖"

    def test_merge_only_with_stack_top(self, session):
        session.append(BrightnessAdjustment({"factor": 1.2}))
        session.append(ContrastAdjustment({"factor": 1.5}))
        session.append(BrightnessAdjustment({"factor": 1.8}))
        assert [a.name for a in session.instructions] == ["brightness", "contrast", "brightness"]

    def test_merge_still_bumps_version(self, session):
        session.append(BrightnessAdjustment({"factor": 1.2}))
        v0 = session.version
        session.append(BrightnessAdjustment({"factor": 1.5}))
        assert session.version == v0 + 1, "合并也视为一次变更，version 仍自增"


class TestUndoRedo:
    def test_undo_pops_last(self, session):
        session.append(BrightnessAdjustment({"factor": 1.2}))
        session.append(ContrastAdjustment({"factor": 1.5}))
        session.undo()
        assert [a.name for a in session.instructions] == ["brightness"]

    def test_redo_restores(self, session):
        session.append(BrightnessAdjustment({"factor": 1.2}))
        session.append(ContrastAdjustment({"factor": 1.5}))
        session.undo()
        session.redo()
        assert [a.name for a in session.instructions] == ["brightness", "contrast"]

    def test_undo_empty_raises(self, session):
        with pytest.raises(HistoryError):
            session.undo()

    def test_redo_empty_raises(self, session):
        with pytest.raises(HistoryError):
            session.redo()

    def test_undo_all_then_redo_all(self, session):
        session.append(BrightnessAdjustment({"factor": 1.2}))
        session.append(ContrastAdjustment({"factor": 1.5}))
        session.undo()
        session.undo()
        assert session.instructions == []
        session.redo()
        session.redo()
        assert [a.name for a in session.instructions] == ["brightness", "contrast"]

    def test_append_after_undo_clears_redo(self, session):
        """撤销后追加新调整必须清空重做历史（FR-014）。"""
        session.append(BrightnessAdjustment({"factor": 1.2}))
        session.append(ContrastAdjustment({"factor": 1.5}))
        session.undo()
        session.append(RotateAdjustment({"angle": 90}))
        with pytest.raises(HistoryError):
            session.redo()
        assert [a.name for a in session.instructions] == ["brightness", "rotate"]

    def test_merged_append_after_undo_clears_redo_too(self, session):
        session.append(BrightnessAdjustment({"factor": 1.2}))
        session.append(ContrastAdjustment({"factor": 1.5}))
        session.undo()
        session.append(BrightnessAdjustment({"factor": 1.9}))  # 合并入栈
        with pytest.raises(HistoryError):
            session.redo()


class TestVersionBumping:
    def test_version_increments_on_every_change(self, session):
        assert session.version == 0
        session.append(BrightnessAdjustment({"factor": 1.2}))
        v1 = session.version
        assert v1 == 1
        session.append(ContrastAdjustment({"factor": 1.5}))
        session.undo()
        session.redo()
        assert session.version == 4, "append/undo/redo 均自增 version（FR-017 前置）"


class TestNonDestructiveContract:
    def test_instructions_are_append_only_objects(self, session):
        """指令对象为追加式，会话不持有/不触碰原图像素（FR-012）。"""
        session.append(BrightnessAdjustment({"factor": 1.2}))
        first = session.instructions[0]
        session.append(ContrastAdjustment({"factor": 1.5}))
        session.undo()
        assert session.instructions[0] is first, "对象身份稳定，仅列表增减"

    def test_no_image_reference_in_session(self):
        """EditSession 不含任何图像处理逻辑/原图引用。"""
        session = EditSession()
        assert not hasattr(session, "image") or session.__dict__.get("image") is None
        assert "PIL" not in type(session).__module__
