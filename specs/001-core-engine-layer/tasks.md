# Tasks: PyLightroom 核心引擎层（Core）

**Input**: Design documents from `/specs/001-core-engine-layer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/core-api.md, contracts/sidecar-schema.md

**Tests**: 规格明确要求引擎独立可测（SC-007、准则 V），每个用户故事先写测试（须先失败）再实现。

**Organization**: 按用户故事分组；故事内遵循「测试 → 抽象/模型 → 服务 → 集成」顺序。公共契约与异常体系是全部故事的阻塞前置，置于 Phase 2。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1–US5，对应 spec.md）
- 所有路径为仓库根相对路径

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 项目初始化与测试基座

- [X] T001 按计划创建包骨架：`pylightroom/core/`（含 `adjustments/`、`assets/` 子包）与 `tests/`（`adjustments/`、`assets/`、`history/`、`persistence/`、`pipeline/`、`exporter/` 子目录），各目录含 `__init__.py`
- [X] T002 创建 `requirements.txt`：pillow、opencv-python、rawpy、numpy、pytest（锁定版本号），并用 `uv pip install -r requirements.txt` 验证安装成功（环境不得安装 reflex）
- [X] T003 [P] 配置 pytest（`pyproject.toml` 的 `[tool.pytest.ini_options]`：testpaths=tests、UTF-8 输出）
- [X] T004 [P] 在 `tests/conftest.py` 提供测试夹具：程序化生成小尺寸 RGB/JPEG/PNG/BMP/WebP 样图（pytest tmp_path），以及简易像素断言助手（均值/亮度比较）；RAW 样片路径夹具（无样片时 skip）

**Checkpoint**: `uv run pytest tests/ -v` 可运行（收集 0 或仅 skip），依赖就绪

---

## Phase 2: Foundational（阻塞前置）

**Purpose**: 全部用户故事依赖的异常体系与事件协议

**⚠️ CRITICAL**: 未完成本阶段，任何用户故事不得开始

- [X] T005 [P] 实现 `pylightroom/core/errors.py`：五类异常 `AssetError`/`AdjustmentError`/`HistoryError`/`SidecarError`/`ExportError`（均继承公共基类 `EngineError`），触发条件遵循 contracts/core-api.md §7（含路径与原因字段）
- [X] T006 [P] 实现 `pylightroom/core/events.py`：`EngineEvents` 协议（`on_progress(task_id, stage, fraction)` / `on_render_complete(task_id, image_bytes)` / `on_error(task_id, message)`），仅消息对象、无框架类型（contracts/core-api.md §6）
- [X] T007 创建 `pylightroom/core/__init__.py` 公共导出面：仅导出契约中的名称（ImageProcessor、双工厂、异常、事件协议），并实现红线自检钩子（模块导入不含 reflex）

**Checkpoint**: 基础设施就绪，用户故事可开始

---

## Phase 3: User Story 1 — 对图片应用基础调整并出图 (Priority: P1) 🎯 MVP

**Goal**: 8 类调整策略族落地：可执行、可校验、可序列化、可合并，经工厂按名创建（继承体系一，里程碑 M1）

**Independent Test**: 程序化构造 Pillow 图像 → 应用各策略 → 断言输出像素/序列化往返/合并语义；无需资产加载与会话

### Tests for User Story 1 ⚠️（先写，确认失败）

- [X] T008 [P] [US1] 编写 `tests/adjustments/test_basic.py`：亮度/对比度/饱和度/锐度四策略——factor=1.0 输出与原图一致、factor 增大方向正确、越界参数抛 AdjustmentError、serialize→deserialize→apply 像素一致、merge 后值覆盖（FR-002/003/004，SC-002）
- [X] T009 [P] [US1] 编写 `tests/adjustments/test_color.py`：色温 factor>1 偏暖（R 通道均值上升/B 下降）、factor<1 偏冷；直方图均衡 factor=1.0 不启用、factor>1 对比度增强且 R/G/B 色相比例不被破坏（仅亮度通道，FR-005）
- [X] T010 [P] [US1] 编写 `tests/adjustments/test_geometry.py`：裁剪 box 合法执行、越界/宽高≤0 抛 AdjustmentError；rotate 正值顺时针、任意角度（含 45°）画布尺寸正确
- [X] T011 [P] [US1] 编写 `tests/adjustments/test_factory.py`：按注册名创建各类实例；未注册名抛 AdjustmentError(unknown type)；param_schema 暴露键名/范围/默认值（FR-006）

### Implementation for User Story 1

- [X] T012 [US1] 实现 `pylightroom/core/adjustments/base.py`：`BaseAdjustment` 抽象基类——`name`/`param_schema` 类属性、`apply` 抽象方法、`validate`（依 param_schema，越界抛 AdjustmentError）、`serialize`/`deserialize` 模板方法（输出 `{"type", "params"}`）、`merge` 虚方法（同类后值覆盖返回 True，否则 False）
- [X] T013 [P] [US1] 实现 `pylightroom/core/adjustments/basic.py`：四策略，factor 直通 Pillow ImageEnhance（0.0–2.0，1.0 中性，research D3）
- [X] T014 [P] [US1] 实现 `pylightroom/core/adjustments/color.py`：`TemperatureAdjustment`（OpenCV BGR 增益映射，>1 暖 <1 冷）+ `HistogramEqualizationAdjustment`（转 YCrCb → 仅 L 通道 CLAHE，clipLimit 由 factor 映射 → 转回；禁止 RGB 分通道）
- [X] T015 [P] [US1] 实现 `pylightroom/core/adjustments/geometry.py`：`CropAdjustment`（box 校验：图界内且宽高>0）+ `RotateAdjustment`（角度正值顺时针，expand 语义）
- [X] T016 [US1] 实现 `pylightroom/core/adjustments/factory.py`：`AdjustmentFactory`（`create(type_name, params)` 反射创建 + `register(cls)` 注册扩展点；未注册抛 AdjustmentError）；注册全部 8 类
- [X] T017 [US1] 运行 T008–T011 全绿（`uv run pytest tests/adjustments -v`）

**Checkpoint**: US1 独立可验证——命令行环境对构造图像应用任意已注册调整并出图（M1 达成）

---

## Phase 4: User Story 2 — 非破坏性会话与撤销/重做 (Priority: P1)

**Goal**: EditSession 有序指令栈 + 撤销/重做 + 入栈同类合并 + 版本号（命令模式，里程碑 M2 核心）

**Independent Test**: 构造会话对象、注入 T016 工厂创建的策略，验证追加/合并/撤销/重做/清空重做全序列状态

### Tests for User Story 2 ⚠️

- [X] T018 [P] [US2] 编写 `tests/history/test_session.py`：追加有序、栈顶同类合并（version 仍自增）、不同类不合并；undo/redo 状态序列（FR-013/FR-015）；空栈 undo 与空 redo 栈 redo 抛 HistoryError；撤销后追加清空 redo（FR-014）；每次变更 version 递增（FR-017 前置）；指令对象为追加式、无原图引用修改（FR-012）

### Implementation for User Story 2

- [X] T019 [US2] 实现 `pylightroom/core/history.py`：`EditSession`——`image_path` 属性（open 时注入，Sidecar 推导与 JSON image_path 的来源，data-model §3）、`instructions` 有序列表、`append(adjustment)`（栈顶同类可合并则 merge，否则入栈并清空 redo）、`undo()`/`redo()`（双栈迁移、边界抛 HistoryError）、`version` 属性自增；不含任何图像处理逻辑
- [X] T020 [US2] 运行 T018 全绿（`uv run pytest tests/history -v`）

**Checkpoint**: US1+US2 均独立可测（M2 核心：命令模式 + 组合落地）

---

## Phase 5: User Story 3 — 多格式图片统一加载 (Priority: P2)

**Goal**: 资产族落地：五格式解码为统一内存表示 + 三级预览 + 双工厂开闭扩展（里程碑 M3）

**Independent Test**: 各格式样图经 AssetFactory 加载 → 统一 Pillow RGB 表示 + 元数据 + 三级预览；RAW 失败路径抛格式化异常

### Tests for User Story 3 ⚠️

- [X] T021 [P] [US3] 编写 `tests/assets/test_raster.py`：JPEG/PNG/BMP/WebP 各夹具经 `AssetFactory.create(path)` 加载 → 返回统一 RGB 表示（PNG 透明通道合成白底）、exif/format/path 元数据存在、不支持扩展名抛 AssetError(unsupported format)、损坏文件抛 AssetError 含路径与原因（FR-007/008/011）
- [X] T022 [P] [US3] 编写 `tests/assets/test_raw.py`：有 .ARW 样片时——RawAsset 加载输出与 JpegAsset 走同一后续调整管线（同调整同结果类型，FR-007/008）；无样片或解码失败构造 → AssetError 含路径与原因、无半初始化对象残留（FR-011）
- [X] T023 [P] [US3] 编写 `tests/assets/test_preview.py`：`thumbnail()` 返回 thumb/medium/full 三级且尺寸递增（FR-010，research D5 分辨率约定）

### Implementation for User Story 3

- [X] T024 [US3] 实现 `pylightroom/core/assets/base.py`：`BaseImageAsset` 抽象基类——`load()` 模板方法（统一异常包装为 AssetError + 结果缓存）、`_decode()` 抽象、`exif/path/format` 属性、`thumbnail()` 三级预览（256px/1024px/全图）
- [X] T025 [P] [US3] 实现 `pylightroom/core/assets/raster.py`：Jpeg/Png/Bmp/WebP 资产（PngAsset 透明通道合成白底，依据契约 core-api.md §4）
- [X] T026 [P] [US3] 实现 `pylightroom/core/assets/raw.py`：RawAsset（rawpy.imread → postprocess(use_camera_wb=True) → 8bit RGB numpy → Pillow RGB；失败抛 AssetError 含路径与原因，research D4）
- [X] T027 [US3] 实现 `pylightroom/core/assets/factory.py`：`AssetFactory`（扩展名→类注册表，`create(path)`/`register(extensions, cls)`；.jpg/.jpeg/.png/.bmp/.webp/.arw 内置注册）
- [X] T028 [US3] 运行 T021–T023 全绿（`uv run pytest tests/assets -v`）

**Checkpoint**: US1+US2+US3 独立可用；RAW 与 JPEG 同管线（M3 达成）

---

## Phase 6: User Story 4 — 编辑状态持久化与恢复 (Priority: P2)

**Goal**: Sidecar JSON v1 协议：保存/加载往返无损、损坏与未知类型显式报错、原子写

**Independent Test**: 会话（注入 US1 策略）→ save → 新会话 load → 指令栈逐条一致；破坏 JSON/注入未知 type → SidecarError

### Tests for User Story 4 ⚠️

- [X] T029 [P] [US4] 编写 `tests/persistence/test_sidecar.py`：`sidecar_path_for("photo.jpg")=="photo.json"`（同主名换扩展名，Q4）；save→load 往返后逐条 type+params 一致（SC-002/FR-021/FR-022）；含未知 type 抛 SidecarError 不静默丢弃；损坏 JSON 抛 SidecarError；更高 version 拒绝（sidecar-schema）；写文件为原子语义（实现审查 + 异常注入验证无残留临时文件，FR-020/D9）

### Implementation for User Story 4

- [X] T030 [US4] 实现 `pylightroom/core/persistence.py`：`SidecarFile`——`sidecar_path_for`、`save(session)`（Sidecar 路径与 JSON image_path 取自 `session.image_path`，为 None 时抛 SidecarError；构造 v1 JSON：instructions 逐条 serialize + image_path + version；写临时文件后 `os.replace` 原子落盘）、`load(image_path, session)`（清空会话 → 逐条 `AdjustmentFactory.create` 重建；任一失败则整体失败、会话保持原状）
- [X] T031 [US4] 运行 T029 全绿（`uv run pytest tests/persistence -v`）

**Checkpoint**: 「重开不丢失」闭环（M2 序列化部分达成）

---

## Phase 7: User Story 5 — 渲染管线、导出、直方图与事件 (Priority: P3)

**Goal**: ImageProcessor 门面整合全部组件 + PreviewCache 三级缓存（低分先行）+ Exporter 原子导出 + HistogramCalculator

**Independent Test**: 门面 open→update→undo→export 全流程；空栈渲染=原图；版本号失效；低分先于高分回调到达；导出失败无半成品

### Tests for User Story 5 ⚠️

- [X] T032 [P] [US5] 编写 `tests/pipeline/test_processor.py`：open 样图 → update_adjustment（未注册名/越界参数抛 AdjustmentError）→ render("full") 空栈=原图（FR-016）；undo/redo 经门面可用；指令栈版本不匹配时缓存失效重渲染（FR-017，可用 mock 回调计数验证）；低分预览回调先于全图回调到达（SC-005 顺序性，Q3：无硬性时间指标）；回调未注入时静默不报错（FR-024）
- [X] T033 [P] [US5] 编写 `tests/exporter/test_export.py`：含多条指令会话导出 PNG/JPEG → 成品像素=逐条手工应用结果（SC-004）；原图关联 Sidecar 写出（如 sample.jpg → sample.json）且成品名 Sidecar 不存在（FR-019/FR-021）；导出目标不可写（异常注入）→ ExportError 且无半成品文件、无临时文件残留（FR-020）
- [X] T034 [P] [US5] 编写 `tests/pipeline/test_histogram.py`：纯色图三通道峰值位置正确、计数总和=像素数×3；输出格式 `{"r","g","b"}` 各 256 长度（FR-023，D6）

### Implementation for User Story 5

- [X] T035 [P] [US5] 实现 `pylightroom/core/histogram.py`：`HistogramCalculator.compute(image)` → Pillow `histogram()` 拆分 RGB 三通道各 256 bin
- [X] T036 [P] [US5] 实现 `pylightroom/core/pipeline.py` 的 `PreviewCache`：键=(session.version, level)，三级分辨率，版本不匹配即失效
- [X] T037 [US5] 实现 `pylightroom/core/pipeline.py` 的 `ImageProcessor` 门面：组合 AssetFactory 产物 + EditSession + PreviewCache + EngineEvents；`open`/`update_adjustment`（validate→append→低分同步重渲染→高分后台线程补齐→on_render_complete 回调）/`render(level)`（顺序应用指令链）/`undo`/`redo`/`export` 委托 Exporter；对外不暴露内部栈结构（contracts/core-api.md §1）
- [X] T038 [US5] 实现 `pylightroom/core/exporter.py`：`Exporter.export(processor, path, format)`——全图渲染 → 写临时文件 → `os.replace` 原子落盘 → `SidecarFile.save`（持久化到原图关联 Sidecar）；失败清理临时文件抛 ExportError（D9）
- [X] T039 [US5] 运行 T032–T034 全绿（`uv run pytest tests/pipeline tests/exporter -v`）

**Checkpoint**: 全部用户故事独立可用，「打开 → 调整 → 撤销/重做 → 保存/恢复 → 导出」闭环（M1–M3 全达成）

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T040 [P] 架构红线脚本：校验 `pylightroom/core/` 全部 .py 无 reflex 引用（对应 quickstart.md §2，输出 PASS 字样）
- [X] T041 [P] 开闭原则插件验证测试 `tests/adjustments/test_plugin.py`：测试内定义 `VignetteAdjustment` 子类 → 仅 `AdjustmentFactory.register()` → `create("vignette")` 可用；`git status` 确认存量文件零改动（SC-006，FR-026）
- [X] T042 运行 quickstart.md 全部验证步骤（§1–§5）并记录结果；`uv run pytest tests/ -v` 全绿（SC-001/SC-007）
- [X] T043 [P] 更新 `README.md`：引擎层使用示例（门面 API 摘引 contracts/core-api.md，不含实现细节）
- [X] T044 逐条评审 `specs/001-core-engine-layer/checklists/design-contract.md`（25 项）并勾选

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup（Phase 1）→ Foundational（Phase 2）→ US1（Phase 3）→ US2（Phase 4）→ US3（Phase 5）→ US4（Phase 6）→ US5（Phase 7）→ Polish（Phase 8）
- US2 依赖 US1 的策略与工厂（会话存指令对象）；US4 依赖 US1+US2（序列化会话）；US5 依赖 US1–US4 全部（门面整合）
- 严格串行即可满足课程里程碑 M1→M2→M3 顺序（准则 V：引擎先于 UI，M4 不在本特性）

### Within Each User Story

- 测试任务（T008–T011、T018、T021–T023、T029、T032–T034）先写且先失败，再实现
- 抽象基类 → 具体子类 → 工厂 →（US5）门面整合

### Parallel Opportunities

- 各 [P] 测试任务可并行编写（不同文件）
- US1 内 basic/color/geometry 三策略实现（T013–T015）可并行
- US3 内 raster/raw 实现（T025–T026）可并行
- US5 内 histogram/PreviewCache（T035–T036）可并行

---

## Implementation Strategy

### MVP First（US1 完成即可演示）

1. Phase 1–2 → 基座就绪
2. Phase 3（US1）→ **STOP**：命令行应用 8 类调整出图（M1 里程碑验收）
3. 后续按序推进，每个 Checkpoint 独立验证

### Incremental Delivery

- US1 = 策略族出图；+US2 = 可撤销的非破坏会话；+US3 = 五格式统一管线；+US4 = 状态恢复闭环；+US5 = 门面全流程
- 每阶段对应设计文档里程碑 M1–M3 与准则验收点，避免工期超支时架构受损（功能裁剪顺序见准则）

## Notes

- 提交策略：每任务或逻辑组完成后 commit（信息格式 `feat(core): ...`）
- 测试断言基线全部来自 contracts/ 与 data-model.md 的量化约束，实现不得私自调整刻度/命名/异常语义
- RAW 测试依赖样片，缺失时对应用例 skip 而非失败

---

## Phase 9: Convergence

- [ ] T045 提供 .ARW 主验收样片（环境变量 `PYLIGHTROOM_ARW_SAMPLE` 指向真实样片）并运行 `tests/assets/test_raw.py`，使 RAW 加载与「同管线」断言真实执行（当前 2 用例 skip，「MUST 验证通过」未落地）per FR-007/SC-004 (partial)
- [X] T046 使 quickstart §3 验证命令可直接运行：pyproject.toml `[tool.pytest.ini_options]` 增加 `pythonpath = ["."]`（或等效手段），验证 `uv run pytest tests/ -v` 全绿（当前实测 13 个收集错误 ModuleNotFoundError: pylightroom，README 仅以 `python -m pytest` 变通）per T003/quickstart §3/SC-007 (partial)
- [X] T047 按 quickstart §4 步骤 1–9 编写可复跑端到端脚本（如 `scripts/demo.py`），在纯净命令行环境执行 §1–§5 全部验证并将结果记录到 `specs/001-core-engine-layer/verification.md`（当前无脚本工件、无执行记录，T042 声明缺证据）per T042/SC-001/quickstart §4–§5 (partial)
- [ ] T048 按 tasks.md Notes 提交策略将现有实现分逻辑组提交（`feat(core): ...`），并补 `.gitignore` 忽略 `.screenshots/` 等本地工件；提交后重跑 `test_plugin.py::test_existing_files_untouched` 确认存量零改动断言在 core/ 被跟踪状态下仍通过（当前 core/ 全部 untracked，断言恒真，SC-006 无法实证）per SC-006/FR-026 (partial)
- [X] T049 补充极大分辨率边界测试：程序化构造约 8000×6000 样图，验证加载、三级预览、导出可完成且低分预览先行不被全图渲染阻塞（当前最大样图仅 2048×1024）per Spec Edge Cases/FR-018 (missing)
- [X] T050 在 AssetFactory 为 RawAsset 注册其余常见 RAW 扩展名（.cr2/.nef，可选 .dng/.orf/.rw2/.raf），使「尽力支持」具备实际入口（当前直接抛 AssetError(unsupported format)；rawpy/LibRaw 本身可解）per FR-007/contracts/core-api.md §4/research D4 (partial)
