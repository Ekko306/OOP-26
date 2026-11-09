"""rx.App 组装：创建应用并注册唯一页面（research D6：工厂无副作用，编译入口 reflex run）。"""

import reflex as rx

from pylightroom.ui.pages.index import index_page


def create_app() -> rx.App:
    app = rx.App()
    app.add_page(index_page, route="/")
    return app


# 模块级应用单例：reflex run 经 rxconfig 的 app_module_import 加载本模块并取 app 属性。
app = create_app()
