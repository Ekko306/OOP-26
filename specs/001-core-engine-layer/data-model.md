# Phase 1 Data Model: PyLightroom 核心引擎层

**Feature**: 001-core-engine-layer | **Date**: 2026-11-09 | **依据**: [spec.md](./spec.md) + [research.md](./research.md)

## 实体总览

```text
BaseImageAsset (抽象)
├── JpegAsset / PngAsset / BmpAsset / WebPAsset   （raster.py）
└── RawAsset                                       （raw.py）
        ▲ 组合
ImageProcessor (门面) ── EditSession ── List[BaseAdjustment] (抽象)
        │                                    ├── Brightness/Contrast/Saturation/Sharpness (basic.py)
        │                                    ├── Temperature/HistogramEqualization (color.py)
        │                                    ├── Crop/Rotate (geometry.py)
        │                                    └── AdjustmentFactory 反射创建
        ├── PreviewCache（三级分辨率，版本号失效）
        ├── Exporter ── SidecarFile（JSON v1）
        ├── HistogramCalculator
        └── EngineEvents（回调协议，注入）
```

## 实体明细

### 1. BaseAdjustment（抽象调整指令）

| 字段/成员 | 类型 | 约束 |
| ---- | ---- | ---- |
| `name` | 类属性 str | 类型标识，全引擎唯一，用于序列化与工厂反射 |
| `param_schema` | 类属性 dict | 每参数：键名、取值范围、默认值；色彩/锐度类统一 0.0–2.0（1.0 中性），几何类自然单位 |
| `apply(image, params)` | 抽象方法 | 输入 Pillow Image + 已校验参数，返回新 Image；禁止原地修改输入 |
| `serialize()` / `deserialize(data)` | 模板方法 | 按 param_schema 双向转换 `{"type": name, "params": {...}}`；往返无损（SC-002） |
| `merge(other)` | 虚方法 | 同类合并（后值覆盖参数）；不同类返回不可合并 |
| `validate(params)` | 具体方法 | 依 param_schema 校验，越界抛参数错误（FR-002） |

**8 个子类算法要点**：亮度/对比度/饱和度/锐度=ImageEnhance 因子直通；色温=BGR 增益（>1 暖 <1 冷）；直方图均衡=CLAHE 仅亮度通道、clipLimit 由因子映射（禁止 RGB 分通道，FR-005）；裁剪=像素框校验后 crop；旋转=角度正值顺时针。

### 2. BaseImageAsset（抽象图像资产）

| 字段/成员 | 类型 | 约束 |
| ---- | ---- | ---- |
| `path` / `format` / `exif` | 实例属性 | 构造时确定；exif 含尺寸、格式、拍摄时间（可得时） |
| `load()` | 模板方法（骨架在基类） | 统一异常包装与缓存判定；子类只实现 `_decode()` |
| `_decode()` | 抽象方法 | 返回统一 Pillow RGB 表示（D2） |
| `thumbnail()` | 具体方法 | 生成缩略/中等/全图三级分辨率（FR-010） |

**子类**：Jpeg/Png/Bmp/WebP（Pillow 直读；PngAsset 透明通道合成白底）；RawAsset（rawpy 后处理 → numpy → Pillow）。

### 3. EditSession（编辑会话）

| 字段 | 类型 | 约束 |
| ---- | ---- | ---- |
| `image_path` | Path \| None | 关联原图路径，open 时注入；Sidecar 路径推导与 JSON `image_path` 字段的来源；None 时不可持久化（报错） |
| `instructions` | List[BaseAdjustment] | 有序；只 append/pop，绝不修改原图（FR-012） |
| `_undo_stack` / `_redo_stack` | 内部历史栈 | 撤销=弹出末条入 redo；重做反向（FR-013） |
| `version` | int | 每次变更自增，供缓存失效判定（FR-017） |

**状态转换**：

```text
append(adj):
  栈顶同类可合并? → merge（version+1）           # FR-015
  ↳ 否则入栈; REDO_STACK = []                    # FR-014
undo:   instructions 非空? → 末条移入 redo 栈     # 否则报告无可操作项
redo:   redo 栈非空? → 弹回 instructions          # 否则报告无可操作项
```

### 4. SidecarFile（持久化）

| 字段 | 值 |
| ---- | ---- |
| 路径规则 | `photo.jpg` → 同目录 `photo.json`（Q4，XMP 惯例） |
| JSON 结构 | `{"version": 1, "image_path": "...", "instructions": [{"type": "...", "params": {...}}]}` |
| 写入 | 会话整体序列化；原子写（临时文件 + replace）；原图永不写入 |
| 读取 | Factory 按 type 重建；文件损坏/未知 type/版本不识别 → 格式化异常（FR-022） |

### 5. ImageProcessor（门面，组合根）

组合：`BaseImageAsset` + `EditSession` + `PreviewCache` + `Exporter` + `EngineEvents`。
职责：`open(path)`（经 AssetFactory）→ `update_adjustment(name, params)`（校验→入栈→标脏→低分重渲染→回调）→ `render(level)`（顺序应用指令链；空栈=原图，FR-016）→ `undo()/redo()` → `export(path, format)`。对外不暴露内部栈结构（门面约束）。

### 6. PreviewCache

| 字段 | 约束 |
| ---- | ---- |
| 三级分辨率 | 缩略 256px / 中等 1024px / 全图（D5） |
| 键 | (session.version, level)；版本不匹配即失效重渲染 |
| 顺序性 | 低分级同步先行，高分级后台线程补齐后经回调替换（SC-005） |

### 7. Exporter

按指令链渲染全图 → 写临时文件 → 原子 rename（D9）；失败清理且无半成品（FR-020）；导出成功同时将会话持久化为原图关联 Sidecar（`photo.jpg` → `photo.json`，成品不单独生成 Sidecar，FR-019/FR-021）。格式：JPEG（默认质量 95）/ PNG。

### 8. HistogramCalculator

输入 Pillow Image → 输出 `{"r": [256], "g": [256], "b": [256]}` 计数数组（D6，FR-023）。

### 9. EngineEvents（回调协议）

`on_progress(task_id, stage, fraction)` / `on_render_complete(task_id, image_bytes)` / `on_error(task_id, message)`；引擎侧为可选注入，None 时静默（D7，FR-024）。数据契约：仅原始数据与消息对象，禁止框架对象穿越（准则 I）。

## 校验规则汇总（来自 FR）

- 调整参数越界 → 拒绝执行 + 参数错误（FR-002、US1-3）
- 裁剪框越界/宽高≤0 → 参数错误（Edge Cases）
- 不支持扩展名/损坏文件/RAW 机型失败 → 格式化异常含路径与原因（FR-011）
- Sidecar 损坏/未知 type → 明确错误不静默丢弃（FR-022）
- 默认参数（1.0）应用 → 输出与原图一致（FR-002 中性值语义）
