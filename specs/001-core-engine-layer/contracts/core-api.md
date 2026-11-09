# Contract: 核心引擎公共 API（core-api）

**Feature**: 001-core-engine-layer | **Date**: 2026-11-09

本契约定义 `pylightroom/core` 对上层（桥接层/脚本）暴露的全部公共接口。上层只允许依赖本契约中的名称；工厂注册是接入新子类的唯一途径（准则 IV）。签名中的参数名与刻度以本契约为准，实现不得偏离。

## 1. 门面：ImageProcessor

```python
class ImageProcessor:
    def __init__(self, events: EngineEvents | None = None) -> None: ...
    def open(self, path: str | Path) -> None
        # 经 AssetFactory 创建资产并解码；失败抛 AssetError
    def update_adjustment(self, name: str, params: dict) -> None
        # AdjustmentFactory 创建 → 校验 → 入栈（含合并）→ 低分预览重渲染
        # name 未注册或参数越界抛 AdjustmentError
    def render(self, level: Literal["thumb", "medium", "full"]) -> Image
        # 顺序应用指令链；空栈返回原图；不修改原图
    def undo(self) -> None   # 空历史抛 HistoryError("nothing to undo")
    def redo(self) -> None   # 空重做栈抛 HistoryError("nothing to redo")
    def export(self, path: str | Path, format: Literal["jpeg", "png"]) -> None
        # 全图渲染 → 原子写出；同时写 Sidecar；失败无半成品
```

## 2. 工厂

```python
class AdjustmentFactory:
    @classmethod
    def create(cls, type_name: str, params: dict) -> BaseAdjustment
        # 按注册名反射创建；未注册名抛 AdjustmentError(unknown type)
    @classmethod
    def register(cls, adjustment_cls: type[BaseAdjustment]) -> None
        # 开闭扩展点：新增子类在此注册，存量代码零修改

class AssetFactory:
    @classmethod
    def create(cls, path: str | Path) -> BaseImageAsset
        # 按扩展名分发；不支持扩展名抛 AssetError(unsupported format)
    @classmethod
    def register(cls, extensions: tuple[str, ...], asset_cls: type[BaseImageAsset]) -> None
```

## 3. 调整契约：BaseAdjustment

```python
class BaseAdjustment(ABC):
    name: ClassVar[str]
    param_schema: ClassVar[dict]   # {param: {"min", "max", "default"}}
    @abstractmethod
    def apply(self, image: Image, params: dict) -> Image: ...
    def validate(self, params: dict) -> dict      # 越界抛 AdjustmentError
    def serialize(self) -> dict                    # {"type": name, "params": {...}}
    @classmethod
    def deserialize(cls, data: dict) -> "BaseAdjustment"
    def merge(self, other: "BaseAdjustment") -> bool   # 同类合并（后值覆盖），否则 False
```

注册名与参数（刻度 0.0–2.0，1.0 中性；几何参数自然单位）：

| name | 参数 | 单位/范围 |
| ---- | ---- | ---- |
| `brightness` / `contrast` / `saturation` / `sharpness` | `factor` | 0.0–2.0，默认 1.0 |
| `temperature` | `factor` | 0.0–2.0（>1 暖，<1 冷），默认 1.0 |
| `histogram_equalization` | `factor` | 0.0–2.0（clipLimit 映射），默认 1.0（不启用） |
| `crop` | `box` | (left, top, right, bottom) 像素；须在图界内且宽高>0 |
| `rotate` | `angle` | 度，正值顺时针，任意实数 |

## 4. 资产契约：BaseImageAsset

```python
class BaseImageAsset(ABC):
    path: Path; format: str; exif: dict
    def load(self) -> Image            # 模板方法：异常包装 + 结果缓存
    @abstractmethod
    def _decode(self) -> Image: ...    # 子类实现，返回 Pillow RGB 表示
    def thumbnail(self) -> dict        # {"thumb", "medium", "full"} 三级 Image
```

支持扩展名：`.jpg/.jpeg` `.png` `.bmp` `.webp`；RAW 主验收 `.arw`（`.cr2/.nef` 尽力支持）。PNG 含透明通道时解码为统一 RGB 表示并合成白底。

## 5. 持久化契约：SidecarFile

```python
class SidecarFile:
    @staticmethod
    def sidecar_path_for(image_path: str | Path) -> Path
        # photo.jpg → photo.json
    @staticmethod
    def save(session: EditSession) -> Path     # 原子写；返回 Sidecar 路径
        # Sidecar 路径与 JSON image_path 均取自 session.image_path；
        # session.image_path 为 None 时抛 SidecarError（不可持久化）
    @staticmethod
    def load(image_path: str | Path, session: EditSession) -> None
        # 反射重建指令注入会话；损坏/未知 type/版本抛 SidecarError
```

JSON 协议见 [sidecar-schema.md](./sidecar-schema.md)。

## 6. 观测契约

```python
class HistogramCalculator:
    @staticmethod
    def compute(image: Image) -> dict[str, list[int]]   # {"r","g","b"} 各 256 bin

class EngineEvents(Protocol):
    def on_progress(self, task_id: str, stage: str, fraction: float) -> None: ...
    def on_render_complete(self, task_id: str, image_bytes: bytes) -> None: ...
    def on_error(self, task_id: str, message: str) -> None: ...
```

## 7. 异常体系

| 异常 | 触发 |
| ---- | ---- |
| `AssetError` | 不支持格式、文件损坏、RAW 解码失败（含路径与原因） |
| `AdjustmentError` | 未注册调整名、参数越界/非法 |
| `HistoryError` | 空栈撤销/空栈重做 |
| `SidecarError` | JSON 损坏、未知指令类型、版本不识别 |
| `ExportError` | 渲染或写出失败（保证无半成品） |

## 8. 架构红线（契约级）

- 本契约全部实现位于 `pylightroom/core/`，任何文件不得 import 界面框架（grep 断言对象）
- 事件数据仅原始数据与消息对象；引擎不感知上层类型
- `apply()` 禁止原地修改输入图像（非破坏性，FR-012）
