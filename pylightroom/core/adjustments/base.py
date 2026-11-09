"""BaseAdjustment 抽象基类：调整族契约（继承体系一，准则 II）。

只定义契约：抽象方法 apply、模板方法 validate/serialize/deserialize、
虚方法 merge。子类声明类属性 name 与 param_schema 后即满足里氏替换，
可无差别进入指令栈与处理器（Spec §4.5）。

参数刻度：色彩/锐度类统一 0.0–2.0 浮点因子，1.0 中性；
裁剪/旋转等几何参数按自然单位（像素框/角度）（Clarifications Q1，FR-002）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from PIL import Image

from pylightroom.core.errors import AdjustmentError


class BaseAdjustment(ABC):
    """一次图像调整的抽象指令（命令模式）。"""

    name: ClassVar[str]
    # {param: {"min", "max", "default"}}；几何参数条目可不含 min/max（自然单位）
    param_schema: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, params: dict) -> None:
        self.params: dict = self.validate(params)

    @abstractmethod
    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        """应用调整并返回新图像；禁止原地修改输入（非破坏性，FR-012）。"""

    # ------------------------------------------------------------------
    # 校验（依 param_schema；越界抛 AdjustmentError，FR-002）
    # ------------------------------------------------------------------
    def validate(self, params: dict) -> dict:
        schema = type(self).param_schema
        if not isinstance(params, dict):
            raise AdjustmentError(
                f"'{self.name}': params 必须为字典，得到 {type(params).__name__}"
            )
        unknown = set(params) - set(schema)
        if unknown:
            raise AdjustmentError(
                f"'{self.name}': 未知参数 {sorted(unknown)}，"
                f"合法参数：{sorted(schema)}"
            )
        validated: dict = {}
        for key, rule in schema.items():
            if key in params:
                value = params[key]
            elif "default" in rule:
                value = rule["default"]
            else:
                raise AdjustmentError(f"'{self.name}': 缺少必填参数 '{key}'")
            if "min" in rule and "max" in rule:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise AdjustmentError(
                        f"'{self.name}': 参数 '{key}' 必须为数值，得到 {value!r}"
                    )
                if not (rule["min"] <= value <= rule["max"]):
                    raise AdjustmentError(
                        f"'{self.name}': 参数 '{key}'={value} 超出合法范围 "
                        f"[{rule['min']}, {rule['max']}]"
                    )
            validated[key] = self._coerce(key, value)
        return validated

    def _coerce(self, key: str, value: Any) -> Any:
        """子类可覆写：对自然单位参数做类型/形状校验与规范化。"""
        return value

    # ------------------------------------------------------------------
    # 序列化（往返无损，FR-003 / SC-002）
    # ------------------------------------------------------------------
    def serialize(self) -> dict:
        return {"type": self.name, "params": self._serialize_params(self.params)}

    @staticmethod
    def _serialize_params(params: dict) -> dict:
        return {
            key: (list(value) if isinstance(value, tuple) else value)
            for key, value in params.items()
        }

    @classmethod
    def deserialize(cls, data: dict) -> "BaseAdjustment":
        if not isinstance(data, dict):
            raise AdjustmentError(f"'{cls.name}': 反序列化数据必须为字典")
        type_name = data.get("type")
        if type_name != cls.name:
            raise AdjustmentError(
                f"类型不匹配：期望 '{cls.name}'，得到 {type_name!r}"
            )
        params = data.get("params")
        if not isinstance(params, dict):
            raise AdjustmentError(f"'{cls.name}': params 必须为字典")
        return cls(params)

    # ------------------------------------------------------------------
    # 同类合并（后值覆盖；合并结果等价于后一条单独应用，FR-004）
    # ------------------------------------------------------------------
    def merge(self, other: "BaseAdjustment") -> bool:
        if type(other) is not type(self):
            return False
        self.params = dict(other.params)
        return True

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"{type(self).__name__}({self.params!r})"
