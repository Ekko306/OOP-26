"""Reflex 应用配置。

app_module_import 指向 pylightroom/ui/app.py（模块级 app 单例），
替代 Reflex 默认的 `app_name/app_name.py` 布局约定（plan D6 变体，
库型包结构与 Reflex 运行约定的衔接）。
"""

import reflex as rx

config = rx.Config(
    app_name="pylightroom",
    app_module_import="pylightroom.ui.app",
)
