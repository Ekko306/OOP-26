# Implementation Plan: PyLightroom 表现层（UI）——单页编辑界面

**Branch**: `003-ui-presentation-layer` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-ui-presentation-layer/spec.md`

## Summary

在既有三层之上补齐最后一层：`ui/` 目录以 Reflex 组件实现单页编辑界面（打开 → 预览/直方图 → 滑块调整 → 撤销/重做 → 导出）。页面是唯一的「组装点」——把桥接层 `FileState`/`DevelopState` 的状态变量注入哑组件属性、把事件处理器注入组件回调；组件零业务状态、零业务分支（schema 驱动渲染：有 min/max 渲染滑块、无则渲染数值输入、裁剪不渲染）。导出固定输出到 `output/` 目录（免输入），上传文件经 UI 层落盘后走既有 `open_file`。本特性对 `core/` 与 `state/` 零改动（纯增量新层），红线以 AST 静态断言进 CI（ui/ 零图像库、零引擎直引）。

## Technical Context

**Language/Version**: Python 3.11.7（uv 管理，Windows 本地）

**Primary Dependencies**: Reflex 0.10.1（002 已安装锁定，含 rx.recharts 图表）、`pylightroom.state`（002 已交付公共面：`FileState`/`DevelopState`）、Pillow/OpenCV/rawpy（仅经引擎间接使用，ui 层禁止直接 import）

**Storage**: 固定输出目录 `output/`（导出成品落盘，由引擎 Exporter/Sidecar 写文件）；上传暂存目录 `uploaded_files/`（Reflex 上传落盘）

**Testing**: pytest 全程无浏览器；组件以「props 注入构造 + 组件树 Var 断言」测试；页面绑定以组件树中对 State 属性/处理器引用的存在性断言测试；架构红线沿用 AST 静态断言（003 扩展 ui/ 目录）

**Target Platform**: 本地桌面级 Web 应用（`reflex run`，默认 3000 端口，Chrome/Edge，单用户）

**Project Type**: web-app（纯 Python 全栈，Reflex State 驱动）

**Performance Goals**: 打开样图后预览与直方图 3 秒内完整呈现（SC-001）；渐进时序承 002（低分先行、高分自动替换）

**Constraints**: 组件哑化（数据经属性注入、事件经回调上抛、零业务分支）；ui/ 仅 import Reflex 与 `pylightroom.state` 公共面；每个交互仅经桥接层事件处理器转发；本特性对 core/ 与 state/ 零修改

**Scale/Scope**: 单用户单会话单页；`pylightroom/ui/` 7 个模块（app、页面、6 类哑组件）+ 根 `rxconfig.py` + `tests/ui/` 测试包

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 准则 | 门槛 | 结论 |
| ---- | ---- | ---- |
| I UI 与逻辑严格分离 | ui/ 只调桥接层公共面；禁止图像处理库与引擎直引 | PASS。页面绑定 FileState/DevelopState 公共 vars 与处理器；组件连 State 都不 import（props 注入）；AST 红线测试覆盖 ui/ |
| II 继承立抽象，组合建运行 | 运行期以组合搭建 | PASS。页面组合六类哑组件；无新增继承（rx.State 子类已由 002 提供） |
| III 非破坏性编辑契约 | 原始像素永不修改 | PASS。UI 只消费 data URL 与直方图数组，导出走引擎 Exporter（原件不动） |
| IV 开闭原则 | 存量零修改，新增走注册 | PASS。对 core/state 零修改；新增调整注册后经 `adjustment_schemas` 自动出现于面板（动态渲染），UI 零修改 |
| V 引擎独立可测，测试先行 | 无浏览器环境完整测试；测试先行 | PASS。组件/页面/红线全部命令行可测（组件树 Var 断言）；tasks 以 TDD 顺序编排 |

无计划内偏差：本特性为纯新增层（additive-only），无引擎或桥接层改动。

## Project Structure

### Documentation (this feature)

```text
specs/003-ui-presentation-layer/
├── plan.md              # 本文件
├── research.md          # Phase 0 决策记录（D1–D7）
├── data-model.md        # Phase 1 组件实体与数据流契约
├── quickstart.md        # Phase 1 无浏览器验证指南 + 浏览器手动验收
├── contracts/
│   └── ui-api.md        # 页面-组件契约 + 渲染规则 + 层级红线
├── checklists/
│   └── requirements.md  # spec 质量清单（已全过）
└── tasks.md             # Phase 2 输出（/speckit-tasks 生成）
```

### Source Code (repository root)

```text
rxconfig.py                  # Reflex 应用配置（app_name=pylightroom，根目录惯例）
output/                      # 固定导出目录（运行时创建，git 忽略）
uploaded_files/              # 上传暂存目录（运行时创建，git 忽略）
pylightroom/
├── core/                    # 【引擎层】本特性零改动
├── state/                   # 【桥接层】本特性零改动（消费其公共面）
└── ui/                      # 【表现层】本特性主体
    ├── __init__.py          # 层级说明 + 公共导出面（app/page）
    ├── app.py               # rx.App 组装：注册页面路由 "/"
    ├── pages/
    │   └── index.py         # 唯一页面：布局组合 + 桥接层绑定（唯一 import state 的模块）
    └── components/
        ├── __init__.py
        ├── adjust_slider.py   # 单滑块（因子型）：值/范围/回调 props 注入
        ├── angle_input.py     # 角度输入 + 应用按钮（rotate）：数值 + 回调 props 注入
        ├── slider_panel.py    # 调整面板：按 schema 动态组合滑块/角度控件（排除裁剪）
        ├── histogram_view.py  # 直方图：RGB 三通道柱状（dict→图表行纯格式映射）
        ├── preview_canvas.py  # 预览画布：data URL 呈现 + 空状态占位
        └── file_menu.py       # 顶栏：上传打开/路径打开、撤销/重做、导出、忙碌指示、错误横幅
tests/
└── ui/
    ├── test_components.py   # 哑组件：props 注入构造 + 树内绑定存在性
    ├── test_index_page.py   # 页面组装：六组件齐备 + State 绑定引用断言
    ├── test_upload_export.py# 上传落盘→open_file、导出路径拼接（真实引擎 + 临时目录）
    └── test_architecture.py # 层级红线扩展：ui/ 零 PIL、零 core 直引、组件零 state import
```

**Structure Decision**: 沿用设计文档 §7 三层目录，`ui/` 内部再分 `pages/`（路由与组装）与 `components/`（哑组件）。页面是唯一 import `pylightroom.state` 的 UI 模块，组件仅 import Reflex——把「绑定」集中在一处，组件保持纯展示、可独立构造测试。`output/` 与 `uploaded_files/` 为运行期目录（git 忽略），不进包。

## Complexity Tracking

> 无需豁免条目：纯新增层，无宪法冲突，无存量修改。
