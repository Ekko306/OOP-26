# Quickstart: 表现层（UI）——单页编辑界面

**Feature**: 003-ui-presentation-layer | **Date**: 2026-11-09

无浏览器自动化验证（准则 V）+ 浏览器手动验收清单（SC-001/SC-003 演示项）。所有命令在仓库根目录，Windows + `PYTHONUTF8=1`。

## §1 前置

- 002 已交付（桥接层 77 用例全绿）：`uv run pytest tests/state/ -q`
- requirements 已含 `reflex==0.10.1`

## §2 无浏览器验证（CI 可跑）

```powershell
# 1. UI 测试包（组件绑定 / 页面组装 / 上传导出链路 / 红线）
$env:PYTHONUTF8='1'; uv run pytest tests/ui/ -q

# 2. 全量回归（含 001 引擎 + 002 桥接层 + 003 UI）
$env:PYTHONUTF8='1'; uv run pytest tests/ -q

# 3. 架构红线（含 003 扩展：ui/ 零图像库、零引擎直引、组件零 state import）
$env:PYTHONUTF8='1'; uv run pytest tests/ui/test_architecture.py tests/state/test_architecture.py -q

# 4. 既有红线脚本复核
$env:PYTHONUTF8='1'; uv run python scripts/check_arch_redline.py

# 5. 桥接层冒烟不回退
$env:PYTHONUTF8='1'; uv run python scripts/demo_state.py
```

**预期**：全部 exit 0；全量 = 250 + 新增 UI 用例，0 failed（2 skipped 为 .ARW 样片，承 001-T045）。

## §3 无浏览器测试要点（实现依据）

- 组件：以示例 props 直接构造，断言组件树中关键 Var 的字符串形式（如含 `preview_data_url`、`on_slider_change`）——不启动浏览器
- 页面：断言六类组件齐备、`FileState`/`DevelopState` 的 vars 与处理器绑定存在
- 上传/导出链路：真实引擎 + 临时目录（复用 002 的 State 直接实例化模式），断言落盘 → `open_file` 可用、导出产物存在于 `output/` 拼接路径
- 红线：AST 静态断言（contracts/ui-api.md §5），不 import 被检模块

## §4 浏览器手动验收（SC-001/SC-003 演示清单）

```powershell
$env:PYTHONUTF8='1'; uv run reflex run    # 打开 http://localhost:3000
```

| # | 步骤 | 预期（对应验收） |
| ---- | ---- | ---- |
| 1 | 打开首页 | 单页三区布局（顶栏/左面板/中画布/右直方图），空态提示可见（FR-011） |
| 2 | 上传一张 PNG 样图 | 预览先低分后高分自动替换，直方图渲染，顶栏显示文件名（US1/AC1，SC-001 ≤3s） |
| 3 | 拖动亮度滑块 | 预览渐进更新、直方图刷新、滑块显示当前值（US2/AC1） |
| 4 | 快速连续拖动 | 终态收敛最后值，无中途残留（US2/AC2） |
| 5 | 角度输入 90 并应用 | 画布旋转，面板出现 rotate（D4）；面板无裁剪入口（Q1 结论） |
| 6 | 点击撤销 | 预览与滑块同步回退（US3/AC1）；无操作可撤时显示可读提示（US3/AC3） |
| 7 | 选择 jpeg 并导出 | 「导出中」→ 成功消息含完整路径，`output/` 出现 `<stem>_edited.jpg`（US4/AC1） |
| 8 | 上传损坏文件 | 错误横幅呈现可读原因，既有预览保持（US5/AC1）；下次成功操作清除旧错（US5/AC2） |
| 9 | 处理期间观察 | 忙碌指示可见，结束后消失（FR-010） |
| 10 | 刷新页面 | 回到干净空态，无报错（Edge Case） |

## §5 验证记录

实现完成后在 `verification.md` 记录：§2 各命令结果、§4 清单逐项勾选、SC-001–SC-007 证据（模板同 002）。
