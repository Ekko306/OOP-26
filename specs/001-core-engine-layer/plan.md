# Implementation Plan: PyLightroom 核心引擎层（Core）

**Branch**: `001-core-engine-layer` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-core-engine-layer/spec.md`

## Summary

实现 PyLightroom 的核心引擎层：纯 Python、零界面框架依赖的图像处理引擎。提供 8 类调整策略族（亮度/对比度/饱和度/锐度/色温/裁剪/旋转/直方图均衡）、多格式图像资产族（JPEG/PNG/BMP/WebP + RAW，主验收 .ARW）、非破坏性编辑会话（指令栈 + 撤销/重做 + 同类合并）、Sidecar 持久化（`photo.jpg` → `photo.json`）、三级预览渲染管线（低分先行，只验顺序性）、导出（JPEG/PNG）、RGB 直方图统计与窄回调事件协议。架构遵循准则：继承建两棵抽象族谱，组合搭运行期结构，双工厂支撑开闭扩展。

## Technical Context

**Language/Version**: Python 3.11+（Pillow/OpenCV/rawpy 均有稳定 wheel；与未来 Reflex 集成兼容）

**Primary Dependencies**: Pillow（I/O、几何变换、ImageEnhance）、OpenCV（色温矩阵、CLAHE 直方图均衡）、rawpy（RAW 解码）、numpy（数组中介）

**Storage**: 文件系统——原图只读；编辑状态存 JSON Sidecar（同主名换扩展名：`photo.jpg` → `photo.json`）；预览缓存写 `assets/` 目录

**Testing**: pytest（纯命令行，无浏览器、无网络）

**Target Platform**: 本地桌面（Windows 优先），命令行可独立运行验证

**Project Type**: library（核心引擎库；本特性不包含 state/ui 层与 rxconfig）

**Performance Goals**: 低分预览先行可用、全图随后替换（只验收顺序性与无全图级阻塞，不设硬性时间指标——见 Clarifications Q3）

**Constraints**: `core/` 零界面框架引用（grep 断言红线）；参数统一 0.0–2.0 浮点因子刻度、1.0 中性（几何参数按自然单位）；原图像素永不写入；导出失败不留半成品

**Scale/Scope**: 8 类调整 + 5 种格式 + 8 个核心模块 + 单元测试全套；单用户本地场景

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 准则原则 | 门禁检查 | 状态 |
| -------- | -------- | ---- |
| I. UI 与逻辑严格分离 | 本特性只创建 `core/`；全部代码无任何界面框架 import；CI grep 断言随 M4 落地，本阶段以本地 grep 验证 | ✅ PASS |
| II. 继承立抽象，组合建运行 | 调整族/资产族用继承（抽象基类只定契约）；会话/处理器/撤销栈/导出器全部组合 | ✅ PASS |
| III. 非破坏性编辑契约 | 调整只追加指令对象；渲染时顺序应用；Sidecar 只存指令序列；原图文件永不写入 | ✅ PASS |
| IV. 开闭原则 | AdjustmentFactory/AssetFactory 注册制；上层仅依赖抽象基类；SC-006 插件演示为验收项 | ✅ PASS |
| V. 引擎独立可测，测试先行 | pytest 全套无浏览器/网络依赖；引擎先于 UI 成型（本特性即 M1–M3） | ✅ PASS |

**Post-design re-check（Phase 1 完成后）**: 设计工件未引入任何界面框架依赖、未修改抽象契约方向、持久化协议符合非破坏约束、工厂注册制保持、测试计划独立可跑 —— 全部门禁维持 ✅ PASS，无 Complexity Tracking 事项。

## Project Structure

### Documentation (this feature)

```text
specs/001-core-engine-layer/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出：技术决策与依据
├── data-model.md        # Phase 1 输出：实体、字段、状态转换
├── quickstart.md        # Phase 1 输出：端到端验证指南
├── contracts/           # Phase 1 输出：引擎公共 API 契约 + Sidecar Schema
│   ├── core-api.md
│   └── sidecar-schema.md
└── tasks.md             # Phase 2 输出（/speckit-tasks 生成，本命令不创建）
```

### Source Code (repository root)

```text
pylightroom/
├── core/                    # 【核心引擎层】纯 Python，零界面框架依赖
│   ├── __init__.py
│   ├── adjustments/
│   │   ├── __init__.py
│   │   ├── base.py          # BaseAdjustment 抽象基类（契约 + 序列化模板方法 + merge）
│   │   ├── basic.py         # 亮度/对比度/饱和度/锐度策略（Pillow ImageEnhance）
│   │   ├── color.py         # 色温/直方图均衡策略（OpenCV）
│   │   ├── geometry.py      # 裁剪/旋转策略（Pillow）
│   │   └── factory.py       # AdjustmentFactory（按类型标识反射创建）
│   ├── assets/
│   │   ├── __init__.py
│   │   ├── base.py          # BaseImageAsset 抽象基类（load 模板方法 + 多级预览）
│   │   ├── raster.py        # Jpeg/Png/Bmp/WebP 资产
│   │   ├── raw.py           # RawAsset（rawpy 解码 → 统一内存表示）
│   │   └── factory.py       # AssetFactory（按扩展名分发）
│   ├── pipeline.py          # ImageProcessor（门面）、PreviewCache（三级分辨率 + 版本号失效）
│   ├── history.py           # EditSession、撤销/重做历史（同类入栈合并）
│   ├── persistence.py       # SidecarFile 读写（JSON 协议 v1）
│   ├── exporter.py          # Exporter（全图渲染 → 成品 + Sidecar；失败无半成品）
│   ├── histogram.py         # HistogramCalculator（RGB 三通道 256 bin）
│   └── events.py            # 回调协议（进度/完成/错误，引擎唯一通知出口）
tests/
├── adjustments/             # 8 类调整：应用正确性、参数校验、序列化往返、合并
├── assets/                  # 五格式加载、元数据、多级预览、解码失败路径
├── history/                 # 撤销/重做模型、合并、清空重做等边界
├── pipeline/                # 空栈渲染=原图、版本号失效、低分先行顺序性
├── persistence/             # Sidecar 往返、损坏文件、未知类型
└── exporter/                # 导出一致性、失败无半成品
requirements.txt             # pillow, opencv-python, rawpy, numpy, pytest（版本锁定）
```

**Structure Decision**: 采用设计文档 §7 的单库布局，本特性只交付 `pylightroom/core/` 与 `tests/`；`state/`、`ui/`、`rxconfig.py` 属后续 M4 特性，此处不创建。`tests/` 按核心模块分目录，全部可在无浏览器命令行环境运行。

## Complexity Tracking

> Constitution Check 全部通过，无违规事项，本表留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| （无） | — | — |
