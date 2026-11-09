# Quickstart: 核心引擎层端到端验证指南

**Feature**: 001-core-engine-layer | **Date**: 2026-11-09

本指南验证引擎在无浏览器、无界面框架的纯净命令行环境中完成全流程（SC-001）。实现完成后按顺序执行。

## 前置条件

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 已安装
- 测试样图：任一 JPEG（必需）；如验证 RAW 路径，另备一张 .ARW 样片
- 界面框架（reflex）**不得**安装在验证环境中（用于红线验证）

## 1. 环境准备

```powershell
uv venv
uv pip install -r requirements.txt
```

预期：依赖安装成功，`reflex` 不在依赖列表中。

## 2. 架构红线检查（准则 I）

```powershell
# core/ 内不得出现任何界面框架引用（无匹配 = 通过）
uv run python -c "from pathlib import Path; hits=[str(p) for p in Path('pylightroom/core').rglob('*.py') if 'reflex' in p.read_text(encoding='utf-8').lower()]; print(hits or 'PASS: core zero-reflex')"
```

预期输出：`PASS: core zero-reflex`

## 3. 单元测试

```powershell
uv run pytest tests/ -v
```

预期：全部通过（SC-007），无网络、无浏览器交互。

## 4. 端到端脚本验证

参考 [core-api.md](./contracts/core-api.md) 编写一次性脚本（或 `uv run python scripts/demo.py`，如 tasks 阶段提供），覆盖主流程：

1. **加载**：`ImageProcessor.open("sample.jpg")` → 无异常
2. **调整**：`update_adjustment("brightness", {"factor": 1.3})` → 低分预览先行回调到达，全图随后替换（SC-005 顺序性）
3. **合并**：再次 `update_adjustment("brightness", {"factor": 1.5})` → 会话指令数仍为 1，参数变为 1.5
4. **撤销/重做**：`undo()` 后栈空、渲染=原图；`redo()` 后恢复
5. **直方图**：`HistogramCalculator.compute(...)` → 返回 r/g/b 各 256 长度
6. **导出**：`export("out.png", "png")` → 生成 `out.png`，同时更新原图 Sidecar（`sample.json`，FR-019/FR-021）；成品目录不出现 `out.json`；渲染像素与逐条手工应用一致（SC-004 的一部分）
7. **恢复**：新会话 `open("sample.jpg")` + 加载 `sample.json` → 指令栈与保存前逐条一致（FR-022）
8. **RAW（可选）**：对 .ARW 样片重复 1–6 → 与 JPEG 走同一管线（FR-007/FR-008）
9. **异常路径**：不存在的调整名、越界参数、损坏的 JSON Sidecar → 各自抛出对应格式化异常，进程不崩溃

## 5. 开闭原则插件验证（SC-006）

在测试脚本中定义一个新调整子类（如「暗角」），仅调用 `AdjustmentFactory.register()` 注册后即可被 `update_adjustment` 使用，且全程不修改任何既有文件。

预期：注册即可用；`git diff` 显示存量代码零改动。

## 通过标准

- 第 2 节输出 PASS；第 3 节全绿；第 4 节九个步骤全部符合预期；第 5 节零存量改动
- 全程原始图片文件字节未变（可用前后哈希比对确认，对应 FR-012）
