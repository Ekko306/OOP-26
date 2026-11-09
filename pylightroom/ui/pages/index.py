"""唯一页面：三区布局组装 + 桥接层绑定（contracts §2.3）。

本模块是表现层唯一 import pylightroom.state 的位置（AST 红线规则⑤）。
UploadBroker 为交互捕获中转（research D2/D3）：上传落盘、路径输入暂存、
导出目录创建与文件名拼接——仅文件 IO 与无分支字符串拼接，不含业务规则。
"""

from pathlib import Path

import reflex as rx

from pylightroom.state import FileState

from pylightroom.ui.components.file_menu import file_menu
from pylightroom.ui.components.histogram_view import histogram_view
from pylightroom.ui.components.preview_canvas import preview_canvas
from pylightroom.ui.components.slider_panel import slider_panel


class UploadBroker(rx.State):
    """页面级交互中转：不 import 桥接层以外的东西，不触碰引擎（research D2）。"""

    path_input: str = ""
    export_format: str = "jpeg"
    angle_input: str = ""

    def set_path_input(self, value: str) -> None:
        self.path_input = value

    def set_export_format(self, value: str) -> None:
        self.export_format = value

    def set_angle_input(self, value: str) -> None:
        self.angle_input = value

    def relay_slider(self, name: str, values: list[float]) -> None:
        """类型适配中转：Reflex slider on_change 提供最终值列表，桥接层收 float。

        单滑块取末位；仅类型转换与转发，不含业务规则（research D4）。"""
        yield FileState.on_slider_change(name, float(values[-1]))

    async def handle_upload(self, files: list) -> None:
        """上传落盘 uploaded_files/<原文件名> 后转发 open_file（research D2）。"""
        for file in files:
            upload_dir = Path("uploaded_files")
            upload_dir.mkdir(parents=True, exist_ok=True)
            filename = getattr(file, "filename", None) or "upload.bin"
            target = upload_dir / Path(filename).name
            target.write_bytes(await file.read())
            yield self.open_file(str(target))  # UploadBroker 继承 FileState，同 State 直转

    async def handle_export(self) -> None:
        """导出到固定 output/ 目录：自动创建、<stem>_edited.<ext>、重名覆盖（research D3）。"""
        async with self.get_state(FileState) as fs:
            file_name = fs.file_name
        if not file_name:
            return
        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)
        extension = "jpg" if self.export_format == "jpeg" else "png"
        target = out_dir / f"{Path(file_name).stem}_edited.{extension}"
        yield FileState.export_file(str(target), self.export_format)


def index_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            file_menu(
                file_name=FileState.file_name,
                has_image=FileState.file_name != "",
                busy=FileState.busy,
                exporting=FileState.exporting,
                error_message=FileState.error_message,
                export_message=FileState.export_message,
                path_value=UploadBroker.path_input,
                on_path_change=UploadBroker.set_path_input,
                on_open_path=FileState.open_file(UploadBroker.path_input),
                on_upload=UploadBroker.handle_upload(rx.upload_files()),
                on_undo=FileState.undo(),
                on_redo=FileState.redo(),
                export_format=UploadBroker.export_format,
                on_format_change=UploadBroker.set_export_format,
                on_export=UploadBroker.handle_export(),
            ),
            rx.hstack(
                rx.vstack(
                    rx.heading("调整", size="4"),
                    slider_panel(
                        rows=FileState.schema_rows,
                        values=FileState.adjustment_values,
                        has_image=FileState.has_image,
                        angle_value=UploadBroker.angle_input,
                        on_angle_change=UploadBroker.set_angle_input,
                        slider_handler=UploadBroker.relay_slider,
                        apply_handler=FileState.apply_adjustment,
                    ),
                    width="280px",
                    align_items="stretch",
                ),
                rx.vstack(
                    preview_canvas(FileState.preview_data_url, FileState.file_name != ""),
                    width="100%",
                ),
                rx.vstack(
                    rx.heading("直方图", size="4"),
                    histogram_view(FileState.histogram_rows),
                    width="340px",
                    align_items="stretch",
                ),
                width="100%",
                align_items="flex-start",
                gap="1em",
            ),
            spacing="4",
            width="90%",
            max_width="1280px",
        ),
        padding="1.5em",
    )
