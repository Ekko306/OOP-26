"""T008：FileState.open_file 打开链路测试（US1，先失败后实现）。

状态直接实例化（_reflex_internal_init=True，research D6）；每例注入全新会话。
事件处理器为渐进生成器：测试中耗尽迭代以执行全部回写步骤。
"""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from pylightroom.core import AdjustmentFactory, HistogramCalculator, SidecarFile
from pylightroom.state import session as session_module
from pylightroom.state.file_state import FileState


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
    instance = FileState(_reflex_internal_init=True)
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


class TestOpenFileSuccess:
    def test_sets_name_and_flag(self, state, png_sample):
        exhaust(state.open_file(str(png_sample)))
        assert state.has_image is True
        assert state.file_name == "sample.png"
        assert state.error_message == ""

    def test_progressive_thumb_then_full(self, state, large_png):
        """渐进推送：第一帧 = thumb 渲染，终帧 = full 渲染（US1/SC-005 语义）。"""
        frames: list[str] = []
        for _ in state.open_file(str(large_png)):
            frames.append(state.preview_data_url)
        session = session_module.get_session()
        assert frames, "渐进处理器至少推送一帧"
        assert frames[0] == png_data_url(session.processor.render("thumb"))
        assert state.preview_data_url == png_data_url(session.processor.render("full"))
        assert len(frames[0]) < len(state.preview_data_url)

    def test_histogram_from_engine_three_channels(self, state, png_sample):
        """直方图经引擎 HistogramCalculator（D7），三通道各 256 桶。"""
        exhaust(state.open_file(str(png_sample)))
        session = session_module.get_session()
        expected = HistogramCalculator.compute(session.processor.render("thumb"))
        assert state.histogram == {
            channel: list(bins) for channel, bins in expected.items()
        }
        assert set(state.histogram) == {"r", "g", "b"}
        assert all(len(bins) == 256 for bins in state.histogram.values())

    def test_schemas_come_from_factory(self, state, png_sample):
        exhaust(state.open_file(str(png_sample)))
        assert state.adjustment_schemas == AdjustmentFactory.registered_schemas()

    def test_adjustment_values_backfilled_with_defaults(self, state, png_sample):
        """缺席调整名回补 schema 默认值（滑块初值全覆盖）。"""
        exhaust(state.open_file(str(png_sample)))
        assert set(state.adjustment_values) == set(state.adjustment_schemas)
        for name, params in state.adjustment_values.items():
            expected = {
                param: rule.get("default")
                for param, rule in state.adjustment_schemas[name].items()
            }
            assert params == expected


class TestOpenFileFailure:
    def test_corrupted_file_keeps_previous_view(self, state, png_sample, corrupted_file):
        """打开失败仅落 error_message，既有预览/直方图/名称不变（FR-004）。"""
        exhaust(state.open_file(str(png_sample)))
        snapshot = (
            state.file_name,
            state.has_image,
            state.preview_data_url,
            dict(state.histogram),
        )
        exhaust(state.open_file(str(corrupted_file)))
        assert state.error_message != ""
        assert (
            state.file_name,
            state.has_image,
            state.preview_data_url,
            dict(state.histogram),
        ) == snapshot

    def test_unsupported_extension(self, state, tmp_path):
        bogus = tmp_path / "file.xyz"
        bogus.write_bytes(b"whatever")
        exhaust(state.open_file(str(bogus)))
        assert state.error_message != ""
        assert state.has_image is False

    def test_missing_file(self, state, tmp_path):
        exhaust(state.open_file(str(tmp_path / "missing.png")))
        assert state.error_message != ""
        assert state.has_image is False


class TestReopenResets:
    def test_reopen_resets_to_fresh_edit_view(self, state, png_sample, jpeg_sample):
        """重复打开重置为干净编辑视图（FR-002）：参数回默认、文件名更新。"""
        exhaust(state.open_file(str(png_sample)))
        exhaust(state.on_slider_change("brightness", 1.8))
        assert state.adjustment_values["brightness"] == {"factor": 1.8}
        exhaust(state.open_file(str(jpeg_sample)))
        assert state.file_name == "sample.jpg"
        for name, params in state.adjustment_values.items():
            expected = {
                param: rule.get("default")
                for param, rule in state.adjustment_schemas[name].items()
            }
            assert params == expected


class TestExportFile:
    def test_export_success_writes_artifacts(self, state, png_sample, tmp_path):
        """导出成功：exporting 先 True 后 False，成品与原图关联 Sidecar 落盘。"""
        exhaust(state.open_file(str(png_sample)))
        out = tmp_path / "out.jpg"
        frames: list[tuple[bool, str]] = []
        for _ in state.export_file(str(out)):
            frames.append((state.exporting, state.export_message))
        assert frames, "导出处理器至少推送一帧"
        assert frames[0][0] is True  # 第一帧：导出中
        assert state.exporting is False
        assert state.export_message != ""
        assert out.is_file()
        assert SidecarFile.sidecar_path_for(png_sample).is_file()

    def test_export_failure_readable_no_tmp(self, state, png_sample, tmp_path):
        """导出失败：原因可读、无崩溃、无残留临时文件（FR-020）。"""
        exhaust(state.open_file(str(png_sample)))
        target = tmp_path / "as-dir.jpg"
        target.mkdir()  # 目标本身是目录 → 写出必失败
        exhaust(state.export_file(str(target)))
        assert state.export_message != ""
        assert state.exporting is False
        assert not list(tmp_path.glob("*.tmp"))

    def test_export_invalid_format_rejected(self, state, png_sample, tmp_path):
        """非法格式透传引擎拒绝（合法限定 jpeg/png，contracts §2）。"""
        exhaust(state.open_file(str(png_sample)))
        exhaust(state.export_file(str(tmp_path / "out.gif"), format="gif"))
        assert state.export_message != ""
        assert state.exporting is False
        assert not (tmp_path / "out.gif").exists()
