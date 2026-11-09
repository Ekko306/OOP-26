# Verification: 桥接层（State）

**Feature**: 002-bridge-state-layer | **Date**: 2026-11-09

## 测试结果（Windows + `PYTHONUTF8=1`，命令一律 `uv run`）

| 范围 | 命令 | 结果 |
| ---- | ---- | ---- |
| 桥接层套件 | `uv run pytest tests/state/ -q` | **77 passed, 0 failed, 0 skipped** |
| 全量回归（含 001 引擎） | `uv run pytest tests/ -q` | **250 passed, 2 skipped, 0 failed**（skip 为 .ARW RAW 样片用例，样片待用户提供，001 T045 约定） |
| 端到端冒烟 | `uv run python scripts/demo_state.py` | **SMOKE ALL PASS**（6/6 步骤） |

### tests/state/ 用例分布

| 文件 | 覆盖 |
| ---- | ---- |
| test_engine_additions.py | 引擎增量：`current_params`、`registered_schemas`（深拷贝）、`refresh_previews`（D8）、红线自检导入链语义（D2） |
| test_presenter.py | Presenter：新者胜、data URL 编码、busy 四态、错误通道与 error_version、`wait_for` 五分支（含错误提前中断）、`reset` |
| test_file_state.py | US1 打开链路（渐进两帧、直方图 3×256、默认值、失败隔离、重开重置）+ US4 导出（成功产物/Sidecar、失败可读、无 .tmp 残留、非法格式拒绝） |
| test_develop_state.py | US2 滑块渐进（转发参数、thumb→full 时序、busy 生命周期、直方图刷新、快速连发收敛、超时降级保留低分帧）+ US3 撤销/重做（值与预览同步、默认回补、空栈提示、SC-004 序列一致性） |
| test_error_isolation.py | US5：同步异常族参数化（Asset/Adjustment/History/ExportError）、异步同版本错误回显、旧错不复现（版本门控）、恢复性 |
| test_architecture.py | 架构红线（AST 静态断言）：core/ 零 reflex；reflex 仅在 state/；state/ 零 PIL/cv2/rawpy |

## 架构红线结果（FR-014 / SC-007）

- `core/` 零 `import reflex`：**PASS**（test_core_never_imports_ui_framework）
- `reflex` 仅出现在 `state/`：**PASS**（test_reflex_confined_to_state_layer）
- `state/` 零 `PIL/cv2/rawpy`：**PASS**（test_state_has_no_heavy_image_libs）
- 既有脚本复核 `scripts/check_arch_redline.py`：**PASS**（无新增违例）

## 实现期计划内偏差（已补记工件）

- **D8**（research.md）：引擎新增 `ImageProcessor.refresh_previews()` additive 公有方法——001 的 `open()` 不产生预览事件，桥接层 open 成功后经此方法触发渐进推送
- **D9**（research.md）：`_render_background` 增加会话对象身份快照 + 渲染后二次校验——修复「重开图片版本归零，旧在途渲染污染新会话」竞态（spec Edge Case）
- 两处均为 additive，未改动 001 契约既有签名与语义；契约已同步至 contracts/state-api.md §3
- 001 回归测试修正一处：`tests/adjustments/test_plugin.py::test_existing_files_untouched` 由「git 工作区干净」断言改为「注册插件前后 core/ 源文件内容快照相等」——保留 FR-026 意图、去除对 git 状态的依赖（002 引擎增量属计划内 additive 变更）

## Success Criteria 达成证据

| SC | 证据 |
| ---- | ---- |
| SC-001 | `FileState`/`DevelopState` 全部处理器仅依赖桥接层；tests/state 各用例零引擎 API 直接调用（经 session 组合根） |
| SC-002 | test_file_state 渐进两帧断言 + test_develop_state thumb→full 时序断言；冒烟 [1/6] |
| SC-003 | test_rapid_updates_converge_to_latest（终态收敛最后值）+ presenter 新者胜测试；冒烟 [3/6] |
| SC-004 | test_sequence_consistency_sc004（任意序列后 values == current_params）；冒烟 [4/6] |
| SC-005 | test_error_isolation 全部路径 + 状态零未捕获异常（参数化 exhaust 不冒泡）；冒烟 [6/6] |
| SC-006 | 全量 250 passed（含 001 回归），无浏览器环境一次通过；桥接层测试不依赖界面组件代码 |
| SC-007 | test_architecture 三项 AST 断言通过（唯一例外层 = state/） |
