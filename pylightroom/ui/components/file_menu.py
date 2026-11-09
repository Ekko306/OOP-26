"""顶栏菜单：打开（上传/路径）、撤销/重做、导出、忙碌指示、错误与导出消息。

对应 FR-002/006/007/008/009/010/013——数据全经 props、事件全经处理器 props
（contracts §2.2，组件自身零业务规则，仅展示性条件）。
"""

import reflex as rx


def file_menu(
    file_name,
    has_image,
    busy,
    exporting,
    error_message,
    export_message,
    path_value,
    on_path_change,
    on_open_path,
    on_upload,
    on_undo,
    on_redo,
    export_format,
    on_format_change,
    on_export,
) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.upload(
                rx.button("上传图片", size="2"),
                id="pl-upload",
                border="1px dashed gray",
                padding="0.2em 0.6em",
                border_radius="md",
                on_drop=on_upload,
            ),
            rx.input(
                value=path_value,
                on_change=on_path_change,
                placeholder="或输入本地路径",
                size="1",
                width="220px",
            ),
            rx.button("打开", size="2", on_click=on_open_path),
            rx.text(file_name, size="2", color_scheme="gray", width="12em", overflow="hidden"),
            rx.spacer(),
            rx.button("撤销", size="2", on_click=on_undo, disabled=~has_image),
            rx.button("重做", size="2", on_click=on_redo, disabled=~has_image),
            rx.select(
                ["jpeg", "png"],
                value=export_format,
                on_change=on_format_change,
                size="1",
                width="7em",
            ),
            rx.button("导出", size="2", on_click=on_export, disabled=busy | (~has_image)),
            rx.cond(busy, rx.spinner(size="2")),
            rx.cond(exporting, rx.text("导出中…", size="2")),
            spacing="2",
            width="100%",
            align_items="center",
        ),
        rx.cond(
            error_message != "",
            rx.box(
                rx.text(error_message, size="2"),
                background_color="#b91c1c",
                color="white",
                padding="0.4em 0.8em",
                border_radius="md",
                width="100%",
            ),
        ),
        rx.cond(
            export_message != "",
            rx.box(
                rx.text(export_message, size="2"),
                background_color="#15803d",
                color="white",
                padding="0.4em 0.8em",
                border_radius="md",
                width="100%",
            ),
        ),
        spacing="2",
        width="100%",
    )
