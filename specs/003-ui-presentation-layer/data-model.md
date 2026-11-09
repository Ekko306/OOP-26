# Data Model: 表现层（UI）——单页编辑界面

**Feature**: 003-ui-presentation-layer | **Date**: 2026-11-09

本层无持久实体。数据只沿「桥接层 State vars → 组件 props → 渲染」单向流动，用户操作沿「组件事件 → 桥接层处理器」单向回流。本文档定义组件实体、props/事件契约与绑定关系；桥接层字段语义见 002 的 data-model.md。

## 1. 组件实体（哑组件，零业务状态、零业务分支）

### AdjustSlider（单滑块，因子型）

| Props | 类型 | 语义 |
| ---- | ---- | ---- |
| `name` | str | 调整名（展示为标签） |
| `value` | Var(float) | 当前值（页面注入 `adjustment_values[name]["factor"]`） |
| `min` / `max` / `default` | float | 刻度范围与默认（页面注入自 `adjustment_schemas[name]["factor"]`） |
| `on_change` | 事件处理器 | 页面注入 `FileState.on_slider_change`（携带 name） |

### AngleInput（角度输入，rotate 专用形态）

| Props | 类型 | 语义 |
| ---- | ---- | ---- |
| `name` | str | 调整名（rotate） |
| `value` | Var(float) | 当前角度（`adjustment_values[name]["angle"]`） |
| `default` | float | 默认角（schema 注入，任意实数） |
| `on_apply` | 事件处理器 | 页面注入 `FileState.apply_adjustment`（透传 `{"angle": 输入值}`） |

### SliderPanel（调整面板）

| Props | 类型 | 语义 |
| ---- | ---- | ---- |
| `schemas` | Var(dict) | `adjustment_schemas`（渲染的唯一数据源） |
| `values` | Var(dict) | `adjustment_values`（当前值注入） |
| `on_slider_change` / `on_apply` | 事件处理器 | 转发给子控件 |

渲染规则（D4，数据驱动、无硬编码调整名）：`schema` 含 `min`/`max` → AdjustSlider；单参数无 min/max → AngleInput 形态；`box`（crop）不渲染；顺序 = 调整名字母序。空 schemas → 面板空态提示。

### HistogramView（直方图）

| Props | 类型 | 语义 |
| ---- | ---- | ---- |
| `histogram` | Var(dict) | `{"r"|"g"|"b": [256 档]}`（桥接层原样注入） |

内部纯格式映射（D5）：dict → `[{bin, r, g, b}]` 图表行，recharts 三系列柱状叠加；空 dict → 占位提示。

### PreviewCanvas（预览画布）

| Props | 类型 | 语义 |
| ---- | ---- | ---- |
| `data_url` | Var(str) | 当前预览 data URL（空串 → 空态占位「未打开图片」） |
| `has_image` | Var(bool) | 是否已打开图片 |

### FileMenu（顶栏）

| Props | 类型 | 语义 |
| ---- | ---- | ---- |
| `file_name` | Var(str) | 当前文件名展示 |
| `busy` / `exporting` | Var(bool) | 忙碌/导出中指示（进行中禁用重复触发类操作） |
| `error_message` / `export_message` | Var(str) | 错误横幅 / 导出结果消息 |
| `has_image` | Var(bool) | 撤销/重做/导出可用性 |
| `on_undo` / `on_redo` | 事件处理器 | 撤销/重做 |
| `on_export` | 事件处理器 | 导出（携带所选格式） |
| `on_open_path` | 事件处理器 | 路径输入打开 |
| `on_upload` | 事件处理器 | 上传落盘处理（D2） |

## 2. 页面（pages/index.py）——唯一绑定组装点

页面把上述组件组合为单页三区布局，并以桥接层完成绑定：

| 绑定方向 | 内容 |
| ---- | ---- |
| State → props | `preview_data_url`、`histogram`、`adjustment_values`、`adjustment_schemas`、`busy`、`error_message`、`exporting`、`export_message`、`file_name`、`has_image` |
| 事件 → 处理器 | `on_slider_change`、`apply_adjustment`、`undo`、`redo`、`export_file`（经 `on_export` 携带格式与 D3 拼接路径）、`open_file`（路径入口；上传经 D2 落盘后调用） |

## 3. 运行期目录（git 忽略，不进包）

| 目录 | 用途 | 生命周期 |
| ---- | ---- | ---- |
| `output/` | 固定导出目录（D3：`<stem>_edited.<ext>`，重名覆盖） | 不存在则由 UI 侧创建 |
| `uploaded_files/` | 上传暂存（D2：落盘后以其路径调 open_file） | 持续累积，课程范围不清理 |

## 4. 状态依赖关系（引用 002，零改动）

- `has_image`（003 新增派生判断）= `FileState.file_name != ""`；UI 仅读既有 vars，不新增 State 字段
- 撤销/重做后滑块同步由 002 保证（`adjustment_values` 随 `current_params` 回填）——UI 无同步逻辑
- 忙碌期重复触发由 002 渐进管线「新者胜」兜底，UI 仅呈现指示（FR-010）
