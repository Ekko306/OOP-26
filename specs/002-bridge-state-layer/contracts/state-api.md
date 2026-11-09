# Contract: 桥接层公共 API（state-api）

**Feature**: 002-bridge-state-layer | **Date**: 2026-11-09

本契约定义 `pylightroom/state` 对表现层（UI）暴露的全部公共接口，以及为支撑桥接而对引擎层做的增量（additive）。UI 只允许依赖本契约中的名称；§1/§2 的名称与签名是实现不得偏离的验收依据。

## 1. 状态变量（UI 绑定面）

```python
class DevelopState(rx.State):
    preview_data_url: str                 # data URL，空串=无预览
    histogram: dict[str, list[int]]       # {"r","g","b": [256 bin]}
    adjustment_values: dict[str, dict]    # 调整名 → 当前生效参数（撤销后与引擎同步；缺席名已回补默认值）
    adjustment_schemas: dict[str, dict]   # 调整名 → {param: {min, max, default}}（滑块刻度唯一来源）
    busy: bool                            # 处理中标志
    error_message: str                    # 可读错误，空串=无；新成功操作清除

class FileState(DevelopState):            # 子状态：继承全部编辑变量（Reflex 子状态语义）
    file_name: str
    has_image: bool
    exporting: bool
    export_message: str
```

## 2. 事件处理器（UI 事件入口，均 ≤「参数转换 + 引擎调用 + 状态回写」三动作）

```python
# FileState
def open_file(self, path: str) -> None
    # 转发引擎 open；成功：presenter.reset → file_name/has_image/预览/直方图/默认值回写（低分先行渐进推送）
    # 失败：error_message 回写，既有界面状态不变
def export_file(self, path: str, format: str) -> None
    # exporting 置位 → 转发引擎 export（同步）→ export_message 回写（成功路径或失败原因）

# DevelopState
def on_slider_change(self, name: str, value: float) -> None      # 值 → {"factor": value} → update_adjustment → 渐进回写
def apply_adjustment(self, name: str, params: dict) -> None      # 通用入口（几何调整等），params 透传 → update_adjustment → 渐进回写
def undo(self) -> None   # 引擎 undo → current_params 回写 adjustment_values → 预览/直方图回写（渐进）
def redo(self) -> None   # 引擎 redo → 同上
```

渐进回写语义（`on_slider_change`/`apply_adjustment`/`undo`/`redo` 共用）：

1. `busy=True` → 引擎调用；低分（thumb）回调在调用内同步送达 → 回写 `preview_data_url`（thumb）+ `histogram` → `yield` 推送第一帧
2. `presenter.wait_for("full", version, timeout=有界)` 等待后台高分 → 命中：回写 full 帧并 `busy=False`；超时：保留低分帧，`busy` 按 presenter 实况落定
3. 中途到达的旧 version 结果由 presenter 丢弃（新者胜），处理器无需感知

错误语义：处理器内同步 `EngineError` 族与回调错误统一落 `error_message`，不向 UI 抛出；打开失败不触碰既有预览/直方图。

## 3. 引擎增量契约（additive，未改动 001 契约任何既有签名）

```python
# pylightroom/core/pipeline.py —— 只读查询
class ImageProcessor:
    def current_params(self) -> dict[str, dict]
        # 按调整名汇总当前生效参数：自指令栈顶向下首次命中者生效；撤销后随栈同步消失
        # 未打开图片时返回 {}

# pylightroom/core/adjustments/factory.py —— 只读查询
class AdjustmentFactory:
    @classmethod
    def registered_schemas(cls) -> dict[str, dict]
        # 全部已注册调整的参数模式深拷贝：{name: {param: {"min","max","default"}}}
        # 返回副本，外部修改不得影响注册表

# pylightroom/core/__init__.py —— 红线自检语义修正（D2）
    # _check_no_ui_framework：由「全局 sys.modules 扫描」改为「core 导入链增量检测」
    # 仅当 reflex 在 core 包本次导入期间被新引入时抛 EngineError
    # grep 断言红线（core/ 零 import reflex）不变

# pylightroom/core/pipeline.py —— 渐进预览入口（D8，实现期新增 additive）
class ImageProcessor:
    def refresh_previews(self) -> None
        # 渲染并推送当前版本三级预览（thumb 同步先行，medium/full 由后台线程补齐）
        # 供桥接层 open_file 成功后调用：open() 本身不产生预览事件（001 契约不变）
        # 未打开图片抛 AssetError；调整/撤销/重做路径已内置刷新，无需重复调用
        # 可靠性（D9）：后台渲染以「会话对象身份 + 版本」双校验，
        # 重开图片使版本归零时旧在途渲染以对象身份区分，不污染新会话
```

## 4. 内部模块（UI 不得直接引用）

- `presenter.Presenter`：`EngineEvents` 实现；版本新者胜；data URL 编码；忙碌/错误通道；`wait_for` 有界等待
- `session.get_session()` / `session.set_session()`：组合根（`ImageProcessor` + presenter）；`set_session` 仅供测试注入替身

## 5. 架构红线（契约级）

- `state/` 是唯一允许同时 import Reflex 与 `pylightroom.core` 的层（tests/state/test_architecture.py grep 断言）
- state 层不直接 import Pillow/OpenCV/rawpy（直方图与预览字节一律经引擎接口）
- 事件处理器出现业务 if/else 分支即违规（逻辑下沉引擎）
- 层间仅传递原始数据与消息对象（参数字典、图像字节、data URL、进度/错误消息）
