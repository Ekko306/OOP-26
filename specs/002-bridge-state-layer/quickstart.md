# Quickstart: 桥接层（State）无浏览器验证

**Feature**: 002-bridge-state-layer | **Date**: 2026-11-09

前置：`uv` 环境、001 引擎已交付。全部验证均在命令行完成，无需浏览器。

## 1. 依赖安装

```powershell
$env:PYTHONUTF8='1'
uv pip install reflex        # 或 uv add reflex；版本解析后固化到 requirements.txt
uv pip list | Select-String reflex
```

## 2. 单元与集成测试（TDD 全绿即验收）

```powershell
uv run pytest tests/state/ -v          # 桥接层全部测试
uv run pytest tests/ -q                # 全量回归（含 001）必须全绿
```

覆盖点对应 spec：presenter 版本新者胜/忙碌/错误/等待（US2/US5）、引擎增量 current_params（US3 一致性）、State 三动作链路（US1–US4）、架构 grep 断言（FR-014）。

## 3. 架构红线断言（CI 可复制）

```powershell
# core 零 reflex import（必须零输出）
Get-ChildItem pylightroom/core -Recurse -Filter *.py | Select-String "import reflex|from reflex"
# reflex 仅出现在 state 层（必须零输出）
Get-ChildItem pylightroom -Recurse -Filter *.py | Select-String "reflex" | Where-Object { $_.Path -notmatch "\\state\\" }
# state 层零第三方图像库 import（必须零输出）
Get-ChildItem pylightroom/state -Filter *.py | Select-String "import PIL|import cv2|import rawpy"
```

## 4. 端到端冒烟（无浏览器，presenter + 真实引擎）

生成测试图后运行状态链路冒烟（实现阶段提供 `scripts/demo_state.py`）：

```powershell
uv run python scripts/demo_state.py    # 预期输出 SMOKE ALL PASS
```

冒烟步骤（脚本内断言）：注入临时 PNG → open_file 链路（预览 data URL、直方图 256 bin、默认值）→ on_slider_change（低分先行 → 后台高分替换 → 版本新者胜）→ undo（滑块值回退 + 预览回退）→ export_file（成品 + export_message 成功路径）→ 非法格式 open（error_message，状态保持）。

## 5. 已知环境注意

- Windows 控制台务必 `PYTHONUTF8=1`（中文断言消息）
- 引擎后台预览回调来自 daemon 线程：presenter 内已加锁，测试中可直接同步调用回调方法模拟
- `.ARW` RAW 样片缺失时相关用例按 001 约定 skip（T045 待用户提供路径）
