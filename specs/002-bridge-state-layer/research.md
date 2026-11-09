# Research & Decisions: 桥接层（State）

**Feature**: 002-bridge-state-layer | **Date**: 2026-11-09

本文档记录 plan 阶段的全部技术决策。每条决策含：决定、理由、被否决的备选。

## D1 引擎门面增量：只读查询方法（current_params / registered_schemas）

**Decision**: 为引擎门面新增两个只读方法（不改既有签名）：
- `ImageProcessor.current_params() -> dict[str, dict]`：按调整名汇总当前生效参数（自栈顶向下首次命中者生效；撤销后随指令栈同步消失）
- `AdjustmentFactory.registered_schemas() -> dict[str, dict]`：全部已注册调整的参数模式深拷贝（name → {param: {min, max, default}}），供滑块刻度与默认值渲染

**Rationale**: FR-008 要求撤销/重做后界面滑块值与引擎编辑状态 100% 一致。若不改引擎，桥接层只能自行镜像指令栈（push/pop 模拟 undo/redo 与 merge 语义）——这会把会话逻辑放进桥接层，直接违反准则 I 与 FR-015（「逻辑下沉引擎」）。把查询放进引擎是唯一的正确分层：引擎 owns 状态，桥接层只读。两处方法均为 additive 只读，符合准则 IV；`current_params` 实现为对 `EditSession.instructions` 的一次反向扫描（约 6 行，引擎侧纯查询，与 001 测试零冲突）。

**Alternatives considered**:
- 桥接层镜像指令栈：否决——业务逻辑下沉失败，merge/undo 语义双份维护必然漂移
- 桥接层直接访问 `processor._session.instructions`：否决——core-api §8 明确「对外不暴露内部栈结构」，私有属性访问破坏契约
- 不支持滑块回写（撤销后滑块停在旧位置）：否决——直接违反 FR-008/SC-004

## D2 红线自检语义修正：全局扫描 → core 自身导入链增量检测

**Decision**: `pylightroom/core/__init__.py` 的 `_check_no_ui_framework` 从「扫描全局 `sys.modules` 是否含 reflex」改为「对 core 包每次导入动作做 sys.modules 前后差集检测」：仅当 reflex 模块在 core 包本次导入期间被新引入（即 core 的导入链主动拉取了 reflex）时抛 `EngineError`。急切导入（`__init__` 顶部）与惰性导入（`__getattr__` 内）均覆盖。

**Rationale**: 001 的全局扫描在引擎独跑时等价于导入链检测；但桥接层进程中 Reflex 合法先于 core 加载（Reflex 应用启动时已 `import reflex`），全局扫描会把「reflex 与 core 合法共存」误判为红线违规——Reflex 进程永远无法导入 core，集成完全阻断。grep 断言（准则 I 的第一道防线）不受影响；修正后的运行时自检语义更精确：「core 的导入链不得引入界面框架」。tests/ 无任何用例断言旧全局扫描行为（已检索确认），修正零破坏。

**Alternatives considered**:
- 桥接层导入 core 前删除 sys.modules 中的 reflex：否决——运行中的 Reflex 应用依赖这些模块，删除即崩溃
- 环境变量开关豁免：否决——core 出现「感知 UI」的开关，比检测语义修正更糟
- 移除运行时自检只留 grep：否决——丢失「导入即验证」的即时反馈，001 文档已承诺该钩子

## D3 state/ 内部分层：presenter + session 两个纯 Python 模块

**Decision**: 桥接层内部拆分：
- `presenter.py`：事件翻译器（内部类 `Presenter`），实现引擎 `EngineEvents` 协议——接收后台线程回调，维护「版本 → 各级预览字节/data URL」的最新结果容器（加锁）、忙碌标志、错误通道、按版本新者胜判定、有界等待原语；纯 Python，只 import `pylightroom.core`
- `session.py`：组合根（组合建运行，准则 II），持有一个 `ImageProcessor`（构造时注入 presenter）并提供测试替身注入口
- `develop_state.py` / `file_state.py`：Reflex State 类，事件处理器只做三动作，从 presenter 读取最新结果回写 vars

**Rationale**: 引擎高分预览回调来自后台线程，Reflex State 变量不能从任意线程安全改写；若 State 直接实现回调协议，State 类将被线程同步、版本判定、base64 编码等胶水细节淹没，且 Reflex 对象使无浏览器测试困难。把翻译器抽成纯 Python 后：presenter 100% 无浏览器可测（准则 V），State 类退化到三动作（FR-015），线程边界收敛在 presenter 内部。

**Alternatives considered**:
- State 类直接实现 EngineEvents：否决——线程安全/编码/版本逻辑与 Reflex 绑定耦合，不可无浏览器测试
- 每个回调直接写 rx.State 全局变量：否决——Reflex 不支持跨线程改写 State，行为未定义
- 引擎回调改为 asyncio 队列由 State 消费：否决——需要改引擎契约（非 additive），且引擎不应感知事件循环

## D4 渐进推送机制：同步处理器 + presenter 有界等待

**Decision**: 事件处理器为同步生成器：① 忙碌置位 → ② 引擎调用（低分回调在调用内同步送达，presenter 已更新）→ ③ 回写低分帧 + 直方图 → `yield` 推送 → ④ `presenter.wait_for("full", version, timeout=有界)` 阻塞等待后台高分（Condition 唤醒，非轮询）→ ⑤ 命中则回写高分帧并清除忙碌，超时则保留低分帧并按 presenter.busy 实况落状态。

**Rationale**: 设计文档 §6.2 已指明「利用事件处理器 yield 机制实现渐进推送」。引擎低分回调在 `update_adjustment` 调用内同步送达（001 已实现），天然构成第一帧；高分在 daemon 线程，用 `threading.Condition` 有界等待可零轮询拿到结果。单用户场景下同步等待可接受（设计文档已接受该权衡）。有界超时保证状态机不会永久悬挂。

**Alternatives considered**:
- async 处理器 + asyncio.Event：否决——引擎线程非事件循环线程，跨到 asyncio 需 call_soon_threadsafe 包装，复杂度不成比例
- 纯轮询（sleep 循环）：否决——Condition 等价且无空转
- 只推低分、高分由用户手动刷新：否决——违反 SC-002（自动替换）

## D5 预览编码：回调 PNG 字节 → base64 data URL

**Decision**: presenter 在接收 `on_render_complete` 的 PNG 字节时即时编码为 `data:image/png;base64,...` 字符串存入结果容器；State 直接把该字符串回写 `preview_data_url` var，`rx.image(src=...)` 可直接消费。

**Rationale**: spec 假设允许实现阶段确定编码形态；data URL 无需静态目录写盘与 URL 管理会话失效问题，版本新者胜逻辑收敛在 presenter 单点。001 引擎回调已保证 PNG 字节格式，编码是纯数据转换（胶水职责）。

**Alternatives considered**:
- 写入 assets/ 目录以 URL 引用：否决——需处理文件命名、清理与会话切换竞态，桥接层引入文件管理职责
- 传输原始字节经 WebSocket：否决——Reflex var 必须 JSON 可序列化，bytes 不可直接绑定

## D6 Reflex 安装与 State 测试策略

**Decision**: `uv add reflex`（版本以解析结果锁定写入 requirements.txt）或 `uv pip install reflex` 后固化版本；测试采用「直接实例化」：`state = DevelopState()` 后直接调用事件处理器方法并断言 vars（异步/生成器处理器按生成器迭代），不启动浏览器与服务器。

**Rationale**: Reflex 的 State 事件处理器本质是实例方法，直接实例化即可覆盖全部「参数转换 → 引擎调用 → 状态回写」断言，这正是桥接层的全部职责面（渲染细节属 UI 特性）。presenter 已承接线程/编码复杂性，State 测试只需替身引擎注入（经 session.py）或真实引擎 + 临时文件。

**Alternatives considered**:
- Reflex 官方浏览器端到端测试（rx.testing / Playwright）：否决——超出本特性范围，UI 特性（后续）再引入
- 绕过 State 类、只测 presenter：否决——FR-017 要求桥接层全部逻辑可测，三动作本身也要有回归

## D7 直方图获取：经引擎 HistogramCalculator，state 层零 PIL import

**Decision**: 每次需要刷新直方图时，State 处理器调用引擎 `HistogramCalculator.compute(engine.render("thumb"))`（渲染走 PreviewCache，命中缓存零成本），把 `{"r","g","b": [256 bin]}` 原样回写 `histogram` var。

**Rationale**: presenter 持有的是 PNG 字节，若在 presenter 内解码则必须 import Pillow——把「state 层只 import Reflex 与 core」的层级声明复杂化；改走引擎渲染接口后，state 层 import 面严格限定为 `reflex` + `pylightroom.core`，架构声明更干净且引擎缓存保证开销可忽略。

**Alternatives considered**:
- presenter 内 import Pillow 解码算直方图：否决——state 层出现第三方图像库依赖，偏离「只 import Reflex 与 core」的理想边界
- 引擎新增直方图推送回调：否决——改引擎契约，非 additive；直方图消费时机由界面节奏决定，推送反而失焦

## D8 引擎增量四：refresh_previews 公有方法（实现期新增 additive）

**Decision**: `ImageProcessor.refresh_previews()` 公有方法——渲染并推送当前版本三级预览（thumb 同步先行 + medium/full 后台线程），仅做 `_require_open` 包装后复用既有 `_refresh_previews`；桥接层 `open_file` 成功后调用。

**Rationale**: 规划期契约假定「open 后引擎自动推送预览」，实现确认 001 的 `open()` 只加载资产建会话、不产生任何预览事件（001 契约不变）；而 state 层禁 PIL、无法自行渲染。最小 additive 解即本方法——open 后由桥接层显式触发渐进推送，US1 时序（低分先行、高分替换）完全复用既有机制。

**Alternatives considered**:
- 让 open() 内置刷新：否决——改变 001 契约既有行为（open 无副作用语义），违反 additive-only 约束
- 桥接层直接调用私有 `_refresh_previews`：否决——越过公有契约，红线自检与可测性差

## D9 后台渲染会话身份校验（实现期竞态修复）

**Decision**: `_render_background` 在入口做会话对象身份快照，每级渲染完成后二次校验 `self._session is not session_at_start or self._session.version != version → 丢弃`。

**Rationale**: 重复打开图片会重建 `EditSession` 并使版本号归零——仅靠版本比较无法区分「新会话的 v0」与「旧会话在途的 v0」，旧在途渲染会以高/同版本号污染新会话（spec Edge Case「打开新图片时旧图片的在途渲染回调必须作废」）。以对象身份 + 版本双校验闭合该竞态；presenter 侧另有版本门控兜底（新者胜）。

**Alternatives considered**:
- 仅比较版本号：否决——重开场景版本归零等值，无法判别会话已切换
- 为会话引入全局递增 session_id：过度设计——对象身份（`is`）即天然唯一标识
