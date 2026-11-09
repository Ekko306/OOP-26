# Phase 0 Research: PyLightroom 核心引擎层

**Feature**: 001-core-engine-layer | **Date**: 2026-11-09 | **Status**: Complete（无 NEEDS CLARIFICATION 遗留）

技术栈已由准则锁定（Reflex/Pillow/OpenCV/rawpy/JSON/pytest），本阶段任务是把规格决策落实到具体实现选型。逐项决策如下。

## D1: Python 版本与依赖管理

- **Decision**: Python 3.11+；依赖锁定在 `requirements.txt`（pillow、opencv-python、rawpy、numpy、pytest）
- **Rationale**: 三方库均有 3.11 稳定 wheel；3.11+ 性能与异常组特性有益；与未来 Reflex（要求 ≥3.9，推荐新版本）集成无冲突。用户偏好 uv，实际安装用 `uv pip install -r requirements.txt`。
- **Alternatives considered**: Python 3.12/3.13（rawpy 新版本 wheel 覆盖尚不保证全平台，保守取 3.11 下限）；conda 环境管理（与用户 uv 偏好不符）。

## D2: 统一内存图像表示

- **Decision**: 以 Pillow `Image`（RGB/A 模式）作为全引擎唯一内存表示；RAW 经 rawpy 解码为 numpy 数组后立即转为 Pillow 图像再进入管线
- **Rationale**: 调整算法主体在 Pillow（ImageEnhance/几何），单一表示使「图从哪来」对下游零感知（FR-008）；OpenCV 算法在策略内部临时转 numpy，转回后仍是 Pillow 图像，边界收敛在策略内部。
- **Alternatives considered**: 全程 numpy 数组（几何变换与 ImageEnhance 需重复封装，得不偿失）；自定义图像类（无收益，纯包装）。

## D3: 参数刻度与各类算法映射

- **Decision**: 对外统一 0.0–2.0 浮点因子、1.0 中性（Clarifications Q1）；各策略内部映射：
  - 亮度/对比度/饱和度/锐度：因子直通 Pillow ImageEnhance（其原生语义即 1.0 中性、0–2 有效）
  - 色温：因子映射到 BGR 增益偏移（>1 偏暖：增 R 减 B；<1 偏冷），OpenCV 矩阵实现
  - 直方图均衡：因子映射 CLAHE `clipLimit`（1.0=不启用，>1 逐级增强），仅亮度通道
  - 旋转：自然单位=角度（度），正值顺时针；裁剪：自然单位=像素框 (left, top, right, bottom)，越界或宽高≤0 拒绝
- **Rationale**: ImageEnhance 直通零换算误差；几何参数按 Clarifications Q1 例外条款取自然单位，UI 层后续自行映射。
- **Alternatives considered**: 色温用开尔文（换算复杂、课程场景无收益）；旋转用弧度（对用户不直观）。

## D4: RAW 解码管线

- **Decision**: RawAsset 组合 rawpy：`rawpy.imread` → `postprocess(use_camera_wb=True)` → 8bit RGB numpy → Pillow RGB；.ARW 为主验收格式，其余常见 RAW 尽力支持；解码失败抛带路径与原因的格式化异常（FR-011）
- **Rationale**: LibRaw 覆盖 .ARW/.CR2/.NEF 等主流格式；`use_camera_wb` 保留相机白平衡，出图观感接近厂商风格。
- **Alternatives considered**: dcraw 命令行（外部进程依赖，违背零外部进程约束）；planet/其他绑定（维护度不如 rawpy）。

## D5: 预览缓存与渐进渲染

- **Decision**: PreviewCache 维护三级分辨率——缩略 256px、中等 1024px、全图（原尺寸）；缓存键=（指令栈版本号，级数），版本号在每次入栈/撤销/重做时自增；渲染入口同步产出低分级、后台线程补齐高分级，完成经回调通知（满足 FR-017/FR-018 与 SC-005 顺序性验收）
- **Rationale**: 版本号比对实现最简单的失效判定；线程只用于「先后顺序」不追求并行度，规避 GIL 下的复杂同步（仅一处后台任务，用标准 `threading.Thread` 足够）。
- **Alternatives considered**: LRU 时间戳失效（判脏不如版本号精确）；进程池/异步框架（单用户桌面场景过重）。

## D6: 直方图统计

- **Decision**: HistogramCalculator 输出 R/G/B 三通道各 256 bin 的计数数组（Pillow `histogram()` 逐通道拆分）
- **Rationale**: 256 bin 是 8bit 图像的自然粒度，UI 绘图直接可用（FR-023）。
- **Alternatives considered**: 归一化亮度单通道直方图（丢失彩色信息，不满足三通道要求）。

## D7: 事件回调协议

- **Decision**: `events.py` 定义 `EngineEvents` 协议（结构化 duck-typing）：`on_progress(task_id, stage, fraction)`、`on_render_complete(task_id, preview)`、`on_error(task_id, message)`；引擎持有可选回调对象，为 None 时静默（FR-024）
- **Rationale**: 窄接口满足准则接口隔离；Protocol 避免引擎依赖具体 UI 类型，桥接层后续实现该协议注入。
- **Alternatives considered**: 观察者注册表（多订阅者管理超出单用户场景需要）；回调函数字典（无类型约束，易错）。

## D8: Sidecar 序列化协议

- **Decision**: JSON 结构 `{"version": 1, "image_path": "...", "instructions": [{"type": "<策略名>", "params": {...}}, ...]}`；命名同主名换扩展名（`photo.jpg` → `photo.json`）；加载时 AdjustmentFactory 按 type 反射重建；损坏/未知 type 抛格式化异常（FR-021/FR-022）
- **Rationale**: 协议即准则锁定的「类型标识 + 参数字典」；version 字段为未来协议演进留位。
- **Alternatives considered**: 与图片同目录集中索引（Clarifications Q4 已否决）；pickle（不可读、有安全面）。

## D9: 导出原子性

- **Decision**: Exporter 先渲染全图到内存，再写临时文件，成功后原子重命名为目标文件；任一步失败清理临时文件，不产生半成品（FR-020）
- **Rationale**: 同目录 `os.replace` 在 Windows/POSIX 均近原子，实现简单可靠。
- **Alternatives considered**: 直接覆写目标（失败即半成品，违反 FR-020）。

## D10: 调整合并与撤销语义

- **Decision**: EditSession 入栈前检查栈顶：同类且可合并则 `merge`（后值覆盖参数）；撤销弹出栈顶并压入重做栈；重做反向；**撤销后追加新调整清空重做栈**（FR-014）；空栈撤销/空重做栈重做报告无可操作项
- **Rationale**: 与设计文档 §6.5 及规格验收场景 2/3/4 一一对应；「清空重做」是所有编辑器的标准语义（规格 Edge Cases 已锁定）。
- **Alternatives considered**: 树状历史分支（超出规格范围，YAGNI）。
