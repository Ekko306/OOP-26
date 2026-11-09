"""FileState：文件级状态（打开/导出，US1/US4）。

继承 DevelopState（Reflex 子状态语义：文件页与编辑页共享编辑变量）；
open_file/export_file 只做参数转换 + 引擎调用 + 状态回写（准则 I）。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pylightroom.core import AdjustmentFactory, EngineError

from pylightroom.state.develop_state import DevelopState
from pylightroom.state.session import get_session


class FileState(DevelopState):
    """文件级变量与打开/导出事件处理器。"""

    file_name: str = ""
    has_image: bool = False
    exporting: bool = False
    export_message: str = ""

    def open_file(self, path: str) -> Iterator[None]:
        """打开照片（US1）：engine open → 全重置 → 渐进推送。

        失败仅落 error_message，既有界面状态不变（FR-004）。
        """
        session = get_session()
        self.error_message = ""
        try:
            session.processor.open(path)
        except EngineError as exc:
            self.error_message = str(exc)
            yield
            return
        session.presenter.reset()  # 旧会话在途结果作废（FR-003）
        self.file_name = Path(path).name
        self.has_image = True
        self.exporting = False
        self.export_message = ""
        self.adjustment_schemas = AdjustmentFactory.registered_schemas()
        self._refresh_adjustment_values()
        session.processor.refresh_previews()  # 引擎增量三（D8）：当前版本三级预览
        yield from self._push_preview_progressively()

    def export_file(self, path: str, format: str = "jpeg") -> Iterator[None]:
        """导出成品（US4）：exporting 置位 → 转发引擎 → 反馈回写复位（三动作）。

        引擎保证原子写出与失败清理（FR-020）；本层仅转译结果消息。
        """
        self.exporting = True
        self.export_message = ""
        yield  # 第一帧：导出中（UI 呈现进度）
        try:
            get_session().processor.export(path, format)
        except EngineError as exc:
            self.export_message = f"导出失败：{exc}"  # 失败原因可读（FR-012）
            self.exporting = False
            yield
            return
        self.export_message = f"已导出至 {path}"
        self.exporting = False
        yield
