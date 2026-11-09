# Research: 表现层（UI）——单页编辑界面

**Feature**: 003-ui-presentation-layer | **Date**: 2026-11-09

本特性为纯新增层（`ui/` + `rxconfig.py` + `tests/ui/`），对 `core/`、`state/` 零修改。技术语境大部分已在 002 交付时确立（Reflex 0.10.1、无浏览器测试策略、三层红线），此处只记录 UI 特有决策。

## D1 哑组件与 Reflex 绑定模式：组件连 State 都不 import

**Decision**: 组件函数不 import `pylightroom.state`——状态变量与事件处理器全部由页面以 props 注入；页面（`pages/index.py`）是 UI 层唯一 import 桥接层的模块。

**Rationale**: Reflex 组件本质是返回组件树的纯函数，props 可以是普通值也可以是 State Var 表达式（`FileState.preview_data_url`、`FileState.on_slider_change`）。把 State 引用收敛到页面一处，组件保持「纯展示函数」：可传入示例值独立构造测试，也使 FR-013「零业务分支」可被静态检查验证（组件文件 grep 不到 state 引用）。

**Alternatives considered**:
- 组件直接引用 `FileState.xxx`（Reflex 常见写法）：否决——组件与 State 形成隐式耦合，无法脱离桥接层测试，「哑组件」约束不可静态验证
- 引入中间 ViewModel 层：过度设计——页面组装已是最薄绑定点

## D2 上传文件流转：UI 层落盘后走既有 open_file

**Decision**: 打开入口用 Reflex 上传控件，UI 层处理器把上传文件落盘到 `uploaded_files/`（文件名沿用原名），随后调用桥接层 `FileState.open_file(落盘路径)`；另备「路径输入 + 打开按钮」直接调 `open_file`，作为开发调试与本地盘文件入口。

**Rationale**: 引擎契约以路径为入口，上传文件必须先落盘。文件落盘属「用户交互捕获」（把浏览器文件流转成路径），不是图像处理、不含业务规则——恰是表现层职责；在桥接层新增上传处理器反而把交互框架细节（Reflex 上传对象）泄漏进 state 层。Reflex 0.10.1 上传 API（`rx.upload` + `rx.upload_files` handler）在实现任务中落地验证，若 API 形态有出入，以「上传文件落盘 → open_file」语义为准做最小适配。

**Alternatives considered**:
- 桥接层 FileState 新增 handle_upload：否决——state 层将依赖 Reflex 上传对象与文件 IO，偏离「参数转换 + 引擎调用 + 状态回写」三动作
- 仅保留路径输入框（免上传）：否决——浏览器演示需要上传入口（spec Assumptions），路径输入仅是开发便利

## D3 导出文件命名：固定 output/ 目录 + 原名后缀

**Decision**: 导出目标路径由 UI 拼接为 `output/<原文件名去扩展名>_edited.<格式后缀>`（如 `photo.png` 导出 jpeg → `output/photo_edited.jpg`），重名覆盖；目录不存在则创建。格式下拉仅 jpeg/png 两项，经 `FileState.export_file(path, format)` 透传。

**Rationale**: 澄清结论 B（固定输出目录、免输入）。文件名拼接是无分支的字符串格式化（展示层胶水），不加规则；`<stem>_edited` 避免覆盖原图，重名覆盖简化课程演示（重复导出即刷新成品）。`output/` 为运行期目录，git 忽略。

**Alternatives considered**:
- 时间戳文件名：否决——演示时文件名不可预测，且属无必要的复杂度
- 桥接层新增 export_to_output_dir：否决——「输出目录约定」是 UI 交付语义，下沉桥接层会把展示决策漏进胶水层
- 浏览器下载（rx.download）：否决——需新增下载端点，超出「简化完成课程要求」取向（Clarifications Q2 选 B）

## D4 schema 驱动的面板渲染规则

**Decision**: 面板按 `adjustment_schemas` 动态渲染：参数模式含 `min`/`max` → 滑块（因子型：brightness/contrast/saturation/sharpness/temperature，走 `on_slider_change`）；无 min/max 的单参数 → 数值输入 + 应用按钮（rotate 的 angle，走 `apply_adjustment`）；`box`（crop）本期不渲染任何入口；`histogram_equalization`（factor 型）正常渲染滑块。渲染顺序按调整名字母序。

**Rationale**: 澄清结论 Q1（旋转进、裁剪不进）。以「schema 是否含 min/max」做控件类型分派是数据驱动判断，渲染顺序稳定可测；新增调整注册后自动出现（准则 IV 的 UI 侧体现）。角度输入不做范围限制（引擎侧 angle 为任意实数），错误由引擎校验经错误通道回显。

**Alternatives considered**:
- 硬编码五个滑块 + 单独旋转区：否决——违背 FR-005 动态生成，扩展调整需改 UI
- rotate 用预设按钮组（±90/180）：否决——数值输入更通用且实现同代价

## D5 直方图渲染：recharts 柱状 + 纯格式映射

**Decision**: `histogram_view` 把 `{"r": [256], "g": [...], "b": [...]}` 映射为图表行 `[{bin: 0, r: …, g: …, b: …}, …]`（纯字典变换），用 Reflex 内置 `rx.recharts` BarChart 以三系列叠加呈现；未打开图片（空 dict）渲染占位提示。

**Implementation amendment (2026-11-09)**: 映射落点由「组件内前端 JS 表达式」改为「桥接层 computed var `DevelopState.histogram_rows`」——实测前端手写 `_js_expr` 绕过 Reflex 的 `useStateContext` 状态声明机制，页面运行时 ReferenceError。经 003 contracts §6 additive 通道移入桥接层（零业务规则、空直方图→空行集），组件改为直接绑定 rows var。chart 仍为 recharts 三系列叠加。

**Rationale**: dict→rows 是展示格式化而非业务规则（无规则分支、不触引擎）。recharts 是 Reflex 内置封装，零新增依赖。

**Alternatives considered**:
- 256 根柱 × 3 色 SVG 手绘：否决——自绘性能与实现成本高，recharts 足以呈现分布
- 直方图降采样后渲染：暂缓——256 bin 直渲染 recharts 可接受，卡顿再做优化（YAGNI）
- 前端手写 JS 表达式做 dict→rows：**否决（实测）**——绕过 state 声明，运行时崩溃

## D6 应用入口与运行形态

**Decision**: 根目录 `rxconfig.py`（`app_name="pylightroom"`，Redis/DB 均关闭即默认）；`pylightroom/ui/app.py` 创建 `rx.App()` 并注册 `pages/index.py` 的页面到路由 `/`；开发运行 `uv run reflex run`。`ui/__init__.py` 声明层级红线（仅 Reflex 与桥接层公共面）并导出 app 工厂。

**Rationale**: Reflex 官方惯例（rxconfig 在运行根目录）；以「app 工厂」而非模块级副作用导出，便于测试按需构建。

**Alternatives considered**:
- rxconfig 放 pylightroom/ 包内：否决——Reflex 以 CWD 定位 rxconfig，根目录是惯例

## D7 测试策略：组件树 Var 断言 + 红线扩展

**Decision**: 全部测试无浏览器：① 哑组件以示例 props 直接构造，断言返回组件树中关键绑定（Var 的字符串形式含期望的 State 属性/事件处理器名或注入值）；② 页面组装测试断言六类组件齐备且绑定正确；③ 上传/导出链路以真实引擎 + 临时目录跑通（复用 002 的 State 直接实例化模式）；④ `tests/ui/test_architecture.py` 扩展 002 的 AST 红线：ui/ 零 PIL/cv2/rawpy、零 `pylightroom.core` 直引、components/ 零 `pylightroom.state` import、全仓 reflex 仅出现在 state/ 与 ui/。

**Rationale**: 组件树中的 Var 以字符串渲染（如 `FileState.preview_data_url`），可低成本断言绑定存在性而不启动浏览器；SC-005/SC-006/SC-007 全部由此覆盖。组件树深度断言保持「关键绑定存在」粒度，不做像素级结构断言（脆弱、无价值）。

**Alternatives considered**:
- Playwright/浏览器端到端：否决——准则 V 要求无浏览器测试；手动验收走 quickstart 清单
- 仅手测 UI：否决——哑组件回归无防护，红线进不了 CI
