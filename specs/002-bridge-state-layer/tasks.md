---

description: "Task list for feature 002-bridge-state-layer"
---

# Tasks: PyLightroom 桥接层（State）

**Input**: Design documents from `/specs/002-bridge-state-layer/`

**Prerequisites**: plan.md、spec.md、research.md（D1–D7 决策）、data-model.md、contracts/state-api.md、quickstart.md

**Tests**: 已请求 TDD（宪法准则 V「测试先行」+ FR-017/SC-006）。全部测试任务先写先失败，再实现转绿；全程无浏览器。

**Organization**: 按用户故事分组。Phase 2 为纯 Python 胶水核心（引擎增量 + presenter + session），是全部 US 的共同地基。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 不同文件、无未完成依赖，可并行
- **[Story]**: US1–US5（对应 spec.md 用户故事）
- 环境注意：Windows 下统一 `$env:PYTHONUTF8='1'`；测试命令 `uv run pytest tests/state/ -v`

## Path Conventions

```text
pylightroom/core/    # 引擎层（仅 Phase 2 的 3 处 additive 变更）
pylightroom/state/   # 桥接层主体（本特性）
tests/state/         # 桥接层测试（无浏览器）
scripts/             # 冒烟脚本
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 依赖就位与目录骨架

- [X] T001 安装 Reflex 并固化版本：`uv pip install reflex`，把解析到的版本以 `reflex==<version>` 写入 [requirements.txt](d:/projects/syp/OOP-26/requirements.txt)；验证 `uv run python -c "import reflex; print(reflex.__version__)"` 成功
- [X] T002 [P] 创建目录骨架：`pylightroom/state/`（含空 `__init__.py`）与 `tests/state/`（含空 `__init__.py` 或按 001 惯例无包文件则以 pytest 配置为准）；确认 `uv run pytest tests/ -q` 基线仍全绿

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 引擎增量（research D1/D2，additive 只读）与纯 Python 胶水核心（presenter/session）——全部 US 的地基，无浏览器可测

**⚠️ CRITICAL**: 未完成本阶段不得开始任何 US

### 引擎增量（TDD）

- [X] T003 编写引擎增量测试 [tests/state/test_engine_additions.py](d:/projects/syp/OOP-26/tests/state/test_engine_additions.py)（先失败）：
  - `current_params`：未打开图片返回 `{}`；单指令返回其参数；同段同类合并后取合并值；`brightness→contrast→brightness` 多段同名取栈顶；`undo` 后消失、`redo` 后恢复
  - `registered_schemas`：含全部已注册调整名；每项形如 `{param: {"min","max","default"}}`；返回深拷贝（外部修改不影响注册表）
  - 红线自检语义（D2）：进程内先存在假 `reflex` 模块再导入 `pylightroom.core` → 正常不炸；core 导入链**新**引入假 `reflex`（临时在 core 子模块注入 `import reflex` 后 reload 验证或以 sys.modules 差集可观测的等价手段）→ 抛 `EngineError`
- [X] T004 实现引擎三处增量使 T003 全绿：[pipeline.py](d:/projects/syp/OOP-26/pylightroom/core/pipeline.py) `ImageProcessor.current_params()`（自栈顶向下反向扫描，首次命中生效，纯只读）；[factory.py](d:/projects/syp/OOP-26/pylightroom/core/adjustments/factory.py) `AdjustmentFactory.registered_schemas()`（deepcopy）；[__init__.py](d:/projects/syp/OOP-26/pylightroom/core/__init__.py) `_check_no_ui_framework` 改为「core 导入链增量检测」（急切导入与 `__getattr__` 惰性导入都做 sys.modules 前后差集；仅差集中新出现 reflex 才抛 `EngineError`）。**不得改动既有签名与行为**

### Presenter 与组合根（TDD）

- [X] T005 [P] 编写 presenter 测试 [tests/state/test_presenter.py](d:/projects/syp/OOP-26/tests/state/test_presenter.py)（先失败）：直接同步调用回调方法模拟引擎线程——
  - `on_render_complete`：thumb/medium/full 各级独立存储；`preview-thumb-v2` 不覆盖 v3（新者胜）；同级更高版本覆盖
  - data URL：字节即时编码为 `data:image/png;base64,...` 形态
  - `on_progress`：`busy=True`；对应 version 的 full 级 `on_render_complete`/`on_error` 后 `busy=False`
  - `on_error`：消息入错误通道；新 version 错误覆盖旧错误
  - `wait_for("full", version, timeout)`：Condition 有界等待命中/超时两分支（超时用极小 timeout 验证）
  - `reset()`：全部结果/错误清空
  - 无法解析的 task_id：仅记录错误消息，不影响结果容器
- [X] T006 实现 [presenter.py](d:/projects/syp/OOP-26/pylightroom/state/presenter.py) 使 T005 全绿：内部类 `Presenter` 实现 `EngineEvents` 协议；`threading.Condition` + 加锁结果字典；`latest(level)` / `wait_for(level, version, timeout)` / `reset()` / `busy`；**纯 Python，仅 import `pylightroom.core` 与标准库**
- [X] T007 [P] 实现 [session.py](d:/projects/syp/OOP-26/pylightroom/state/session.py) 组合根：`get_session()` 返回组合对象（持 `ImageProcessor(presenter)` 与 presenter 引用）；`set_session()` 供测试注入替身；单会话语义

**Checkpoint**: `uv run pytest tests/state/test_engine_additions.py tests/state/test_presenter.py -v` 全绿；引擎全量回归 `uv run pytest tests/ -q` 仍全绿

---

## Phase 3: User Story 1 - 打开照片后界面呈现可编辑视图 (Priority: P1) 🎯 MVP

**Goal**: 界面层经桥接层即可让用户看到预览（低分先行）、RGB 直方图、就绪滑块与文件名；失败路径可读且状态保持

**Independent Test**: 直接实例化 FileState、注入真实引擎 + 临时 PNG，调用 `open_file`，断言渐进回写与错误隔离；无需其余故事

### Tests for User Story 1 ⚠️ 先失败

- [X] T008 [P] [US1] 编写 [tests/state/test_file_state.py](d:/projects/syp/OOP-26/tests/state/test_file_state.py) 打开链路用例：
  - 成功：`file_name`/`has_image=True`；`preview_data_url` 先 thumb 后 full（渐进，借 presenter.wait_for 语义）；`histogram` 三通道各 256 bin 且与图内容一致；`adjustment_schemas` 来自 `registered_schemas()`；`adjustment_values` 全部为 schema 默认值
  - 失败：不支持格式/损坏文件 → `error_message` 非空可读、`has_image`/预览等既有状态不变、状态层无未捕获异常
  - 重复打开：状态重置干净（FR-002）

### Implementation for User Story 1

- [X] T009 [US1] 实现 [develop_state.py](d:/projects/syp/OOP-26/pylightroom/state/develop_state.py)：`DevelopState(rx.State)`——按 data-model §2 声明全部 vars 与初值；私有渐进回写辅助（取 presenter 最新帧 → 写 vars → yield；直方图经 `HistogramCalculator.compute(session.render("thumb"))` 获取，D7）；**处理器只做三动作**
- [X] T010 [US1] 实现 [file_state.py](d:/projects/syp/OOP-26/pylightroom/state/file_state.py)：`FileState(DevelopState)`——vars（file_name/has_image/exporting/export_message，data-model §3）与 `open_file(path)` 三动作：参数转换 → `session.open`（异常落 error_message）→ presenter.reset + 渐进回写
- [X] T011 [US1] 完善 [state/\_\_init\_\_.py](d:/projects/syp/OOP-26/pylightroom/state/__init__.py)：公共导出面（`DevelopState`/`FileState` 等，PEP 562 与 001 风格一致）；模块 docstring 声明「本层是唯一同时 import Reflex 与 core 的层」

**Checkpoint**: `uv run pytest tests/state/test_file_state.py -v` 全绿 → US1 可独立验收（MVP）

---

## Phase 4: User Story 2 - 拖动滑块预览渐进即时更新 (Priority: P1)

**Goal**: 滑块事件 → 参数转发引擎 → 预览渐进回写（低分先行/高分替换/新者胜），忙碌标志与错误通道如实

**Independent Test**: 实例化 DevelopState + 真实引擎（先 open），模拟滑块事件与快速连发，断言版本新者胜与渐进时序

### Tests for User Story 2 ⚠️ 先失败

- [X] T012 [P] [US2] 编写 [tests/state/test_develop_state.py](d:/projects/syp/OOP-26/tests/state/test_develop_state.py) 调整链路用例：
  - `on_slider_change`：转发断言（引擎收到 `{"factor": value}`）；thumb 帧先行回写；`busy` 生命周期；高分（full）替换到位
  - 直方图随每次调整刷新（内容变化可观测）
  - 错误路径：引擎拒绝（越界参数经 `apply_adjustment` 注入）→ `error_message` 非空、预览保持最近有效帧
  - `apply_adjustment` 通用入口：params 字典透传（rotate 等几何调整）

### Implementation for User Story 2

- [X] T013 [US2] 实现 `DevelopState.on_slider_change` 与 `apply_adjustment`（[develop_state.py](d:/projects/syp/OOP-26/pylightroom/state/develop_state.py)）：三动作 + 渐进回写（research D4：`presenter.wait_for("full", version, 有界超时)` Condition 等待，非轮询）；超时降级保留低分帧、busy 按实况落定

**Checkpoint**: US1+US2 独立可验收；`uv run pytest tests/state/ -v` 全绿

---

## Phase 5: User Story 3 - 撤销/重做后界面与编辑状态一致 (Priority: P2)

**Goal**: undo/redo 后滑块值与预览和引擎指令栈 100% 一致；空栈可读提示

**Independent Test**: 实例化 State，执行「调整→撤销→调整→重做」序列，逐点断言 `adjustment_values` 与预览

### Tests for User Story 3 ⚠️ 先失败

- [X] T014 [P] [US3] 扩展 [tests/state/test_develop_state.py](d:/projects/syp/OOP-26/tests/state/test_develop_state.py) 撤销/重做用例：
  - undo 后：`adjustment_values` 与 `current_params()` 一致（被撤销名回补 schema 默认值，data-model §2）；预览回退
  - redo 后：值与预览前进一致
  - 空栈 undo/redo：`error_message` 可读提示、界面状态不变（HistoryError 转译）
  - 序列一致性：任意操作序列后 `adjustment_values` == 引擎 `current_params()` 缺省回补（SC-004）

### Implementation for User Story 3

- [X] T015 [US3] 实现 `DevelopState.undo` / `redo`（[develop_state.py](d:/projects/syp/OOP-26/pylightroom/state/develop_state.py)）：引擎调用 → `current_params()` 回写 `adjustment_values`（缺席名按 schema 默认值回补）→ 渐进回写预览/直方图

**Checkpoint**: US1–US3 全绿

---

## Phase 6: User Story 4 - 导出成品并获得进度与结果反馈 (Priority: P2)

**Goal**: 导出请求转发引擎，`exporting` 进度呈现与成功/失败可读反馈

**Independent Test**: 实例化 FileState（先 open 临时图），`export_file` 到临时目录，断言成品存在与消息回写

### Tests for User Story 4 ⚠️ 先失败

- [X] T016 [P] [US4] 扩展 [tests/state/test_file_state.py](d:/projects/syp/OOP-26/tests/state/test_file_state.py) 导出用例：
  - 成功：`exporting` 先 True 后 False；`export_message` 为成功路径；成品文件与 Sidecar 存在（引擎职责，断言产物即可）
  - 失败：不可写路径 → `export_message` 失败原因可读、无崩溃、无残留 `.tmp`（引擎保证）
  - 合法格式限定 jpeg/png 透传

### Implementation for User Story 4

- [X] T017 [US4] 实现 `FileState.export_file`（[file_state.py](d:/projects/syp/OOP-26/pylightroom/state/file_state.py)）：`exporting` 置位 → 转发引擎 `export`（同步）→ `export_message` 回写复位（三动作）

**Checkpoint**: US1–US4 全绿

---

## Phase 7: User Story 5 - 异常全程可读提示且界面零崩溃 (Priority: P3)

**Goal**: 引擎全部错误路径 100% 转可读消息，状态层零未捕获异常，错误后可继续操作

**Independent Test**: 参数化注入全部异常族与错误回调，逐路径断言 `error_message` 与状态完整性

### Tests for User Story 5 ⚠️ 先失败

- [X] T018 [P] [US5] 编写 [tests/state/test_error_isolation.py](d:/projects/syp/OOP-26/tests/state/test_error_isolation.py) 参数化用例：
  - 同步异常族：`AssetError`（open）、`AdjustmentError`（update）、`HistoryError`（undo/redo）、`ExportError`（export）→ 对应消息通道回写、无异常冒泡
  - 异步：`on_error` 回调直达 presenter 错误通道 → `error_message`
  - 恢复性：任意错误后继续正常操作（重新 open/调整）恢复正常；新成功操作清除旧 `error_message`（FR-013）

### Implementation for User Story 5

- [X] T019 [US5] 补齐错误隔离实现（[presenter.py](d:/projects/syp/OOP-26/pylightroom/state/presenter.py) 与两个 State 文件按 T018 缺口修补）：确保同步 `try/except EngineError` 与回调错误统一落通道、无未捕获异常路径

**Checkpoint**: 全部 US 完成；`uv run pytest tests/state/ -v` 全绿

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T020 架构红线测试 [tests/state/test_architecture.py](d:/projects/syp/OOP-26/tests/state/test_architecture.py)：以纯 Python 遍历源码断言——`core/` 零 `import reflex`；`reflex` 引用仅出现在 `state/`；`state/` 零 `PIL/cv2/rawpy` import（对应 quickstart §3，可进 CI）
- [X] T021 [P] 冒烟脚本 [scripts/demo_state.py](d:/projects/syp/OOP-26/scripts/demo_state.py)（quickstart §4 全步骤，输出 `SMOKE ALL PASS`）
- [X] T022 全量回归与验证记录：`uv run pytest tests/ -q` 全绿（含 001 回归）；架构断言通过；把测试计数与红线结果记入 [verification.md](d:/projects/syp/OOP-26/specs/002-bridge-state-layer/verification.md)
- [X] T023 同步本文件勾选与最终报告（对照 spec SC-001–SC-007 逐条给出达成证据）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1（Setup）**：无依赖，立即开始
- **Phase 2（Foundational）**：依赖 Phase 1（reflex 需就位以便后续 import 链验证；T003–T007 本身不 import reflex 的部分可与 T001 并行）——**阻断全部 US**
- **Phase 3–7（US）**：依赖 Phase 2；US1→US2→US3 依次扩展同一 State 文件（顺序执行）；US4 依赖 US1（file_state.py）；US5 依赖 US1–US4 的实现面
- **Phase 8（Polish）**：依赖全部 US

### User Story Dependencies

- **US1（P1，MVP）**：仅依赖 Phase 2
- **US2**：依赖 US1（需先有打开链路与 DevelopState 骨架）
- **US3**：依赖 US2（同文件扩展、依赖 current_params 增量）
- **US4**：依赖 US1（file_state.py 扩展；可与 US2/US3 并行开发但同文件无冲突）
- **US5**：依赖 US1–US4（汇总验证错误面）

### Within Each User Story

- 测试任务先写先失败 → 实现任务转绿 → Checkpoint 独立验收
- 渐进回写辅助（T009）先于依赖它的处理器（T010/T013/T015）

### Parallel Opportunities

- T001 与 T002 并行；T003/T005 并行（不同文件）
- T007（session.py）与 T005/T006 尾段可并行
- T012 与 T016 的测试编写可并行（不同文件）
- T020/T021 可并行

---

## Implementation Strategy

### MVP First（仅 US1）

1. Phase 1 + Phase 2 完成（地基：引擎增量 + presenter + session）
2. Phase 3（US1）→ 独立验收：打开链路全绿
3. **STOP and VALIDATE**：`uv run pytest tests/state/test_file_state.py -v`

### Incremental Delivery

- +US2 → 滑块渐进体验（核心交互）→ +US3 → 撤销闭环 → +US4 → 导出收口 → +US5 → 错误兜底 → Phase 8 红线与冒烟
- 每故事一个 Checkpoint，任意点可停

## Notes

- 引擎后台回调来自 daemon 线程：presenter 测试以同步注入模拟（加锁语义真实覆盖）
- 所有桥接层测试不启动浏览器/服务器（FR-017）；State 直接实例化调用处理器
- 不得在 state 层引入 Pillow/OpenCV/rawpy（D7）；不得修改 001 契约既有签名（additive only）
- 环境红线：Windows + `PYTHONUTF8=1`；命令一律 `uv run`

---

## Phase 9: Convergence

**Purpose**: speckit-converge 对照 spec/plan/tasks 与当前代码评估出的剩余工作（T001–T017 实现与测试已就位，US1–US4 全绿；以下为 US5 收尾与 Phase 8 收口）。

- [X] T024 修正 US5 异步错误用例并转绿 [tests/state/test_error_isolation.py](d:/projects/syp/OOP-26/tests/state/test_error_isolation.py)：`EditSession` 版本单调递增（undo/redo 也 +1），「回到旧版本号回显」假设不成立——以替身 `_FailingFullProcessor`（thumb 同步送达、full 级以 `on_error` 失败）断言同版本错误回显 `error_message` 且 busy 按实况解除；以真实引擎断言旧版本错误不随后续操作复现（wait_for 错误提前中断语义）per FR-012 / US5-AC2 (partial)
- [X] T025 编写架构红线测试 [tests/state/test_architecture.py](d:/projects/syp/OOP-26/tests/state/test_architecture.py)：纯 Python 遍历源码——`core/` 零 `import reflex`；`reflex` 引用仅出现在 `state/`；`state/` 零 `PIL/cv2/rawpy` import per FR-014 / SC-007 / T020 (missing)
- [X] T026 编写冒烟脚本 [scripts/demo_state.py](d:/projects/syp/OOP-26/scripts/demo_state.py)：quickstart §4 全步骤（打开 → 滑块 → 撤销/重做 → 导出 → 错误路径），输出 `SMOKE ALL PASS` per T021 / quickstart §4 (missing)
- [X] T027 全量回归与验证记录：`uv run pytest tests/ -q` 全绿（含 001 回归）+ 架构断言通过，测试计数与红线结果记入 [verification.md](d:/projects/syp/OOP-26/specs/002-bridge-state-layer/verification.md) per T022 / SC-006 (missing)
- [X] T028 同步 tasks.md 勾选（T008–T019 及本阶段）并出最终报告：对照 SC-001–SC-007 逐条给出达成证据 per T023 (partial)
- [X] T029 补记引擎计划内偏差至设计工件：[research.md](d:/projects/syp/OOP-26/specs/002-bridge-state-layer/research.md) 新增 D8（`refresh_previews` 公有方法，供 open 后渐进推送）与 D9（`_render_background` 会话身份快照 + 渲染后二次校验）；[contracts/state-api.md](d:/projects/syp/OOP-26/specs/002-bridge-state-layer/contracts/state-api.md) §3 补 refresh_previews 契约 per plan 决策补记 (partial)
