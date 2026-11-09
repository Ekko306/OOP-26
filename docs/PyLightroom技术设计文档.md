# PyLightroom 简化版技术设计文档

**文档类型：前期技术设计（不含代码实现）**

**版本：V1.0**

**日期：2026-11-09**

---

## 1. 文档说明

### 1.1 编写目的

本文档为「简化版 Adobe Lightroom」桌面级 Web 应用（下称 **PyLightroom**）的前期技术设计文档。项目为面向对象程序设计课程作业，核心考核目标是：以优秀的面向对象设计（继承、组合、多态）实现一个高内聚低耦合、可扩展、易维护的图像编辑软件。

本文档只做技术设计，不包含任何代码实现。交付物为：系统架构、类与模块职责划分、设计模式选型说明、模块接口规格、目录结构、开发里程碑与风险预案。

### 1.2 读者

- 课程指导教师与答辩评委：验证 OOP 设计水平
- 开发者本人：作为后续编码的施工蓝图

### 1.3 需求范围确认记录

本项目参照 Adobe Lightroom 的功能体系做了如下取舍（已与需求方确认）：

| Lightroom 原有功能 | 本项目决策 | 理由 |
| ---- | ---- | ---- |
| Library 照片管理模块（目录、评级、筛选、收藏） | **舍弃** | 集中精力做 Develop 编辑模块，避免工作量发散 |
| 100+ 调整滑块、曲线、HSL、局部蒙版 | **保留基础组**：亮度/对比度/饱和度/锐度/色温 + 裁剪/旋转 + 直方图显示 | 基础组能完整覆盖策略模式继承体系，功能深度与 OOP 展示度平衡 |
| 非破坏性编辑（指令栈、历史面板、快照、虚拟副本） | **中等版**：指令栈 + 撤销/重做 + 导出时渲染，不做历史面板 UI 与快照 | 保留 Command 模式核心架构，交互简化以控制工期 |
| RAW 原图支持（.CR2/.NEF/.ARW 等） | **支持基础 RAW**：经 rawpy 解码后进入统一处理管线 | 展示 BaseImageAsset 抽象层的开闭原则扩展点 |

---

## 2. 项目概述

### 2.1 产品定位

PyLightroom 是一个基于 Web 的**非破坏性照片编辑器**：用户打开图片后，所有调整操作（拖动滑块、裁剪、旋转）都只记录为参数指令，**原始像素永不修改**；导出时才按指令链实时渲染生成新文件。这一「指令式编辑」是它区别于普通画图软件的根本特征，也是 Lightroom 的工作流灵魂 [1][2]。

### 2.2 系统边界

- **做**：图片导入（JPEG/PNG/BMP/WebP + 常见 RAW）、基础调整（滑块 + 裁剪 + 旋转）、直方图显示、撤销/重做、导出（JPEG/PNG）、编辑参数持久化（重开不丢失）
- **不做**：照片库管理、曲线/HSL/局部调整、批处理、打印、云同步、地图/人脸识别等 Lightroom 高级模块

### 2.3 技术栈总览

| 类别 | 选型 | 用途 |
| ---- | ---- | ---- |
| 前端框架 | Reflex | 纯 Python 全栈框架，State 驱动 UI，自动生成 React 前端 + FastAPI 后端，WebSocket 双向通信 [3][4] |
| 基础图像处理 | Pillow | I/O、几何变换、ImageEnhance 系列调整（亮度/对比度/饱和度/锐度）[5][6] |
| 高级图像处理 | OpenCV | 色温调整、直方图计算、直方图均衡等色彩科学类算法 [7] |
| RAW 解码 | rawpy（LibRaw 绑定） | 将相机 RAW 文件解码为可处理的 RGB 矩阵 [8] |
| 数据交换 | JSON | 调整指令序列化（Sidecar 文件） |
| 测试 | pytest | 核心引擎层纯 Python，可独立做单元测试 |

---

## 3. 系统总体架构

### 3.1 三层架构模型

系统严格划分为三层，依赖方向**单向向下**，这是「UI 与逻辑分离」强制要求的结构性保障：

| 层级 | 包名 | 职责 | 关键约束 |
| ---- | ---- | ---- | ---- |
| 表现层（UI） | `ui/` | 页面路由、组件渲染、用户交互捕获 | 只调用桥接层暴露的方法，禁止触碰任何图像处理 API |
| 桥接层（State） | `state/` | Reflex 状态定义、事件转发、把引擎结果转成 UI 可消费的数据 | 唯一允许同时 import Reflex 与核心引擎的层，只做「胶水」，不含业务规则 |
| 核心引擎层（Core） | `core/` | 资产加载、调整算法、指令栈、撤销重做、渲染、导出、序列化 | **纯 Python，零 Reflex 依赖**，可独立运行、独立测试、独立复用 |

### 3.2 分离机制的强制保障

「UI 类与逻辑类不耦合」不能只靠自觉，本设计用四条硬约束保障：

1. **物理隔离**：`core/` 目录不出现任何 `import reflex` 语句，CI 可用一条 grep 断言永久把关——这是验收红线，违反即返工。
2. **依赖倒置**：桥接层依赖引擎（组合一个 ImageProcessor 实例），引擎对桥接层一无所知。引擎层若需通知外部「渲染完成」，通过回调接口（观察者）注入，由桥接层实现，而不是反向调用 State。
3. **数据契约**：两层间只传递「原始数据 + 消息对象」（参数字典、图像字节、进度事件），禁止传递 UI 组件或 Reflex 对象。
4. **独立可测**：`core/` 可在无浏览器的命令行环境跑完整单元测试；`ui/` 层的改动永远不需要改引擎的测试。

### 3.3 一次典型交互的完整链路

以「用户拖动对比度滑块」为例：

1. UI 层滑块组件触发事件 → 调用桥接层事件处理器；
2. 桥接层将滑块值转为参数字典，调用引擎层 `ImageProcessor.update_adjustment(对比度, 值)`；
3. 引擎向指令栈压入一条更新指令，标记预览脏位，异步重渲染低分辨率预览；
4. 渲染完成，引擎经回调接口通知桥接层；
5. 桥接层把预览图 URL 写入 State 变量，Reflex 自动重渲染受影响组件。

整个过程中，UI 层不知道「指令栈」的存在，引擎层不知道「滑块」的存在。

---

## 4. 面向对象核心设计

本章是文档的重心。所有设计以两个原则展开：**继承用于建立抽象分类体系（is-a）**，**组合用于搭建运行能力（has-a）**，避免为炫技而滥用继承。

### 4.1 继承体系一：调整操作（策略族）

**抽象基类 `BaseAdjustment`** 定义所有图像调整操作的统一契约：

| 成员 | 性质 | 职责 |
| ---- | ---- | ---- |
| `name` / `param_schema` | 类属性 | 指令名称、参数模式（键名、取值范围、默认值） |
| `apply(image, params)` | **抽象方法** | 对图像执行该调整，返回新图像对象 |
| `serialize()` / `deserialize(data)` | 模板方法 | 指令对象 ↔ 字典，序列化逻辑内聚于基类，子类零负担 |
| `merge(other)` | 虚方法 | 两条同类指令的合并规则（后值覆盖），支撑「同一滑块多次拖动只占一条历史」 |

**具体策略子类**（继承 BaseAdjustment，每类封装一种算法）：

| 子类 | 封装算法 | 底层库 |
| ---- | ---- | ---- |
| `BrightnessAdjustment` | 亮度/曝光线性缩放 | Pillow ImageEnhance [6] |
| `ContrastAdjustment` | 对比度（均值基准缩放） | Pillow ImageEnhance |
| `SaturationAdjustment` | 饱和度（亮度保持） | Pillow ImageEnhance |
| `SharpnessAdjustment` | 锐化/模糊 | Pillow ImageEnhance |
| `TemperatureAdjustment` | 色温（暖/冷色调偏移） | OpenCV 色彩矩阵 |
| `CropAdjustment` | 裁剪（记录几何框，不直接切图） | Pillow crop |
| `RotateAdjustment` | 旋转/翻转 | Pillow rotate |
| `HistogramEqualizationAdjustment` | 直方图均衡（仅在亮度通道执行，保护色彩） | OpenCV CLAHE [7] |

**设计价值**：新增「暗角」「颗粒感」等工具时，只需新建一个子类并注册，**任何现有代码零修改**——开闭原则的直接体现，也是答辩时最有说服力的扩展演示。

### 4.2 继承体系二：图像资产（格式族）

**抽象基类 `BaseImageAsset`** 统一「一张被编辑的图」的资源契约：

| 成员 | 性质 | 职责 |
| ---- | ---- | ---- |
| `load()` | 抽象方法 | 把磁盘文件解码为统一的内存图像表示（模板方法在基类统一处理缓存与异常） |
| `exif` / `path` / `format` | 实例属性 | 元数据（尺寸、格式、拍摄时间） |
| `thumbnail()` | 具体方法 | 生成多级分辨率预览（缩略图/中等/全图） |

**具体子类**：`JpegAsset`、`PngAsset`（含带透明通道的特殊处理）、`RawAsset`（组合 rawpy 解码管线，将 RAW 转为 RGB 矩阵后与普通图走同一条后续管线）[8]。

**设计价值**：`RawAsset` 是「以继承扩展新格式」的最佳示例——新增 RAW 支持没有触碰任何已有加载代码。

### 4.3 组合结构设计

| 组合方 | 被组合部分 | 说明 |
| ---- | ---- | ---- |
| `EditSession`（编辑会话） | 指令列表 `List[BaseAdjustment]` | 非破坏性编辑的核心：每次调整只追加指令对象，渲染时顺序应用；多态调度使会话不关心具体指令类型 |
| `ImageProcessor`（处理器） | `BaseImageAsset` + `EditSession` + 预览缓存 + 导出器 | 协调「读取原图 → 应用指令链 → 生成预览」的完整流程 |
| `UndoStack` / `RedoStack` | `EditSession` 的指令差异快照 | 撤销 = 弹出末尾指令；重做 = 重新压入，无状态丢失 [2] |
| `Exporter` | 序列化器 + `ImageProcessor` | 导出时按指令链实时渲染最终像素并写出文件 |
| `SidecarFile` | 序列化器 | 把指令栈存为与图片同名的 JSON 文件（对应 Lightroom 的 XMP Sidecar 理念 [2]），重开图片自动恢复编辑状态 |
| UI 组件树 | Reflex 原子组件 | `SliderPanel` 组合多个 `AdjustSlider`，页面组合 `SliderPanel + Canvas + HistogramView` |

### 4.4 设计模式选型总表

| 模式 | 应用位置 | 解决的问题 | 类型侧重 |
| ---- | ---- | ---- | ---- |
| **策略模式** | BaseAdjustment 策略族 | 调整算法可互换、可扩展 [9] | 继承 + 多态 |
| **命令模式** | 指令栈 + 撤销/重做 | 非破坏性编辑、操作历史 [10] | 组合 |
| **模板方法** | BaseImageAsset.load 的缓存/异常骨架；BaseAdjustment.serialize | 公共流程内聚基类，子类只填差异 | 继承 |
| **工厂模式** | `AssetFactory`（按扩展名造资产）、`AdjustmentFactory`（按 type 字符串反射造策略实例） | 解除上层对具体子类的依赖 | 组合 |
| **观察者模式** | 引擎 → 桥接层的渲染完成/进度回调 | 引擎不反向依赖 UI，反向控制零耦合 | 组合 |
| **门面模式** | `ImageProcessor` 对外暴露的极简接口 | UI 侧只需认识一个类 | 组合 |

> 继承与组合的分工一目了然：**继承集中在两棵抽象族谱（调整族、资产族）+ Reflex State 子类化**；**组合承担全部运行期结构（会话、处理器、撤销栈、导出器、组件树）**。优先组合、谨慎继承，符合「组合优于继承」的经典原则，答辩可直接引用。

### 4.5 SOLID 达成路径

| 原则 | 体现 |
| ---- | ---- |
| 单一职责 | 每个类一个变化维度：算法变 → 改策略子类；格式变 → 加资产子类；UI 变 → 改 ui 层 |
| 开闭 | 新调整工具/新图片格式 = 新增子类 + 工厂注册，存量代码零修改 |
| 里氏替换 | 所有策略/资产子类可无差别替换进指令栈与处理器 |
| 接口隔离 | 引擎回调只暴露 on_render_complete / on_progress 两个窄方法 |
| 依赖倒置 | 桥接层与工厂依赖抽象基类；引擎层完全不依赖 Reflex |

---

## 5. 模块详细设计

### 5.1 核心引擎层 `core/`

| 模块 | 核心类 | 职责 |
| ---- | ---- | ---- |
| `adjustments/` | BaseAdjustment + 8 个策略子类 + AdjustmentFactory | 全部图像调整算法与序列化 |
| `assets/` | BaseImageAsset、JpegAsset、PngAsset、RawAsset、AssetFactory | 文件解码、元数据、多级预览 |
| `pipeline.py` | ImageProcessor、PreviewCache | 渲染管线与预览缓存（低分预览先行、全图后台补齐） |
| `history.py` | EditSession、UndoStack、RedoStack | 指令栈、撤销重做、指令合并 |
| `persistence.py` | SidecarFile | 指令栈 ↔ JSON 的读写 |
| `exporter.py` | Exporter | 按指令链渲染全图并导出 JPEG/PNG |
| `histogram.py` | HistogramCalculator | RGB 三通道直方图统计（供 UI 绘图消费） |
| `events.py` | 回调协议（渲染完成、进度、错误） | 引擎对外的唯一通知出口 |

### 5.2 桥接层 `state/`

| 状态类 | 继承自 | 职责 |
| ---- | ---- | ---- |
| `DevelopState` | rx.State | 滑块值、预览 URL、直方图数据、processing 标志等 UI 绑定变量；事件处理器只做「取参 → 调引擎 → 写状态」三件事 |
| `FileState` | rx.State | 打开/导入图片、导出进度 |

约束：桥接层单个事件处理器不超过「参数转换 + 引擎调用 + 状态回写」三个动作；出现任何 if/else 业务分支，说明逻辑该下沉到引擎层。

### 5.3 表现层 `ui/`

| 模块 | 内容 |
| ---- | ---- |
| `components/` | `AdjustSlider`（单滑块，参数与回调由外部注入）、`SliderPanel`（组合多个滑块）、`HistogramView`、`PreviewCanvas`、`FileMenuBar`、`ExportDialog` |
| `pages/` | 单页编辑界面（打开图片 → 编辑 → 导出全流程一页完成） |

组件均为「哑组件」：不持有业务状态，一切数据经 props 注入，事件经回调上抛——与引擎层的「纯逻辑」形成镜像对称。

### 5.4 序列化协议（Sidecar 文件）

指令对象采用「类型标识 + 参数字典」协议持久化，对应 Lightroom 的 XMP Sidecar 理念 [2]：

- 每条指令序列化为包含 type（策略名）与 params（参数字典）的 JSON 对象；
- 整个编辑会话序列化为指令数组 + 图片路径 + 版本号；
- 加载时由 AdjustmentFactory 按 type 反射重建策略实例并注入参数；
- 原图文件永不写入，满足「非破坏」的存储层定义。

---

## 6. 数据流与关键技术难点

### 6.1 导入 → 编辑 → 导出主流程

导入（AssetFactory 按扩展名造资产子类）→ 解码生成多级预览并写入缓存 → 用户调整（指令入栈、低分预览即时重渲染）→ 松开滑块（后台线程渲染高分预览替换）→ 导出（Exporter 遍历指令链对全图应用全部指令 → 写出成品文件 + Sidecar）。

### 6.2 难点一：Web 端预览性能

拖动滑块若每次经 WebSocket 传全图会明显卡顿。方案：PreviewCache 维护缩略/中等/全图三级分辨率；交互期仅重渲染并 Base64 传输低分预览；利用 Reflex 事件处理器的 yield 机制实现渐进推送（先低分后高分）[3][4]。缓存失效策略采用「指令栈版本号」比对，避免无效重渲染。

### 6.3 难点二：彩色图直方图均衡的色偏

对 RGB 三通道分别均衡会破坏色彩关系产生色偏。方案：HistogramEqualizationAdjustment 内部严格执行「转 YCrCb/LAB 空间 → 仅对亮度通道做 CLAHE → 合并转回」的流程，并用 clipLimit 抑制噪声放大 [7]。

### 6.4 难点三：RAW 解码与统一管线

RAW 文件是传感器马赛克数据，需去马赛克、白平衡、色彩空间转换才能编辑。方案：RawAsset 组合 rawpy 完成解码 [8]，输出与普通图相同的内存表示；后续管线对「图从哪来」完全无感——这正是资产抽象层的价值。

### 6.5 难点四：撤销与指令合并

同一滑块连续拖动会产生大量中间指令，历史会被淹没。方案：BaseAdjustment.merge 定义同类合并规则，指令栈在入栈前检查栈顶是否同类可合并；撤销粒度天然干净。

---

## 7. 项目目录结构设计

```text
pylightroom/
├── rxconfig.py
├── assets/                  # 静态资源与预览缓存
├── pylightroom/
│   ├── core/                # 【核心引擎层】纯 Python，零 Reflex 依赖
│   │   ├── __init__.py
│   │   ├── adjustments/
│   │   │   ├── __init__.py
│   │   │   ├── base.py      # BaseAdjustment 抽象基类
│   │   │   ├── basic.py     # 亮度/对比度/饱和度/锐度策略
│   │   │   ├── color.py     # 色温/直方图均衡策略
│   │   │   ├── geometry.py  # 裁剪/旋转策略
│   │   │   └── factory.py   # AdjustmentFactory
│   │   ├── assets/
│   │   │   ├── __init__.py
│   │   │   ├── base.py      # BaseImageAsset 抽象基类
│   │   │   ├── raster.py    # Jpeg/Png/Bmp/WebP 资产
│   │   │   ├── raw.py       # RawAsset（rawpy）
│   │   │   └── factory.py   # AssetFactory
│   │   ├── pipeline.py      # ImageProcessor、PreviewCache
│   │   ├── history.py       # EditSession、Undo/RedoStack
│   │   ├── persistence.py   # SidecarFile 读写
│   │   ├── exporter.py      # Exporter
│   │   ├── histogram.py     # HistogramCalculator
│   │   └── events.py        # 回调协议
│   ├── state/               # 【桥接层】唯一 import Reflex + core 的层
│   │   ├── __init__.py
│   │   ├── develop_state.py
│   │   └── file_state.py
│   └── ui/                  # 【表现层】哑组件与页面
│       ├── __init__.py
│       ├── components/
│       │   ├── __init__.py
│       │   ├── adjust_slider.py
│       │   ├── slider_panel.py
│       │   ├── histogram_view.py
│       │   ├── preview_canvas.py
│       │   └── export_dialog.py
│       └── pages/
│           ├── __init__.py
│           └── editor.py
├── tests/                   # 核心引擎层单元测试（无浏览器环境）
└── requirements.txt
```

目录结构即架构：三个物理目录对应三个逻辑层，`core/` 的独立性一眼可辨，答辩时可直接作为「UI 与逻辑分离」的结构性证据。

---

## 8. 开发里程碑

| 阶段 | 交付物 | 验收标准 | OOP 里程碑 |
| ---- | ---- | ---- | ---- |
| M1 引擎骨架 | BaseAdjustment + 4 个基础策略 + 单测 | 命令行环境对 JPEG 应用亮度/对比度并出图 | 继承体系一落地 |
| M2 会话与历史 | EditSession、Undo/Redo、指令合并、序列化 | 撤销重做正确；重开程序编辑状态恢复 | 命令模式 + 组合落地 |
| M3 资产与 RAW | BaseImageAsset 族 + 双工厂 | RAW 文件与 JPEG 走同一管线出图 | 继承体系二 + 开闭原则 |
| M4 Reflex 集成 | 桥接层 + 单页 UI（滑块 + 画布） | 浏览器中拖滑块实时预览 | 三层分离验收（grep 断言 core 零 Reflex） |
| M5 完善 | 直方图、裁剪旋转、导出对话框、性能优化 | 完整走通「打开 → 编辑 → 导出」 | 端到端联调 |
| M6 收尾 | 测试补全、架构说明、答辩材料 | pytest 全绿；新增一个自定义调整插件不改旧代码（答辩演示） | 扩展性实证 |

里程碑刻意把引擎层（M1–M3）全部排在接触 Reflex（M4）之前：逻辑层先于 UI 独立成型并测试，本身就是「UI 与逻辑分离」最好的过程证明。

---

## 9. 风险与预案

| 风险 | 概率 | 预案 |
| ---- | ---- | ---- |
| RAW 样片格式多样，rawpy 解码个别机型失败 | 中 | RawAsset 解码失败抛格式化异常，UI 提示但不崩溃；答辩演示自带验证过的样片 |
| 预览性能不达预期，滑块拖动卡顿 | 中 | 降级预案：交互期预览分辨率降至 240p 级别；缩略图渲染与全图渲染彻底分离在不同线程 |
| Reflex 版本迭代导致 API 变动 | 低 | 桥接层极薄，改动集中在一个目录；锁定 requirements 版本号 |
| 工期超支 | 中 | 功能裁剪顺序已排定：先弃直方图、再弃色温；OOP 架构（评分主体）在任何裁剪下完整保留 |

---

## 10. 面向对象考核点自查

| 考核维度 | 本设计的对应实现 |
| ---- | ---- |
| 继承 | BaseAdjustment → 8 策略子类；BaseImageAsset → 3+ 资产子类；rx.State → 2 业务子状态 |
| 组合 | EditSession 组合指令列表；ImageProcessor 组合资产/会话/缓存/导出器；UI 组件树嵌套 |
| 多态 | 指令栈遍历时统一调用 apply，会话对具体指令类型无感知 |
| 抽象 | 两棵抽象基类树只定义契约不绑定实现 |
| 封装 | 每种算法内聚于单一策略类；序列化细节对子类透明 |
| UI/逻辑分离 | 三层物理目录 + 单向依赖 + grep 断言 + 独立测试四重保障 |
| 开闭原则 | 新调整工具/新格式 = 加子类 + 注册工厂，旧代码零修改 |
| 高内聚低耦合 | 策略类之间零依赖；core 层零框架依赖；层间只走窄接口 |

---

## 11. 参考来源

- [1] Adobe 官方：在 Lightroom Classic 的「修改照片」模块中编辑照片 [helpx.adobe.com](https://helpx.adobe.com/cn/lightroom-classic/desktop/help/applying-adjustments-develop-module-basic.html)
- [2] Lightroom Queen：撤销与历史记录机制 [lightroomqueen.com](https://www.lightroomqueen.com/how-undo-restore-history/)
- [3] Reflex 官方文档：项目结构与大型应用最佳实践 [reflex.dev](https://reflex.dev/docs/advanced-onboarding/code-structure/)
- [4] Reflex 编码范式与最佳实践指南 [mp.weixin.qq.com](https://mp.weixin.qq.com/s?__biz=Mzg5NDU1OTc3Mg==&idx=1&mid=2247484688&sn=b49d039d06b17da4c2b084a17d56e971)
- [5] Pillow 基础操作 [runoob.com](https://www.runoob.com/pillow/pillow-basic.html)
- [6] Pillow ImageEnhance 官方参考 [pillow.readthedocs.io](https://pillow.readthedocs.io/en/latest/reference/ImageEnhance.html)
- [7] OpenCV 彩色图像直方图均衡化（YCrCb 通道法）[wenku.csdn.net](https://wenku.csdn.net/doc/3unn8jgwky)
- [8] Python 策略模式实现 [dev.to](https://dev.to/timilehin-olusegun/strategy-design-patterns-in-python-3n3a)
- [9] Python Reflex 构建现代 Web 应用指南 [blog.csdn.net](https://blog.csdn.net/liaoqingjian/article/details/147415295)
- [10] Pillow ImageOps 与图像增强模块 [pillow.ac.cn](https://pillow.ac.cn/en/stable/reference/ImageOps.html)
