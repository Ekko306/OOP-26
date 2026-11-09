"""直方图视图：RGB 三通道柱状（FR-004，research D5）。

dict→rows 的格式映射在桥接层 computed var `histogram_rows` 完成
（003 实现修正：前端手写 JS 绕过 state 声明机制，见 002 additive 记录）；
本组件仅绑定 rows var 与空态占位。
"""

import reflex as rx


def histogram_view(rows) -> rx.Component:
    """三通道柱状叠加；空行集（未打开）呈现占位提示。"""
    rows_var = rx.Var.create(rows).to(list[dict])
    return rx.cond(
        rows_var.length() == 0,
        rx.center(
            rx.text("直方图（未打开图片）", color_scheme="gray", size="2"),
            height="220px",
            width="100%",
        ),
        rx.recharts.bar_chart(
            rx.recharts.bar(data_key="r", fill="#ef4444"),
            rx.recharts.bar(data_key="g", fill="#22c55e"),
            rx.recharts.bar(data_key="b", fill="#3b82f6"),
            rx.recharts.x_axis(data_key="bin"),
            rx.recharts.y_axis(),
            data=rows_var,
            height=220,
        ),
    )
