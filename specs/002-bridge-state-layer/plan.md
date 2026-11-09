# Implementation Plan: PyLightroom 桥接层（State）

**Branch**: `002-bridge-state-layer` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-bridge-state-layer/spec.md`

## Summary

桥接层把核心引擎门面（`ImageProcessor` + 回调协议）包装成界面框架可直接绑定的状态变量与事件处理器：打开→预览/直方图渐进呈现、滑块调整→参数转发→预览回写、撤销/重做→界面与编辑状态一致、导出→结果反馈。内部以纯 Python「事件翻译器」（presenter）承接引擎后台线程回调（按版本新者胜、线程安全），Reflex State 类只保留「参数转换 + 引擎调用 + 状态回写」三个动作。引擎侧仅两处只读增量（`current_params()`、`registered_schemas()`）与红线自检语义修正（全局 sys.modules 扫描 → core 自身导入链增量检测），均为 additive，不改动 001 契约既有签名。

## Technical Context

**Language/Version**: Python 3.11.7（uv 管理，Windows 本地）

**Primary Dependencies**: Reflex（本特性新增安装，版本以安装时最新稳定版锁定并写入 requirements）、`pylightroom.core`（001 已交付契约）、Pillow/OpenCV/rawpy（仅经引擎间接使用，state 层不直接 import）

**Storage**: N/A（持久化由引擎 Sidecar 负责，桥接层零持久化）

**Testing**: pytest，全程无浏览器；Reflex State 以直接实例化方式测试；引擎后台线程回调以同步注入方式测试

**Target Platform**: 本地桌面级 Web 应用（Reflex 默认端口，单用户）

**Project Type**: web-app（纯 Python 全栈，Reflex State 驱动）

**Performance Goals**: 低分预览先行、高分后台补齐后自动替换（顺序性验收；不设硬性时间指标，承 001 SC-005）

**Constraints**: 每个事件处理器 ≤「参数转换 + 引擎调用 + 状态回写」三动作；层间仅传递原始数据与消息对象；`core/` 目录零 `import reflex`（grep 红线）；state 层不直接 import Pillow/OpenCV

**Scale/Scope**: 单用户单会话（一次编辑一张图）；5 个 state 层模块 + `tests/state/` 测试包 + 引擎 3 处增量

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 准则 | 门槛 | 结论 |
| ---- | ---- | ---- |
| I UI 与逻辑严格分离 | 桥接层是唯一同时 import Reflex 与 core 的层；core 零 reflex import（grep 红线）；层间仅原始数据/消息对象 | PASS。presenter/session 为纯 Python（仅 import core），Reflex 只出现在两个 State 模块；D2 的自检语义修正不放松 grep 红线 |
| II 继承立抽象，组合建运行 | 运行期结构以组合搭建；继承仅限抽象族谱 + rx.State 业务子状态 | PASS。session（组合根）组合 ImageProcessor+presenter；继承仅 FileState(DevelopState) 子状态与 rx.State 基类 |
| III 非破坏性编辑契约 | 原始像素永不修改 | PASS。桥接层不触碰像素，只转发参数字典与图像字节 |
| IV 开闭原则 | 存量代码零修改，新增走注册 | PASS。引擎两处增量均为新增只读方法（additive）；新增调整经工厂注册即自动出现在 adjustment_schemas/values，桥接与 UI 零修改 |
| V 引擎独立可测，测试先行 | 无浏览器环境完整测试；测试先于实现 | PASS。presenter/引擎增量/State 逻辑全部可在命令行环境测试；tasks 以 TDD 顺序编排 |

计划内偏差（已论证，见 [research.md](./research.md) D1/D2）：引擎层 3 处 additive 变更。理由：撤销后滑块同步若在桥接层镜像指令栈，等于把会话逻辑下沉失败（违反准则 I/FR-015）；红线自检若维持全局扫描，Reflex 进程将无法导入 core（集成阻断）。

## Project Structure

### Documentation (this feature)

```text
specs/002-bridge-state-layer/
├── plan.md              # 本文件
├── research.md          # Phase 0 决策记录
├── data-model.md        # Phase 1 状态实体与数据契约
├── quickstart.md        # Phase 1 无浏览器验证指南
├── contracts/
│   └── state-api.md     # 桥接层对 UI 的契约 + 引擎增量契约
├── checklists/
│   └── requirements.md  # spec 质量清单（已全过）
└── tasks.md             # Phase 2 输出（/speckit-tasks 生成）
```

### Source Code (repository root)

```text
pylightroom/
├── core/                      # 【引擎层】仅 3 处 additive 变更（见 contracts/state-api.md §3）
│   ├── __init__.py            # 红线自检语义修正（D2）
│   ├── pipeline.py            # + ImageProcessor.current_params()（D1）
│   └── adjustments/factory.py # + AdjustmentFactory.registered_schemas()（D1）
├── state/                     # 【桥接层】本特性主体
│   ├── __init__.py            # 公共导出面 + 层级红线自检（唯一双 import 层）
│   ├── presenter.py           # 事件翻译器：EngineEvents 实现、版本新者胜、data URL、忙碌/错误通道（纯 Python）
│   ├── session.py             # 组合根：ImageProcessor + presenter 的单会话持有者（可注入替身）
│   ├── develop_state.py       # DevelopState(rx.State)：预览/直方图/调整值/忙碌/错误 + 编辑事件处理器
│   └── file_state.py          # FileState(DevelopState)：打开/导出事件处理器与文件级状态
└── ui/                        # 【表现层】不在本特性范围（后续特性）
tests/
└── state/
    ├── test_presenter.py        # 回调注入：顺序/乱序/错误/忙碌/等待
    ├── test_engine_additions.py # 引擎增量 + 红线自检修正
    ├── test_develop_state.py    # State 直接实例化：编辑事件链路
    ├── test_file_state.py       # 打开/导出链路（真实引擎 + 临时文件）
    └── test_architecture.py     # 层级红线：双 import 唯一性 grep 断言
```

**Structure Decision**: 沿用设计文档 §7 的三层物理目录（目录结构即架构）。state/ 内部把「胶水」拆成两个纯 Python 模块——presenter（承接引擎后台线程回调与数据转换，可脱离 Reflex 测试）与 session（组合根，支持测试注入替身）——使 Reflex State 类退化到纯三动作，同时满足准则 V 的无浏览器可测性。

## Complexity Tracking

> 无需豁免条目：引擎两处增量均为只读 additive 方法，红线自检修正仅收紧检测语义到「core 自身导入链」，不放松 grep 断言红线。
