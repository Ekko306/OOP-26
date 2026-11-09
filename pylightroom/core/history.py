"""EditSession：非破坏性编辑会话（命令模式，US2 / M2 核心）。

有序指令栈 + 撤销/重做双栈 + 入栈同类合并 + 版本号。
只记录/迁移指令对象，绝不修改原始像素，不含任何图像处理逻辑（FR-012）。
"""

from __future__ import annotations

from pathlib import Path

from pylightroom.core.adjustments.base import BaseAdjustment
from pylightroom.core.errors import HistoryError


class EditSession:
    """一张图的全部编辑记录：持久化的单位（data-model §3）。"""

    def __init__(self, image_path: str | Path | None = None) -> None:
        # open 时注入；Sidecar 路径推导与 JSON image_path 字段的来源；None 时不可持久化
        self.image_path: Path | None = Path(image_path) if image_path is not None else None
        self.instructions: list[BaseAdjustment] = []
        self._undo_stack: list[BaseAdjustment] = []
        self._redo_stack: list[BaseAdjustment] = []
        self._version: int = 0

    @property
    def version(self) -> int:
        """每次变更自增，供预览缓存失效判定（FR-017）。"""
        return self._version

    # ------------------------------------------------------------------
    # 追加（含入栈同类合并，FR-015）与历史失效（FR-014）
    # ------------------------------------------------------------------
    def append(self, adjustment: BaseAdjustment) -> None:
        if self.instructions:
            top = self.instructions[-1]
            if type(top) is type(adjustment) and top.merge(adjustment):
                self._invalidate_redo()
                self._version += 1
                return
        self.instructions.append(adjustment)
        self._invalidate_redo()
        self._version += 1

    def _invalidate_redo(self) -> None:
        self._redo_stack.clear()

    # ------------------------------------------------------------------
    # 撤销/重做（双栈迁移，边界抛 HistoryError，FR-013）
    # ------------------------------------------------------------------
    def undo(self) -> None:
        if not self.instructions:
            raise HistoryError("nothing to undo：无可撤销的调整记录")
        self._redo_stack.append(self.instructions.pop())
        self._version += 1

    def redo(self) -> None:
        if not self._redo_stack:
            raise HistoryError("nothing to redo：无可重做的调整记录")
        self.instructions.append(self._redo_stack.pop())
        self._version += 1
