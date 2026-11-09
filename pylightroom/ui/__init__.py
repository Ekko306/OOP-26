"""表现层（ui）：Reflex 组件、页面路由与交互捕获。

层级红线（specs/003-ui-presentation-layer/contracts/ui-api.md §5）：
- 本层仅允许 import Reflex 与 pylightroom.state 的公共导出面；
- 禁止图像处理库（PIL/cv2/rawpy）与 pylightroom.core 直引；
- components/ 子包零 pylightroom.state import（哑组件，数据经 props 注入、事件经回调上抛）；
- pylightroom.state 仅被 pages/index.py 引用（唯一绑定组装点）。
"""

from typing import Any

__all__ = ["create_app"]


def __getattr__(name: str) -> Any:
    if name != "create_app":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from pylightroom.ui.app import create_app

    return create_app
