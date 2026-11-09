"""T012：DevelopState 调整链路测试（US2 滑块渐进更新）。

状态直接实例化（_reflex_internal_init=True，research D6）；真实引擎先 open
再模拟滑块/几何事件；渐进生成器在 yield 时刻采样 frames 观测时序。
超时降级用替身处理器（thumb 同步送达、full 永不送达，research D4）。
"""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from pylightroom.state import develop_state as develop_state_module
from pylightroom.state import session as session_module
from pylightroom.state.develop_state import DevelopState
from pylightroom.state.presenter import Presenter
from pylightroom.state.session import EngineSession


def exhaust(events) -> None:
    """耗尽渐进生成器事件处理器。"""
    for _ in events:
        pass


def png_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(
        "ascii"
    )


@pytest.fixture
def state():
    """直接实例化 + 干净会话（组合根注入点，contracts/state-api.md §4）。"""
    session_module.set_session(None)
    instance = DevelopState(_reflex_internal_init=True)
    yield instance
    session_module.set_session(None)


@pytest.fixture
def large_png(tmp_path):
    """400x300 样图：thumb(≤256) 与 full 渲染尺寸不同，可区分渐进两帧。"""
    image = Image.new("RGB", (400, 300))
    px = image.load()
    for y in range(300):
        for x in range(400):
            px[x, y] = (x % 256, y % 256, (x + y) % 256)
    path = tmp_path / "large.png"
    image.save(path, "PNG")
    return path


@pytest.fixture
def opened_session(large_png):
    """真实引擎已打开图片的会话（打开是 FileState 职责，US1）。"""
    session = session_module.get_session()
    session.processor.open(str(large_png))
    return session


class _StuckFullProcessor:
    """替身处理器：thumb 同步送达、full 永不送达（超时降级用，D4）。

    需要提供真 PIL 图的 render()：直方图计算（D7）在桥接层内进行。
    """

    def __init__(self, presenter: Presenter, image: Image.Image) -> None:
        self._presenter = presenter
        self._image = image
        self._version = 0

    @property
    def version(self) -> int:
        return self._version

    def current_params(self) -> dict[str, dict]:
        return {}

    def render(self, level: str) -> Image.Image:
        return self._image

    def update_adjustment(self, name: str, params: dict) -> None:
        self._version += 1
        buffer = io.BytesIO()
        self._image.save(buffer, "PNG")
        task = f"preview-thumb-v{self._version}"
        self._presenter.on_progress(task, "render", 0.0)
        self._presenter.on_render_complete(task, buffer.getvalue())
        # full 级事件永不送达 → wait_for 必然超时


class TestSliderForwarding:
    def test_forwards_factor_to_engine(self, state, opened_session):
        """滑块值经 {factor: value} 参数转换转发引擎（contracts §2）。"""
        exhaust(state.on_slider_change("brightness", 1.5))
        assert opened_session.processor.current_params()["brightness"] == {
            "factor": 1.5
        }
        assert state.adjustment_values["brightness"] == {"factor": 1.5}

    def test_progressive_thumb_then_full(self, state, opened_session):
        """渐进推送：第一帧 = thumb 渲染，终帧 = full 渲染（SC-005 顺序性）。"""
        assert state.preview_data_url == ""  # 打开由 FileState 负责，初始无预览
        frames: list[str] = []
        for _ in state.on_slider_change("brightness", 1.2):
            frames.append(state.preview_data_url)
        processor = opened_session.processor
        assert frames, "渐进处理器至少推送一帧"
        assert frames[0] == png_data_url(processor.render("thumb"))
        assert state.preview_data_url == png_data_url(processor.render("full"))
        assert len(frames[0]) < len(state.preview_data_url)

    def test_busy_lifecycle_true_then_false(self, state, opened_session):
        """busy 生命周期：第一帧（full 未到位）忙碌，full 到位后解除。"""
        frames: list[bool] = []
        for _ in state.on_slider_change("brightness", 1.2):
            frames.append(state.busy)
        assert frames == [True]
        assert state.busy is False

    def test_histogram_refreshes_per_adjustment(self, state, opened_session):
        """直方图随每次调整刷新（内容变化可观测）。"""
        exhaust(state.on_slider_change("brightness", 1.0))
        before = dict(state.histogram)
        assert before, "首次调整后应已有直方图"
        exhaust(state.on_slider_change("brightness", 2.0))
        assert dict(state.histogram) != before

    def test_rapid_updates_converge_to_latest(self, state, opened_session):
        """快速连发：新者胜，终态收敛到最高版本的预览与参数。"""
        exhaust(state.on_slider_change("brightness", 1.2))
        exhaust(state.on_slider_change("brightness", 1.5))
        processor = opened_session.processor
        assert processor.current_params() == {"brightness": {"factor": 1.5}}
        assert state.preview_data_url == png_data_url(processor.render("full"))
        assert state.busy is False


class TestApplyAdjustment:
    def test_rotate_angle_passthrough(self, state, opened_session):
        """几何调整通用入口：params 原样透传引擎。"""
        exhaust(state.apply_adjustment("rotate", {"angle": 90}))
        assert opened_session.processor.current_params()["rotate"] == {"angle": 90}
        assert state.adjustment_values["rotate"] == {"angle": 90}

    def test_out_of_range_rejected(self, state, opened_session):
        """引擎拒绝越界参数：错误落通道、预览保持最近有效帧、界面不变。"""
        exhaust(state.on_slider_change("brightness", 1.5))
        good_preview = state.preview_data_url
        good_values = dict(state.adjustment_values)
        exhaust(state.apply_adjustment("brightness", {"factor": 3.0}))
        assert state.error_message != ""
        assert state.preview_data_url == good_preview
        assert dict(state.adjustment_values) == good_values
        assert opened_session.processor.current_params()["brightness"] == {
            "factor": 1.5
        }

    def test_next_success_clears_error(self, state, opened_session):
        """FR-013：新成功操作清除旧错误消息。"""
        exhaust(state.apply_adjustment("brightness", {"factor": 3.0}))
        assert state.error_message != ""
        exhaust(state.on_slider_change("brightness", 1.3))
        assert state.error_message == ""


class TestFullTimeoutDegradation:
    def test_timeout_keeps_thumb_frame_and_busy(
        self, state, monkeypatch, rgb_image
    ):
        """full 永不送达：有界超时后保留低分帧，busy 按引擎实况保持。"""
        monkeypatch.setattr(
            develop_state_module, "FULL_WAIT_TIMEOUT_SECONDS", 0.05
        )
        presenter = Presenter()
        processor = _StuckFullProcessor(presenter, rgb_image)
        session_module.set_session(
            EngineSession(processor=processor, presenter=presenter)
        )
        exhaust(state.on_slider_change("brightness", 1.5))
        assert state.preview_data_url == png_data_url(rgb_image)
        assert state.busy is True  # presenter 实况：full 未完成即仍忙碌
        assert state.error_message == ""


class TestUndoRedo:
    def test_undo_reverts_values_and_preview(self, state, opened_session):
        """撤销后：参数值与预览随引擎指令栈回退（FR-008）。"""
        exhaust(state.on_slider_change("brightness", 1.5))
        exhaust(state.undo())
        processor = opened_session.processor
        assert processor.current_params() == {}
        assert state.adjustment_values == {}
        assert state.preview_data_url == png_data_url(processor.render("full"))
        assert state.error_message == ""

    def test_undo_backfills_schema_default(self, state, opened_session):
        """被撤销名按 schema 默认值回补（滑块同步，data-model §2）。"""
        from pylightroom.core import AdjustmentFactory

        state.adjustment_schemas = AdjustmentFactory.registered_schemas()
        exhaust(state.on_slider_change("brightness", 1.5))
        exhaust(state.undo())
        assert state.adjustment_values["brightness"] == {"factor": 1.0}

    def test_redo_advances_values_and_preview(self, state, opened_session):
        """重做后：值与预览前进一致。"""
        exhaust(state.on_slider_change("brightness", 1.5))
        exhaust(state.undo())
        exhaust(state.redo())
        processor = opened_session.processor
        assert processor.current_params() == {"brightness": {"factor": 1.5}}
        assert state.adjustment_values["brightness"] == {"factor": 1.5}
        assert state.preview_data_url == png_data_url(processor.render("full"))

    def test_empty_stack_undo_readable(self, state, opened_session):
        """空栈撤销：HistoryError 转译为可读提示，界面不变（FR-009）。"""
        exhaust(state.undo())
        assert state.error_message != ""
        assert state.busy is False
        assert state.preview_data_url == ""

    def test_empty_stack_redo_readable(self, state, opened_session):
        exhaust(state.redo())
        assert state.error_message != ""
        assert state.preview_data_url == ""

    def test_sequence_consistency_sc004(self, state, opened_session):
        """任意操作序列后 adjustment_values 与引擎 current_params 一致（SC-004）。"""
        exhaust(state.on_slider_change("brightness", 1.5))
        exhaust(state.apply_adjustment("rotate", {"angle": 90}))
        exhaust(state.on_slider_change("contrast", 0.8))
        exhaust(state.undo())  # 撤销 contrast
        exhaust(state.undo())  # 撤销 rotate，剩 brightness
        processor = opened_session.processor
        assert processor.current_params() == {"brightness": {"factor": 1.5}}
        assert state.adjustment_values == {"brightness": {"factor": 1.5}}
        exhaust(state.redo())  # 恢复 rotate
        assert processor.current_params() == {
            "brightness": {"factor": 1.5},
            "rotate": {"angle": 90},
        }
        assert state.adjustment_values == processor.current_params()
