"""AdjustmentFactory：按类型标识反射创建（开闭扩展点，准则 IV / FR-006）。

新增调整策略的唯一接入途径：继承 BaseAdjustment → 调用 register()，
存量代码零修改（FR-026，SC-006 插件演示验收项）。
"""

from __future__ import annotations

from pylightroom.core.adjustments.base import BaseAdjustment
from pylightroom.core.errors import AdjustmentError


class AdjustmentFactory:
    """策略注册表：name → 子类。"""

    _registry: dict[str, type[BaseAdjustment]] = {}

    @classmethod
    def create(cls, type_name: str, params: dict) -> BaseAdjustment:
        adjustment_cls = cls._registry.get(type_name)
        if adjustment_cls is None:
            raise AdjustmentError(
                f"unknown adjustment type: {type_name!r}（未注册，"
                f"已注册：{sorted(cls._registry)}）"
            )
        return adjustment_cls(params)

    @classmethod
    def register(cls, adjustment_cls: type[BaseAdjustment]) -> type[BaseAdjustment]:
        """注册扩展点；可作装饰器使用。"""
        if not (isinstance(adjustment_cls, type) and issubclass(adjustment_cls, BaseAdjustment)):
            raise AdjustmentError(
                f"register 仅接受 BaseAdjustment 子类，得到 {adjustment_cls!r}"
            )
        cls._registry[adjustment_cls.name] = adjustment_cls
        return adjustment_cls

    @classmethod
    def registered_names(cls) -> list[str]:
        return sorted(cls._registry)
