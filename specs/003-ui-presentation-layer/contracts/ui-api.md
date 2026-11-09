# Contract: UI 层契约（页面-组件 + 层级红线）

**Feature**: 003-ui-presentation-layer | **Date**: 2026-11-09

本契约界定 `pylightroom/ui/` 对内的组装方式与对外的依赖边界。桥接层契约见 `specs/002-bridge-state-layer/contracts/state-api.md`（本特性零改动，仅消费）。

## §1 模块与公共面

```text
pylightroom/ui/__init__.py    # 层级声明 + 导出 create_app()
pylightroom/ui/app.py         # create_app() -> rx.App：创建应用、注册页面路由 "/"
rxconfig.py                   # 根目录 Reflex 配置：app_name="pylightroom"，其余默认
pylightroom/ui/pages/index.py # index_page() -> 组件树：三区布局 + 桥接层绑定（唯一 import state 的 UI 模块）
pylightroom/ui/components/*   # 六类哑组件：仅 import reflex，props 注入
```

- `create_app()`：无副作用工厂（便于测试构建），内部 `app.add_page(index_page, route="/")`
- 运行入口：`uv run reflex run`（开发模式，默认端口）

## §2 页面-组件绑定契约（props 名称见 data-model.md §1）

每个哑组件 MUST 满足：

1. 模块内零 `pylightroom.state` import（组件连 State 都不引用，D1）
2. 零业务分支：仅允许展示性条件（空态占位、禁用态）与纯格式映射（直方图 dict→rows、导出路径拼接）
3. 数据经 props 注入、事件经回调 props 上抛；组件不持有可变状态

页面 `index_page()` MUST 满足：

1. 是 UI 层唯一 import `pylightroom.state` 的模块，绑定仅使用其公共导出面（`FileState`/`DevelopState` 的 vars 与事件处理器）
2. 组合六类组件：FileMenu（顶）、SliderPanel（左）、PreviewCanvas（中）、HistogramView（右）及错误/导出反馈呈现
3. 事件回流全部经桥接层处理器：滑块 → `on_slider_change`；旋转 → `apply_adjustment("rotate", {"angle": v})`；撤销/重做 → `undo`/`redo`；导出 → `export_file(拼接路径, 格式)`（D3）；打开 → 路径直调 `open_file` 或上传落盘后调 `open_file`（D2）

## §3 导出路径拼接（D3）

```text
path = output / f"{Path(file_name).stem}_edited.{ext}"    # ext ∈ {"jpg"(jpeg) | "png"}
```

- 目录不存在则创建（UI 侧一次性 `mkdir`，属交互捕获文件 IO，非图像处理）
- 重名覆盖；成功反馈展示完整保存路径（`export_message` 由桥接层提供）
- 格式选择仅 jpeg/png 两项（引擎支持集的子集，与 FR-008 一致）

## §4 上传流转（D2）

```text
rx.upload 控件 → UI 上传处理器（落盘 uploaded_files/<原文件名>）→ FileState.open_file(落盘路径)
```

- 落盘文件名沿用原名；上传处理器属 UI 层「交互捕获」职责（Reflex 上传对象不进 state 层）
- 路径输入框作为开发调试入口，直接调 `open_file(输入路径)`
- 两者失败均走引擎异常 → 桥接层错误通道 → 错误横幅（UI 零 try/except 业务分支）

## §5 层级红线（AST 静态断言，扩展 002 的 test_architecture.py）

| 规则 | 断言 |
| ---- | ---- |
| 图像处理库隔离 | `ui/` 零 `PIL`/`cv2`/`rawpy` import |
| 引擎直引隔离 | `ui/` 零 `pylightroom.core`（或 `pylightroom.core.*`）import |
| 组件哑化 | `ui/components/` 零 `pylightroom.state` import |
| reflex 分布 | 全仓 `import reflex` 仅存在于 `pylightroom/state/` 与 `pylightroom/ui/` |
| 双 import 唯一性 | `pylightroom.state` 仅被 `pylightroom/state/` 自身与 `pylightroom/ui/pages/index.py` 引用（UI 侧） |

红线测试纳入 `tests/ui/test_architecture.py`，与 002 红线（core 零 reflex 等）共同构成 SC-005/SC-006/SC-007 的 CI 证据。

## §6 对既有契约的影响

- `pylightroom/core/`：零改动
- `pylightroom/state/`：零改动（仅消费公共面；若实现中发现缺口，按 002 Assumptions 以 additive 方式补并回写契约）
- 新增顶层：`rxconfig.py`、`output/`（运行期，git 忽略）、`uploaded_files/`（运行期，git 忽略）
