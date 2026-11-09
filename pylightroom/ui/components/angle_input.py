"""角度输入 + 应用按钮（rotate 形态，research D4：点击应用触发，输入值经页面 var 受控）。

实现修正（2026-11-09）：占位改为标量 prop default（数据由 schema_rows 注入）。
"""

import reflex as rx


def angle_input(name, default, angle_value, on_angle_change, on_apply) -> rx.Component:
    """on_apply(name, {"angle": 角度}) 透传引擎校验；数值转换失败由错误通道回显。"""
    return rx.hstack(
        rx.text(name, size="2", width="7em"),
        rx.input(
            value=angle_value,
            on_change=on_angle_change,
            placeholder=rx.Var.create(default).to(str),
            width="6em",
            size="1",
        ),
        rx.button(
            "应用",
            size="1",
            on_click=on_apply(name, {"angle": angle_value.to(float)}),
        ),
        spacing="2",
        width="100%",
        align_items="center",
    )
