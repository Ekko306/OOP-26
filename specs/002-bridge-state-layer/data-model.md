# Data Model: 桥接层（State）

**Feature**: 002-bridge-state-layer | **Date**: 2026-11-09

本文档定义桥接层的状态实体、字段契约与状态转换。层间只存在「引擎 → presenter → Reflex vars」的单一数据流向。

## 1. Presenter（事件翻译器，纯 Python，内部类）

引擎回调的唯一消费者与桥接层的线程边界。

| 字段 | 类型 | 语义 | 约束 |
| ---- | ---- | ---- | ---- |
| `_results` | `dict[str, _Result]` | 预览级 → 最近结果（version、PNG 字节、data URL） | 仅受锁保护写入；「新者胜」：version 更大才覆盖 |
| `_error` | `str \| None` | 最近一条错误消息 | 错误与结果同 version 竞争，新 version 胜 |
| `_error_version` | `int` | 错误所属版本 | 仅高于已有结果的 version 才覆盖 |
| `_busy` | `bool` | 处理中标志 | `on_progress` 置 True；对应 version 的 full 级完成/出错置 False |
| `_condition` | `threading.Condition` | 有界等待原语 | `wait_for(level, version, timeout)` 供处理器同步等待后台结果 |

方法：`on_progress(task_id, stage, fraction)` / `on_render_complete(task_id, image_bytes)` / `on_error(task_id, message)`（实现引擎 `EngineEvents` 协议）；`latest(level) -> _Result \| None`、`wait_for(level, version, timeout)`、`reset()`、`busy` 属性。

任务标识解析：`preview-{level}-v{version}`（level ∈ thumb/medium/full）；无法解析的 task_id 仅记录错误消息，不影响结果容器。

## 2. DevelopState（Reflex State 基类：编辑视图）

| Var | 类型 | 语义 | 初值 |
| ---- | ---- | ---- | ---- |
| `preview_data_url` | `str` | 当前预览（data URL；空串=无预览） | `""` |
| `histogram` | `dict[str, list[int]]` | RGB 三通道直方图（各 256 bin） | 空 dict |
| `adjustment_values` | `dict[str, dict]` | 调整名 → 当前生效参数字典（撤销后随引擎回退；未出现者回补 schema 默认值） | 打开时按 schema 默认值填充 |
| `adjustment_schemas` | `dict[str, dict]` | 调整名 → 参数模式（min/max/default），UI 渲染滑块刻度的唯一来源 | 打开时从 `registered_schemas()` 填充 |
| `busy` | `bool` | 处理中标志（镜像 presenter.busy） | `False` |
| `error_message` | `str` | 可读错误消息（空串=无错误） | `""` |

事件处理器（全部 ≤ 三动作）：

| 处理器 | 签名 | 三动作展开 |
| ---- | ---- | ---- |
| `on_slider_change` | `(name: str, value: float)` | 值→`{factor: value}` → `update_adjustment` → 回写预览/直方图/忙碌/错误（渐进 yield） |
| `apply_adjustment` | `(name: str, params: dict)` | 透传参数字典 → `update_adjustment` → 回写（几何调整通用入口） |
| `undo` / `redo` | `()` | 引擎调用 → `current_params()` 回写 adjustment_values → 预览/直方图回写 |

错误语义：同步异常（`EngineError` 族）与异步 `on_error` 回调统一落 `error_message`；下一次成功操作清除（FR-013）。

## 3. FileState（DevelopState 子状态：文件域）

| Var | 类型 | 语义 | 初值 |
| ---- | ---- | ---- | ---- |
| `file_name` | `str` | 当前编辑文件名 | `""` |
| `has_image` | `bool` | 是否已打开图片（UI 禁用编辑区的依据） | `False` |
| `exporting` | `bool` | 导出进行中标志 | `False` |
| `export_message` | `str` | 导出结果反馈（成功路径/失败原因，空串=无） | `""` |

事件处理器：`open_file(path: str)`（转发 `open` → presenter reset → 文件名/预览/直方图/默认值回写）、`export_file(path: str, format: str)`（`exporting` 置位 → 转发 `export` → 成功/失败消息回写）。

> 导出为同步操作（001 契约），无分数进度事件；`exporting` 即进度呈现形态，spec FR-010 的「进度」按此落定。

## 4. 引擎增量（additive，详见 contracts/state-api.md §3）

- `ImageProcessor.current_params() -> dict[str, dict]`：只读，反向扫描指令栈
- `AdjustmentFactory.registered_schemas() -> dict[str, dict]`：只读，深拷贝防外部篡改注册表
- `_check_no_ui_framework`：检测语义由「全局 sys.modules 扫描」收紧为「core 导入链增量检测」（D2）

## 5. 状态转换（单会话生命周期）

```text
[空闲] --open_file 成功--> [已打开]（has_image=True，默认值预览就绪）
[已打开] --on_slider_change/apply_adjustment--> [处理中 busy=True] --低分回调--> 渐进推送 --full 回调/超时--> [已打开 busy=False]
[已打开] --undo/redo--> 同上（adjustment_values 与指令栈同步）
[已打开] --export_file--> [导出中 exporting=True] --成功/失败--> [已打开 exporting=False + export_message]
[任意] --引擎异常/on_error--> error_message 回写（状态不崩溃，可继续操作）
[已打开] --open_file 成功--> 重置为新会话（presenter.reset，旧在途回调因 session 切换作废）
```

## 6. 校验规则（桥接层不作业务校验）

参数合法性由引擎 `update_adjustment` → `BaseAdjustment.validate` 负责（001 契约）；桥接层只转换与透传，校验失败按 FR-012 落错误消息。
