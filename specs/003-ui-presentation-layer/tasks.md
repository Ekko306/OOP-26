---

description: "Task list for feature implementation"
---

# Tasks: 表现层（UI）——单页编辑界面

**Input**: Design documents from `/specs/003-ui-presentation-layer/`

**Prerequisites**: plan.md（必需）✅、spec.md（必需）✅、research.md ✅、data-model.md ✅、contracts/ui-api.md ✅、quickstart.md ✅

**Tests**: 包含测试任务——项目宪法准则 V（引擎独立可测、测试先行）为强制约束，全部测试无浏览器（research D7）。

**Organization**: 按用户故事分组，支持独立实现与验证。对 `core/` 与 `state/` **零改动**（纯新增层）。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1–US5，映射 spec.md 优先级 P1→P3）
- 描述含精确文件路径

## Path Conventions

- 纯 Python 全栈（Reflex）：`pylightroom/ui/`（表现层）+ 根 `rxconfig.py` + `tests/ui/`
- 运行期目录：`output/`（导出）、`uploaded_files/`（上传暂存）——git 忽略，不进包

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 应用骨架与运行期约定

- [x] T001 创建根 `rxconfig.py`（`app_name="pylightroom"`，其余默认，research D6）；`.gitignore` 增补 `output/`、`uploaded_files/`、`.web/`（Reflex 运行产物）
- [x] T002 [P] 创建 UI 包骨架：`pylightroom/ui/__init__.py`（模块 docstring 声明层级红线：仅 Reflex 与桥接层公共面；`__all__ = ["create_app"]` + PEP 562 惰性导出）、`pylightroom/ui/components/__init__.py`、`pylightroom/ui/pages/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 架构红线守卫——先于一切 UI 代码就位（准则 V + SC-005/006/007）

**⚠️ CRITICAL**: 本阶段完成后才可开始任何用户故事

- [x] T003 创建 `tests/ui/test_architecture.py`：按 contracts/ui-api.md §5 落实五条 AST 静态断言——①`pylightroom/ui/` 零 `PIL`/`cv2`/`rawpy` import；②`ui/` 零 `pylightroom.core`（含子模块）直引；③`ui/components/` 零 `pylightroom.state` import；④全仓 `import reflex` 仅存在于 `pylightroom/state/` 与 `pylightroom/ui/`；⑤`pylightroom.state` 被 UI 侧引用的模块仅 `pylightroom/ui/pages/index.py`。测试不 import 被检模块，仅 AST/文本扫描 `pylightroom/` 目录（此时 ui 近空应即通过，随实现持续守卫）

**Checkpoint**: 红线守卫就位，UI 实现在其保护下推进

---

## Phase 3: User Story 1 — 打开图片查看预览与直方图 (Priority: P1) 🎯 MVP

**Goal**: 用户在单页上传或输入路径打开图片，渐进预览与直方图呈现，空态/文件名/布局齐备（FR-001/002/011，SC-001）

**Independent Test**: `uv run pytest tests/ui/ -q` 全绿 + 组件树断言四类组件绑定存在 + 真实引擎链路（上传落盘→open_file→状态回写）通过

### Tests for User Story 1 ⚠️（先写，确认 FAIL 再实现）

- [x] T004 [P] [US1] 创建 `tests/ui/test_components.py`：PreviewCanvas 用例（data_url 呈现绑定、空态占位、has_image 驱动）与 HistogramView 用例（r/g/b 三系列绑定、空 dict 空态）——以示例 props 直接构造组件，断言组件树中关键 Var 的字符串形式（research D7）
- [x] T005 [P] [US1] 创建 `tests/ui/test_index_page.py` 骨架用例：`index_page()` 组件树包含四类组件（FileMenu/SliderPanel 占位计数、PreviewCanvas、HistogramView）且绑定 `FileState`/`DevelopState` 关键 vars（`preview_data_url`/`histogram`/`file_name`/`has_image`）与处理器（`open_file`）

### Implementation for User Story 1

- [x] T006 [US1] 实现 `pylightroom/ui/components/preview_canvas.py`：data URL 呈现（`rx.image`）、空态占位（「未打开图片」）、has_image 驱动切换；仅展示性条件（data-model §1）
- [x] T007 [P] [US1] 实现 `pylightroom/ui/components/histogram_view.py`：`{"r"|"g"|"b": [256档]}` → `[{bin, r, g, b}]` 纯格式映射（research D5）+ `rx.recharts` BarChart 三系列叠加；空 dict 占位
- [x] T008 [US1] 实现 `pylightroom/ui/components/file_menu.py`（一次成型，US3/US4/US5 在此之上加测试）：上传控件（落盘 `uploaded_files/<原文件名>` 后调 `open_file`，research D2）、路径输入 + 打开按钮、文件名展示、undo/redo 按钮、导出格式选择（jpeg/png）+ 导出按钮（拼接 `output/<stem>_edited.<ext>`，research D3）、busy/exporting 忙碌指示、error_message/export_message 呈现——数据全经 props、事件全经处理器 props（contracts §2）
- [x] T009 [US1] 实现 `pylightroom/ui/pages/index.py`（三区布局组装 + 桥接层绑定，UI 唯一 import state 的模块）与 `pylightroom/ui/app.py`（`create_app()` 无副作用工厂 + `app.add_page(index_page, route="/")`，research D6）；更新 `pylightroom/ui/__init__.py` 惰性导出
- [x] T010 [US1] 创建 `tests/ui/test_upload_export.py` US1 部分：上传落盘→`open_file` 链路（真实引擎 + 临时目录，State 直接实例化模式承 002）、路径打开、损坏文件错误反馈（既有视图保持）、打开新图视图整体重置（US2/AC3）

**Checkpoint**: User Story 1 独立可测——打开→预览→直方图全链路无浏览器验证通过

---

## Phase 4: User Story 2 — 滑块调整实时更新 (Priority: P1)

**Goal**: 调整面板按参数模式动态生成滑块/角度控件，拖动即时渐进更新（FR-003/005，SC-002，澄清 Q1：旋转进、裁剪不渲染）

**Independent Test**: 面板组件树按 schema 渲染断言通过 + `on_slider_change`/`apply_adjustment` 绑定存在 + 全量 ui 套件不回退

### Tests for User Story 2 ⚠️

- [x] T011 [P] [US2] 扩展 `tests/ui/test_components.py`：AdjustSlider 用例（值/范围/默认来自注入 schema、`on_slider_change` 绑定含调整名）与 AngleInput 用例（数值输入 + 应用按钮 → `apply_adjustment` 透传 `{"angle": 值}`）

### Implementation for User Story 2

- [x] T012 [P] [US2] 实现 `pylightroom/ui/components/adjust_slider.py`：标签（调整名）+ 滑块，min/max/default 与值经 props 注入（data-model §1）
- [x] T013 [P] [US2] 实现 `pylightroom/ui/components/angle_input.py`：数值输入 + 应用按钮，default 经 props 注入（research D4）
- [x] T014 [US2] 实现 `pylightroom/ui/components/slider_panel.py`：schema 驱动渲染——含 `min`/`max` → AdjustSlider、单参数无 min/max → AngleInput 形态、`box`（crop）不渲染、顺序为调整名字母序、空 schemas 空态（research D4）；`tests/ui/test_components.py` 补面板渲染规则用例（用真实 `registered_schemas` 形态的样例 schema 断言控件类型分派）

**Checkpoint**: User Stories 1+2 独立可测——打开→拖滑块→渐进更新链路通过

---

## Phase 5: User Story 3 — 撤销与重做同步交互 (Priority: P2)

**Goal**: 顶栏撤销/重做可用，预览与滑块同步回退/前进，空栈可读提示（FR-004，US3/AC1–AC3）

**Independent Test**: 组件树断言 undo/redo 处理器绑定存在 + FileState 驱动的撤销→`adjustment_values`/预览同步回退端到端用例通过（同步机制由 002 已测，本层验证绑定与状态流）

### Tests for User Story 3 ⚠️

- [x] T015 [US3] 扩展 `tests/ui/test_index_page.py`：FileMenu 中 undo/redo 事件绑定断言；FileState 直接实例化端到端用例——开图→滑块调整→处理器 undo→断言 `adjustment_values` 回退至默认、`preview_data_url` 更新；空栈 undo → `error_message` 可读提示且界面 vars 不变（FR-009）

**Checkpoint**: User Stories 1+2+3 独立可测

---

## Phase 6: User Story 4 — 导出成品 (Priority: P2)

**Goal**: 一键导出到固定 `output/` 目录（免输入），成功反馈含完整保存位置（FR-008，澄清 Q2，SC-003）

**Independent Test**: 导出链路真实引擎端到端——`output/` 自动创建、`<stem>_edited.<ext>` 拼接、重名覆盖、jpeg/png 两格式、成功后 `export_message` 含路径

### Tests for User Story 4 ⚠️

- [x] T016 [US4] 扩展 `tests/ui/test_upload_export.py`：导出路径拼接规则（`photo.png` + jpeg → `output/photo_edited.jpg`，D3）、目录不存在自动创建、重名覆盖、两种格式真实导出链路（State 直接实例化驱动 `export_file`）、成功后 `export_message` 断言

**Checkpoint**: User Stories 1–4 独立可测

---

## Phase 7: User Story 5 — 错误反馈与忙碌指示 (Priority: P3)

**Goal**: 错误横幅可读呈现、旧错随新操作清除、忙碌/导出中指示可见（FR-009/010/013，SC-004）

**Independent Test**: 组件树断言错误横幅与忙碌指示绑定存在 + 「操作发起即清旧错」端到端用例通过（错误通道机制由 002 已测）

### Tests for User Story 5 ⚠️

- [x] T017 [US5] 扩展 `tests/ui/test_index_page.py`：错误横幅绑定 `error_message`、忙碌指示绑定 `busy`/`exporting`、导出反馈绑定 `export_message` 断言；端到端用例——先制造错误（损坏文件打开失败）→ 再成功操作（`on_slider_change`）→ 断言 `error_message` 清零（FR-013）

**Checkpoint**: 全部五个用户故事独立可测

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 全量验证与交付记录

- [x] T018 运行 quickstart.md §2 全部命令（ui 套件 / 全量回归 / 红线测试 / `scripts/check_arch_redline.py` / `scripts/demo_state.py` 冒烟），创建 `specs/003-ui-presentation-layer/verification.md`：记录各命令结果（含计数与 exit code）、SC-001–SC-007 逐条证据（模板承 002）、`checklists/` 状态表（内置 16/16 + ux-architecture 评审状态，只读记录不修改标记）
- [x] T019 复核 `tasks.md` 全部勾选 `[X]`，对照 spec.md SC-001–SC-007 逐条标注证据位置（verification.md 章节引用）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始（T001 → T002 可并行执行）
- **Foundational (Phase 2)**: 依赖 Phase 1——**阻断所有用户故事**（红线守卫先行）
- **US1 (Phase 3)**: 依赖 Phase 2；T004/T005（测试）→ T006/T007（并行）→ T008 → T009（组装）→ T010
- **US2 (Phase 4)**: 依赖 Phase 3（SliderPanel 需页面已组装才能进组件树断言）；T011 → T012/T013（并行）→ T014
- **US3 (Phase 5)**: 依赖 Phase 4（断言对象含 FileMenu 与面板的完整页面）
- **US4 (Phase 6)**: 依赖 Phase 3（FileMenu 已成型）；与 US3 无文件冲突可并行
- **US5 (Phase 7)**: 依赖 Phase 3；与 US3/US4 无文件冲突，但按验收顺序靠后
- **Polish (Phase 8)**: 依赖全部用户故事完成

### User Story Dependencies

- **US1（P1）**: Foundational 后立即可做——含页面组装与 FileMenu 成型，是 US2–US5 的承载面（唯一有结构性依赖的故事）
- **US2（P1）**: 依赖 US1 的页面组装（组件树断言需页面就位）
- **US3（P2）/US4（P2）/US5（P3）**: 均只依赖 US1 的组件成型，彼此零文件冲突——理论可并行，串行推进时按 P2→P2→P3

### Within Each User Story

- 测试先写并确认 FAIL（红）→ 实现转绿（准则 V）
- 组件先于组装、被组合者先于组合者
- 每故事在 Checkpoint 处独立验证后推进

### Parallel Opportunities

- T001/T002（Setup 两文件无交集）
- T004/T005、T006/T007、T011、T012/T013（同阶段不同文件）
- US3/US4/US5 的测试文件互不重叠（test_index_page / test_upload_export / test_index_page——US3 与 US5 同文件需串行）

---

## Parallel Example: User Story 1

```text
# 测试先行（并行）：
Task: "T004 [P] [US1] tests/ui/test_components.py 预览画布与直方图用例"
Task: "T005 [P] [US1] tests/ui/test_index_page.py 页面组装骨架用例"

# 组件实现（并行）：
Task: "T006 [US1] components/preview_canvas.py"
Task: "T007 [P] [US1] components/histogram_view.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1–2：骨架 + 红线守卫
2. Phase 3：US1（打开→预览→直方图）
3. **STOP and VALIDATE**：`uv run pytest tests/ui/ -q` 全绿 + `uv run reflex run` 手动开图看预览
4. MVP 已可演示（SC-001 达成）

### Incremental Delivery

- +US2 → 滑块调整可演示（SC-002）
- +US3/US4 → 撤销与导出闭环（US4 结束即功能完备）
- +US5 → 反馈打磨 → Phase 8 全量验证交付

### Single Developer Strategy

按 Phase 顺序串行执行（本仓无多人协作场景）；故事内遵循测试先红后绿的 TDD 节奏。

---

## Notes

- [P] 任务 = 不同文件、无未完成依赖
- [Story] 标签保证任务到需求（FR/AC）的溯源
- 对 `core/`、`state/` 的任何「顺手修改」都违反本特性 additive 承诺——发现缺口回写 contracts §6 并走澄清
- 每任务完成即跑对应测试文件；每个 Checkpoint 跑 `tests/ui/` 全套防回退
- `reflex run` 手动验收仅限最终 quickstart §4 清单，CI 内全部无浏览器
