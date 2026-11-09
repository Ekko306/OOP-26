"""T018：错误隔离参数化测试（US5）。

引擎全部异常族 → 对应消息通道回写、零未捕获异常；异步回调错误按版本
门控回显；错误后界面可继续操作（FR-012/FR-013）。
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pylightroom.state import session as session_module
from pylightroom.state.file_state import FileState
from pylightroom.state.presenter import Presenter
from pylightroom.state.session import EngineSession


def exhaust(events) -> None:
    """耗尽渐进生成器事件处理器。"""
    for _ in events:
        pass


@pytest.fixture
def state():
    session_module.set_session(None)
    instance = FileState(_reflex_internal_init=True)
    yield instance
    session_module.set_session(None)


@pytest.fixture
def large_png(tmp_path):
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
    session = session_module.get_session()
    exhaust_session = session.processor
    exhaust_session.open(str(large_png))
    return session


# (处理器, 参数工厂, 消息通道, 异常族标识)
SYNC_ERROR_CASES = [
    ("open_file", lambda tp: (str(tp / "missing.png"),), "error_message", "AssetError"),
    (
        "on_slider_change",
        lambda tp: ("brightness", 99.0),
        "error_message",
        "AdjustmentError",
    ),
    (
        "apply_adjustment",
        lambda tp: ("brightness", {"factor": -1.0}),
        "error_message",
        "AdjustmentError",
    ),
    ("undo", lambda tp: (), "error_message", "HistoryError"),
    ("redo", lambda tp: (), "error_message", "HistoryError"),
]


class TestSyncErrorIsolation:
    @pytest.mark.parametrize(
        ("handler", "make_args", "channel", "exc_name"),
        SYNC_ERROR_CASES,
        ids=[case[3] for case in SYNC_ERROR_CASES],
    )
    def test_engine_error_lands_in_channel(
        self, state, opened_session, tmp_path, handler, make_args, channel, exc_name
    ):
        """引擎同步异常族 → 消息通道回写、无异常冒泡（FR-012）。"""
        exhaust(getattr(state, handler)(*make_args(tmp_path)))
        assert getattr(state, channel) != ""
        assert state.busy is False

    def test_export_error_lands_in_export_channel(
        self, state, opened_session, tmp_path
    ):
        """ExportError → export_message 独立通道，不污染 error_message。"""
        target = tmp_path / "as-dir.jpg"
        target.mkdir()
        exhaust(state.export_file(str(target)))
        assert state.export_message != ""
        assert state.error_message == ""
        assert state.exporting is False

    def test_failed_open_then_successful_open_recovers(
        self, state, large_png, tmp_path
    ):
        """打开失败后再打开成功：视图完整恢复（恢复性）。"""
        exhaust(state.open_file(str(tmp_path / "missing.png")))
        assert state.error_message != ""
        exhaust(state.open_file(str(large_png)))
        assert state.error_message == ""
        assert state.has_image is True
        assert state.preview_data_url != ""


class _FailingFullProcessor:
    """替身处理器：thumb 同步送达、full 级以错误回调失败（异步错误面）。

    与真实引擎一致：thumb 渲染成功、full 渲染经回调通道报错——
    wait_for 的「同版本错误提前中断」路径由此可测。
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
        return self._image  # 真 PIL 图：直方图计算（D7）可用

    def update_adjustment(self, name: str, params: dict) -> None:
        self._version += 1
        buffer = io.BytesIO()
        self._image.save(buffer, "PNG")
        task = f"preview-thumb-v{self._version}"
        self._presenter.on_progress(task, "render", 0.0)
        self._presenter.on_render_complete(task, buffer.getvalue())
        self._presenter.on_error(
            f"preview-full-v{self._version}", "BackgroundRenderError: mock"
        )


class TestAsyncErrorSurface:
    def test_same_version_error_surfaces_in_message(
        self, state, rgb_image
    ):
        """引擎后台线程失败回调（同版本）→ error_message、busy 按实况解除。"""
        presenter = Presenter()
        processor = _FailingFullProcessor(presenter, rgb_image)
        session_module.set_session(
            EngineSession(processor=processor, presenter=presenter)
        )
        exhaust(state.on_slider_change("brightness", 1.2))
        assert state.error_message == "BackgroundRenderError: mock"
        assert state.busy is False  # full 级错误清忙
        assert state.preview_data_url != ""  # 低分帧保留（超时降级语义同样适用）

    def test_stale_error_not_resurfaced(self, state, opened_session):
        """旧版本异步错误不随后续操作复现（版本门控，FR-013 语义）。

        EditSession 版本单调递增：旧错误的 error_version 恒小于新操作版本。
        """
        session = opened_session
        exhaust(state.on_slider_change("brightness", 1.2))
        session.presenter.on_error(
            f"preview-full-v{session.processor.version}", "BackgroundRenderError: stale"
        )
        exhaust(state.on_slider_change("brightness", 1.5))  # 新版本操作
        assert state.error_message == ""  # 旧错不回显
        assert state.preview_data_url != ""  # 新操作正常出图


class TestRecoveryAfterErrors:
    def test_errors_then_normal_operation_recovers(
        self, state, opened_session, tmp_path
    ):
        """任意错误后继续正常操作恢复正常；新成功操作清除旧错误（FR-013）。"""
        exhaust(state.on_slider_change("brightness", 3.0))  # 越界
        assert state.error_message != ""
        exhaust(state.on_slider_change("brightness", 1.2))  # 恢复
        assert state.error_message == ""
        assert state.preview_data_url != ""
        exhaust(state.export_file(str(tmp_path / "x.gif"), format="gif"))  # 再错
        assert state.export_message != ""
        exhaust(state.on_slider_change("contrast", 1.3))  # 再恢复
        assert state.error_message == ""
        assert state.preview_data_url != ""
