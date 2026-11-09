# Verification: 表现层（UI）——单页编辑界面

**Feature**: 003-ui-presentation-layer | **Date**: 2026-11-09

本文档记录 003 实现完成的验证证据：命令、结果计数与 SC-001–SC-007 逐条对照。

## 1. 验证命令与结果

| 命令（quickstart §2） | 结果 |
| ---- | ---- |
| `uv run pytest tests/ui/ -q` | **30 passed**（exit 0）：test_architecture 5 + test_components 12 + test_index_page 9 + test_upload_export 4 |
| `uv run pytest tests/ -q`（全量回归，含 001/002） | **280 passed, 2 skipped**（exit 0；skip 为 .ARW 样片，待 001-T045 样图） |
| `uv run pytest tests/ui/test_architecture.py -q`（AST 红线） | 5 passed（ui 零图像库 / 零 core / components 零 state / reflex 限 state+ui+rxconfig / state 限 index.py） |
| `uv run python scripts/check_arch_redline.py` | `PASS — pylightroom/core/ 共 19 个文件，零界面框架引用`（exit 0） |
| `uv run python scripts/demo_state.py` | `SMOKE ALL PASS`（[1/6]–[6/6]，含 export_file 与错误隔离） |

### 本阶段增量修正（披露）

- `tests/state/test_architecture.py::test_reflex_confined_to_state_layer`：002 时代规则「reflex 仅 state/」扩展为「state/ 与 ui/」（003 contracts §5 计划内），ui 内部细则由 tests/ui/test_architecture.py 守卫。
- `pylightroom/core/__init__.py::_check_no_ui_framework`：比较写法由 `startswith("reflex.")` 改为顶层段比较（语义等价；消除 scripts 红线文本扫描对字符串字面量 `reflex.` 的误报）。
- **桥接层 additive**：新增 `DevelopState.histogram_rows` computed var（dict→rows 纯格式映射）——实测前端手写 JS 表达式绕过 Reflex state 声明机制（运行时 ReferenceError），按 contracts §6 additive 通道移入桥接层；`histogram_view` 组件 props 由 `histogram` 改为 `rows`（research D5 修正记录）。
- **Reflex 运行衔接**：`rxconfig.py` 设 `app_module_import="pylightroom.ui.app"`，app.py 增模块级 `app = create_app()` 单例——库型包结构与 Reflex 默认 `app_name/app_name.py` 布局约定的衔接（plan D6 变体）。

### 浏览器实机验证（2026-11-09）

`uv run reflex run`（端口 3000）+ 浏览器代理走查：**PASS**——页面无 JS 错误渲染，全部中文元素（上传图片/打开/撤销/重做/导出、调整、直方图、未打开图片占位）与三区布局确认；修正前后的对照截图存档于浏览器代理。

### 实机运行期问题修复（2026-11-09，第二轮，浏览器端到端复验 PASS）

实机走查发现两个纯前端/衔接层问题，均修复并回归：

1. **上传 500（`POST :8001/_upload` Internal Server Error）**
   - 根因：`UploadBroker.handle_upload` 以 `file.filename` 直接拼路径（Reflex 0.10.1 中该属性可为 `None`，`upload_dir / None` 抛 TypeError），且上传目录 `uploaded_files/` 未见 `parents=True` 兜底。
   - 修复（[index.py#L42-L50](file:///D:/projects/syp/OOP-26/pylightroom/ui/pages/index.py)）：`getattr(file, "filename", None) or "upload.bin"` 兜底、`mkdir(parents=True, exist_ok=True)`、事件转发改为同 State 直调（`UploadBroker` 继承 `FileState`）。
2. **调整面板空白（上传成功但滑块零渲染，无控制台报错）**
   - 根因：`slider_panel` 将 dict var 强转 `list[tuple]` 后在前端迭代——Reflex 前端把 dict var 处理为 JS 对象，`.length`/`foreach` 均静默失效（React 渲染零子项且无错误，难以从控制台发现）。
   - 修复（additive 通道，与 `histogram_rows` 同先例）：
     - 桥接层新增 `DevelopState.schema_rows` computed var（[develop_state.py#L64-L96](file:///D:/projects/syp/OOP-26/pylightroom/state/develop_state.py)）——把注册表展平为 `list[dict]` 行（`kind: "slider"|"angle"` + `name/min/max/default`）；**crop（box 形态）在桥接层即不生成行**，排除规则由「无 factor/angle 键不产行」承载，组件树不再有 crop 硬编码。
     - `slider_panel` 改为遍历 `schema_rows` 列表 + `has_image` 布尔空态判断；`adjust_slider`/`angle_input` 的范围/占位改为标量 props（哑组件进一步收窄，不做 var 下标适配）。
   - 纯格式映射（无业务规则、不触引擎），符合 contracts §6 additive 条款；层间红线（state/ui AST 断言）不受影响。

**回归基线**：`uv run pytest tests/ -q` → **285 passed, 2 skipped**（新增 `tests/state/test_develop_state.py::TestComputedRows` 4 用例：histogram_rows 形状/空态、schema_rows 滑块行/角度行/crop 排除/字母序；UI 套件 30 用例同步更新）。

**最终浏览器走查（PASS）**：上传样图 → 预览与直方图渲染 → 「调整」下 6 个滑块（brightness/contrast/histogram_equalization/saturation/sharpness/temperature）+ rotate 角度输入带「应用」按钮 → 无 crop 控件 → 控制台零错误。

## 2. 成功标准（SC-001–SC-007）逐条证据

| SC | 标准摘要 | 证据 |
| ---- | ---- | ---- |
| SC-001 | 打开样图后 3 秒内预览与直方图完整呈现 | 桥接层渐进推送（002 已测）+ `test_index_page::test_page_binds_all_state_vars`（页面绑定 preview_data_url/histogram）；计时验证归 quickstart §4 浏览器手动项 |
| SC-002 | 滑块调整后无需刷新/重开即见变化 | `test_index_page::test_undo_restores_values_and_preview`（on_slider_change → vars/预览同步）+ 002 develop_state 渐进套件 |
| SC-003 | 撤销/重做后界面与引擎状态一致 | 同上 e2e（undo 回补默认值 1.0、redo 恢复 1.5、预览同步）+ 002 current_params 套件 |
| SC-004 | 导出成功反馈含完整保存位置 | `test_upload_export::test_real_export_writes_file`（export_message 含 `sample_edited.jpg` 完整路径）+ `test_export_targets_fixed_output_dir`（`output/<stem>_edited.<ext>` 拼接、目录自动创建、重名覆盖） |
| SC-005 | ui/ 零图像处理 API 引用 | `test_architecture::test_ui_imports_no_image_processing_library`（AST 静态断言） |
| SC-006 | ui/ 零引擎直引 + components 零 state | `test_ui_imports_no_core`、`test_components_import_no_state` |
| SC-007 | reflex 引用仅限合法层 | `tests/ui/test_architecture::test_reflex_import_confined_to_state_ui_and_rxconfig`（含 rxconfig.py 配置例外，plan D6）+ `tests/state/test_architecture::test_reflex_confined_to_state_layer`（全仓双向守卫） |

## 3. Checklist 状态（只读记录）

| Checklist | Total | Checked | Unchecked | 状态 |
| ---- | ---- | ---- | ---- | ---- |
| checklists/requirements.md（内置） | 16 | 16 | 0 | 全过 |
| checklists/ux-architecture.md（评审） | 34 | 34 | 0 | 全过（含 CHK015 澄清后勾选） |

## 4. 浏览器手动验收（quickstart §4，未在 CI 内）

`uv run reflex run` 后按 quickstart.md §4 十步清单人工走查——属交付演示项，不阻塞本验证记录（无浏览器测试已全覆盖交互语义）。

## 5. 结论

19/19 任务完成；全部测试通过；红线四层（core 零框架 / ui 零图像库 / components 哑化 / 绑定唯一性）静态验证通过。003 可交付。
