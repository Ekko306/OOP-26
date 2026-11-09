# Verification: 核心引擎层端到端验证记录

**Feature**: 001-core-engine-layer | **Date**: 2026-11-09 | **环境**: Windows / uv / Python ≥3.11

对应 quickstart.md §1–§5（任务 T047）。全部命令在仓库根以纯命令行执行，未启动任何 UI。

## §1 环境准备

- 依赖：`uv pip install -r requirements.txt` 已安装 pillow / opencv-python / rawpy / numpy / pytest（requirements.txt 锁定版本）
- 环境变量：Windows 控制台设置 `$env:PYTHONUTF8 = '1'` 保证 UTF-8 输出
- 红线前置：`uv run python -c "import reflex"` → `ModuleNotFoundError: No module named 'reflex'`（环境无界面框架依赖）✓

## §2 架构红线

```
$ uv run python scripts/check_arch_redline.py
PASS — pylightroom/core/ 共 19 个文件，零界面框架引用
```

## §3 单元测试

```
$ uv run pytest tests/ -q
........................................................................ [ 41%]
..................................ss.................................... [ 83%]
.............................                                            [100%]
```

**结果：171 passed, 2 skipped（0 failed）**。skip 的 2 例为 `tests/assets/test_raw.py` 的 .ARW 真机样片用例（按设计在无样片时 skip，样片接入见 T045 / 环境变量 `PYLIGHTROOM_ARW_SAMPLE`）。

测试覆盖：8 类调整策略、双工厂、EditSession、Sidecar 往返、管线/缓存/回调、导出、直方图、插件开闭、极大分辨率边界（≈8000×6000，T049）。

## §4 端到端脚本（`uv run python scripts/demo.py`）

```
工作目录: C:\Users\Administrator\AppData\Local\Temp\pylightroom-demo-0ftb7vf3
样图: sample.jpg 400x300 (JPEG)

[PASS] 1 加载 —— open(sample.jpg) 无异常，version=0
[PASS] 2 调整·低分先行 —— 回调顺序: preview-thumb → preview-medium → preview-full
[PASS] 3 同类合并 —— undo 一步即回原图（指令数=1）；redo 后与单独应用 1.5 像素一致
[PASS] 4 撤销/重做 —— undo→空栈=原图；空栈再 undo 抛 HistoryError；redo 恢复
[PASS] 5 直方图 —— r/g/b 各 256 bin，计数总和 = 400×300×3
[PASS] 6 导出+Sidecar —— out.png 生成、sample.json 更新、成品目录无 out.json、像素=逐条手工应用
[PASS] 7 会话恢复 —— 新会话加载 sample.json：type+params 逐条一致
[SKIP] 8 RAW 同管线 —— 未设置 PYLIGHTROOM_ARW_SAMPLE（见 T045）
[PASS] 9 异常路径 —— 未知调整名/越界参数 → AdjustmentError；损坏 JSON → SidecarError；进程未崩溃
[PASS] 10 插件注册（§5） —— VignetteAdjustment 定义于脚本内部，仅 register() 即可用于管线，存量文件零改动
[PASS] 11 原图不可变（FR-012） —— SHA-256 前后一致：原始图片文件字节未变

结果: 10 PASS / 1 SKIP / 0 FAIL
DEMO ALL PASS
```

## §5 开闭原则插件验证

- demo 步骤 10：脚本内部定义 `VignetteAdjustment` → `AdjustmentFactory.register()` → `update_adjustment("vignette", ...)` 即刻可用 ✓
- `tests/adjustments/test_plugin.py::test_existing_files_untouched` 在 §3 全量测试中通过 ✓
- git 跟踪基线下的零改动复验：随 T048 提交后重跑（见 tasks.md Phase 9 / T048）

## 结论

- SC-001（纯命令行全流程：打开 → 调整 → 撤销/重做 → 保存/恢复 → 导出）达成 ✓
- SC-005（低分预览先行、高分后台补齐、回调顺序正确）达成 ✓
- SC-007（测试全绿）达成：171 passed / 2 skipped ✓
- SC-004（.ARW 主验收）待 T045 提供真实样片后闭环；接入方式：`$env:PYLIGHTROOM_ARW_SAMPLE = '<样片路径>'` 后重跑 `uv run pytest tests/assets/test_raw.py -v` 与 demo
