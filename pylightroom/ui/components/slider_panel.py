"""调整面板：按参数模式动态生成控件（FR-005，research D4）。

渲染规则：面板行由桥接层 computed var `schema_rows` 展平注入
（kind == "slider" → AdjustSlider；kind == "angle" → AngleInput；
crop 等无 factor/angle 形态的调整在桥接层即不生成行）。
仅展示性条件与数据分派，零业务规则（contracts §2.2）。

实现修正（2026-11-09）：前端 dict 迭代（entries 强转）不可靠——
零渲染且无报错；改遍历 list[dict] 行（Reflex 最成熟路径），
空态判断用 has_image 布尔 var。
"""

import reflex as rx

from pylightroom.ui.components.adjust_slider import adjust_slider
from pylightroom.ui.components.angle_input import angle_input


def _row_component(row, *, values_var, angle_value, on_angle_change, slider_handler, apply_handler) -> rx.Component:
    """单行面板项：schema_rows 行 → 滑块/角度输入（纯展示分派）。"""
    name = row["name"].to(str)
    return rx.cond(
        row["kind"] == "slider",
        adjust_slider(
            name=name,
            default=row["default"],
            min_=row["min"],
            max_=row["max"],
            value=values_var[name]["factor"],
            on_change=slider_handler,
        ),
        angle_input(
            name=name,
            default=row["default"],
            angle_value=angle_value,
            on_angle_change=on_angle_change,
            on_apply=apply_handler,
        ),
    )


def slider_panel(rows, values, has_image, angle_value, on_angle_change, slider_handler, apply_handler) -> rx.Component:
    rows_var = rx.Var.create(rows).to(list[dict[str, object]])
    values_var = rx.Var.create(values).to(dict[str, dict[str, float]])
    return rx.vstack(
        rx.cond(
            has_image,
            rx.foreach(
                rows_var,
                lambda row: _row_component(
                    row,
                    values_var=values_var,
                    angle_value=angle_value,
                    on_angle_change=on_angle_change,
                    slider_handler=slider_handler,
                    apply_handler=apply_handler,
                ),
            ),
            rx.text("打开图片后加载调整面板", color_scheme="gray", size="2"),
        ),
        spacing="2",
        width="100%",
    )
