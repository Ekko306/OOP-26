"""单滑块（因子型调整）：标签 + 数值 + 滑块，值/范围/回调全经 props 注入（data-model §1）。

实现修正（2026-11-09）：范围改为标量 props（min_/max_/default）——面板数据
由桥接层 schema_rows 展平后逐行注入（前端 dict 下标不可靠，见 develop_state
schema_rows 注释）。
"""

import reflex as rx


def adjust_slider(name, default, min_, max_, value, on_change) -> rx.Component:
    """on_change 为 EventHandler 引用；调用 on_change(name) 生成 partial 事件，
    剩余 value 参数（list[float]，Reflex slider 触发器类型）由事件填充，
    由页面级 relay 转换为 float 后转发桥接层（contracts §2.2 哑组件不做类型适配）。"""
    value_var = rx.Var.create(value)
    return rx.vstack(
        rx.hstack(
            rx.text(name, size="2", width="7em"),
            rx.text(value_var.to_string(), size="1", color_scheme="gray"),
            justify="between",
            width="100%",
        ),
        rx.slider(
            default=default,
            min_=min_,
            max_=max_,
            value=[value_var],
            on_change=on_change(name),
            width="100%",
        ),
        spacing="1",
        width="100%",
    )
