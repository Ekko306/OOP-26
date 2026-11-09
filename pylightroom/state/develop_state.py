"""DevelopState：编辑视图状态（Reflex State 基类，US2/US3）。

只做「参数转换 + 引擎调用 + 状态回写」三动作（准则 I、FR-015）；业务规则
全部在引擎。预览字节一律来自 presenter（引擎 PNG 编码，D5），直方图经引擎
HistogramCalculator 计算（D7）——本层零 PIL import。
"""

from __future__ import annotations

from collections.abc import Iterator

import reflex as rx

from pylightroom.core import EngineError, HistogramCalculator

from pylightroom.state.session import get_session

# 后台高分（full）渲染的有界等待上限；超时保留低分帧（research D4）
FULL_WAIT_TIMEOUT_SECONDS: float = 5.0


class DevelopState(rx.State):
    """编辑视图变量与调整类事件处理器（滑块/几何/撤销/重做）。"""

    preview_data_url: str = ""
    histogram: dict[str, list[int]] = {}
    adjustment_values: dict[str, dict] = {}
    adjustment_schemas: dict[str, dict] = {}
    busy: bool = False
    error_message: str = ""

    # ------------------------------------------------------------------
    # 内部回写辅助（私有方法，非事件处理器；仅「取数 → 写 vars」）
    # ------------------------------------------------------------------
    def _write_histogram(self) -> None:
        """直方图 ← 引擎对当前 thumb 渲染的计算结果（D7）。"""
        result = HistogramCalculator.compute(get_session().processor.render("thumb"))
        self.histogram = {channel: list(bins) for channel, bins in result.items()}

    def _refresh_adjustment_values(self) -> None:
        """adjustment_values ← current_params；缺席名回补 schema 默认值（US3 一致性）。

        键集为生效参数 ∪ schemas：几何类调整（rotate/crop）即便不在
        schemas 中也能如实呈现引擎实况。
        """
        effective = get_session().processor.current_params()
        schemas = self.adjustment_schemas
        self.adjustment_values = {
            name: (
                dict(effective[name])
                if name in effective
                else {
                    param: rule.get("default") for param, rule in schemas[name].items()
                }
            )
            for name in set(effective) | set(schemas)
        }

    def _push_preview_progressively(self) -> Iterator[None]:
        """渐进回写（D4/D5）：thumb 帧+直方图 → yield → 有界等待 full → 结算。

        busy/错误通道按 presenter 实况落定；错误按版本门控回显（FR-013）。
        """
        session = get_session()
        version = session.processor.version
        thumb = session.presenter.latest("thumb")
        if thumb is not None:
            self.preview_data_url = thumb.data_url
        self._write_histogram()
        self.busy = True
        yield  # 第一帧（低分先行）推送
        if session.presenter.wait_for("full", version, FULL_WAIT_TIMEOUT_SECONDS):
            full = session.presenter.latest("full")
            if full is not None:
                self.preview_data_url = full.data_url
        self.busy = session.presenter.busy
        error = session.presenter.error_message
        if error and session.presenter.error_version >= version:
            self.error_message = error

    # ------------------------------------------------------------------
    # 事件处理器（US2 滑块渐进更新 / US3 撤销重做）
    # ------------------------------------------------------------------
    def on_slider_change(self, name: str, value: float) -> Iterator[None]:
        """滑块事件 → 因子参数转换（UI 语义：滑块即因子，contracts §2）。"""
        yield from self._forward_adjustment(name, {"factor": value})

    def apply_adjustment(self, name: str, params: dict) -> Iterator[None]:
        """几何类调整通用入口：params 原样透传引擎（contracts §2）。"""
        yield from self._forward_adjustment(name, params)

    def undo(self) -> Iterator[None]:
        """撤销：引擎 undo → 参数值随 current_params 同步（FR-008）。"""
        yield from self._forward_history(get_session().processor.undo)

    def redo(self) -> Iterator[None]:
        """重做：引擎 redo → 参数值随 current_params 同步（FR-008）。"""
        yield from self._forward_history(get_session().processor.redo)

    # ------------------------------------------------------------------
    # 转发实现（错误隔离 + 渐进回写的公共尾段；无业务规则）
    # ------------------------------------------------------------------
    def _forward_adjustment(self, name: str, params: dict) -> Iterator[None]:
        session = get_session()
        self.error_message = ""  # FR-013：新操作即清除旧错
        self.busy = True
        try:
            session.processor.update_adjustment(name, params)
        except EngineError as exc:
            self.error_message = str(exc)  # 错误隔离：不向 UI 抛出（FR-012）
            self.busy = session.presenter.busy
            yield
            return
        self._refresh_adjustment_values()
        yield from self._push_preview_progressively()

    def _forward_history(self, operation) -> Iterator[None]:
        session = get_session()
        self.error_message = ""
        self.busy = True
        try:
            operation()
        except EngineError as exc:  # 空栈等：提示可读，界面状态不变（FR-009）
            self.error_message = str(exc)
            self.busy = session.presenter.busy
            yield
            return
        self._refresh_adjustment_values()
        yield from self._push_preview_progressively()
