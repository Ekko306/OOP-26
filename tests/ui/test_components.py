"""哑组件绑定测试（T004/T011/T014）：props 注入 + 组件树 Var 断言（research D7）。"""

import reflex as rx

from pylightroom.state import DevelopState, FileState
from pylightroom.ui.components.adjust_slider import adjust_slider
from pylightroom.ui.components.angle_input import angle_input
from pylightroom.ui.components.file_menu import file_menu
from pylightroom.ui.components.histogram_view import histogram_view
from pylightroom.ui.components.preview_canvas import preview_canvas
from pylightroom.ui.components.slider_panel import slider_panel
from tests.ui._helpers import assert_binds, handler_names, var_tokens


def _menu(**overrides):
    props = dict(
        file_name=FileState.file_name,
        has_image=FileState.file_name != "",
        busy=FileState.busy,
        exporting=FileState.exporting,
        error_message=FileState.error_message,
        export_message=FileState.export_message,
        path_value=UploadBrokerStub.path_input,
        on_path_change=UploadBrokerStub.set_path_input,
        on_open_path=FileState.open_file(UploadBrokerStub.path_input),
        on_upload=FileState.open_file("x"),  # 占位：真实注入见 test_index_page
        on_undo=FileState.undo(),
        on_redo=FileState.redo(),
        export_format=UploadBrokerStub.export_format,
        on_format_change=UploadBrokerStub.set_export_format,
        on_export=FileState.export_file("y", "jpeg"),  # 占位
    )
    props.update(overrides)
    return file_menu(**props)


class UploadBrokerStub(rx.State):  # noqa: N801 —— 组件测试仅需任意 State var
    path_input: str = ""
    export_format: str = "jpeg"
    angle_input: str = ""

    def set_path_input(self, value: str) -> None: ...
    def set_export_format(self, value: str) -> None: ...
    def set_angle_input(self, value: str) -> None: ...

    def relay_slider(self, name: str, values: list[float]) -> None: ...


class TestPreviewCanvas:
    def test_shows_bound_data_url(self):
        comp = preview_canvas(FileState.preview_data_url, FileState.file_name != "")
        assert_binds(comp, FileState.preview_data_url)

    def test_empty_placeholder_constructible(self):
        assert preview_canvas("", False) is not None


class TestHistogramView:
    def test_binds_rows_var(self):
        comp = histogram_view(DevelopState.histogram_rows)
        assert_binds(comp, DevelopState.histogram_rows)

    def test_placeholder_when_empty(self):
        assert histogram_view([]) is not None


class TestFileMenu:
    def test_binds_core_vars_and_events(self):
        comp = _menu()
        assert_binds(
            comp,
            FileState.file_name,
            FileState.busy,
            FileState.exporting,
            FileState.error_message,
            FileState.export_message,
            FileState.undo(),
            FileState.redo(),
            FileState.open_file(UploadBrokerStub.path_input),
            FileState.export_file("y", "jpeg"),
        )

    def test_has_image_drives_controls(self):
        comp = _menu()
        assert_binds(comp, FileState.file_name != "")  # has_image 进 disabled 条件


class TestAdjustSlider:
    def test_binds_value_range_and_handler(self):
        comp = adjust_slider(
            name="brightness",
            default=1.0,
            min_=0.0,
            max_=2.0,
            value=FileState.adjustment_values.to(dict[str, dict[str, float]])["brightness"]["factor"],
            on_change=UploadBrokerStub.relay_slider,
        )
        assert_binds(
            comp,
            FileState.adjustment_values.to(dict[str, dict[str, float]])["brightness"]["factor"],
            UploadBrokerStub.relay_slider("brightness"),
        )


class TestAngleInput:
    def test_applies_angle_params_via_button(self):
        comp = angle_input(
            name="rotate",
            default=0.0,
            angle_value=UploadBrokerStub.angle_input,
            on_angle_change=UploadBrokerStub.set_angle_input,
            on_apply=FileState.apply_adjustment,
        )
        assert_binds(
            comp,
            UploadBrokerStub.angle_input,
            UploadBrokerStub.set_angle_input,
            FileState.apply_adjustment("rotate", {"angle": UploadBrokerStub.angle_input.to(float)}),
        )


_SAMPLE_ROWS = [
    {"name": "brightness", "kind": "slider", "min": 0.0, "max": 2.0, "default": 1.0},
    {"name": "rotate", "kind": "angle", "min": -360.0, "max": 360.0, "default": 0.0},
]


class TestSliderPanel:
    def _panel(self, rows=_SAMPLE_ROWS):
        return slider_panel(
            rows=rows,
            values=FileState.adjustment_values,
            has_image=True,
            angle_value=UploadBrokerStub.angle_input,
            on_angle_change=UploadBrokerStub.set_angle_input,
            slider_handler=UploadBrokerStub.relay_slider,
            apply_handler=FileState.apply_adjustment,
        )

    def test_dispatches_slider_for_factor_row(self):
        assert_binds(self._panel(), UploadBrokerStub.relay_slider("brightness"))

    def test_dispatches_angle_input_for_angle_row(self):
        assert_binds(self._panel(), FileState.apply_adjustment("rotate", {"angle": UploadBrokerStub.angle_input.to(float)}))

    def test_no_crop_hardcoded_in_panel(self):
        # crop 排除规则由桥接层 schema_rows 承载（tests/state/test_develop_state.py），面板树无 crop 硬编码
        tokens = var_tokens(self._panel()) | handler_names(self._panel())
        assert not any("crop" in token for token in tokens)

    def test_empty_rows_placeholder(self):
        comp = self._panel([])
        assert comp is not None
