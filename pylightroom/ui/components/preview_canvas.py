"""预览画布：data URL 呈现 + 空态占位（data-model §1；仅展示性条件，FR-003/FR-011）。"""

import reflex as rx


def preview_canvas(data_url, has_image) -> rx.Component:
    """按 has_image 切换「预览图 / 未打开图片」占位。"""
    return rx.cond(
        has_image,
        rx.center(
            rx.image(
                src=data_url,
                width="100%",
                max_height="70vh",
                object_fit="contain",
                border_radius="md",
            ),
            height="100%",
            width="100%",
        ),
        rx.center(
            rx.text("未打开图片", color_scheme="gray", size="4"),
            height="60vh",
            width="100%",
        ),
    )
