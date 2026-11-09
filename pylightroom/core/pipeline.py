"""渲染管线：PreviewCache（三级分辨率 + 版本号失效）与 ImageProcessor 门面（US5）。

- PreviewCache：键 = (session.version, level)，版本不匹配即失效（FR-017，D5）
- ImageProcessor：组合 AssetFactory 产物 + EditSession + PreviewCache + EngineEvents；
  低分预览同步先行、高分级后台线程补齐后经回调替换（FR-018，SC-005 顺序性）；
  对外不暴露内部栈结构（core-api §1/§8）
"""

from __future__ import annotations

import io
import threading
from pathlib import Path

from PIL import Image

from pylightroom.core.adjustments.factory import AdjustmentFactory
from pylightroom.core.assets.base import THUMB_SIZE, MEDIUM_SIZE
from pylightroom.core.assets.factory import AssetFactory
from pylightroom.core.errors import AssetError
from pylightroom.core.events import EngineEvents
from pylightroom.core.history import EditSession

RenderLevel = str  # Literal["thumb", "medium", "full"]


class PreviewCache:
    """以 (version, level) 为键的预览缓存；仅保留当前版本条目。"""

    def __init__(self) -> None:
        self._entries: dict[tuple[int, RenderLevel], Image.Image] = {}

    def get(self, version: int, level: RenderLevel) -> Image.Image | None:
        return self._entries.get((version, level))

    def put(self, version: int, level: RenderLevel, image: Image.Image) -> None:
        self._entries = {
            key: value for key, value in self._entries.items() if key[0] == version
        }
        self._entries[(version, level)] = image


def _encode_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class ImageProcessor:
    """门面：open → update_adjustment → render → undo/redo → export（组合根）。"""

    def __init__(self, events: EngineEvents | None = None) -> None:
        self._events = events
        self._asset = None
        self._session: EditSession = EditSession()
        self._cache = PreviewCache()
        self._bg_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # 打开（经 AssetFactory，FR-009）
    # ------------------------------------------------------------------
    def open(self, path: str | Path) -> None:
        asset = AssetFactory.create(path)  # 不支持扩展名 → AssetError
        asset.load()  # 立即解码：损坏文件在 open 即暴露（FR-011，无半初始化残留）
        self._asset = asset
        self._session = EditSession(image_path=Path(path))
        self._cache = PreviewCache()

    @property
    def version(self) -> int:
        """当前会话指令栈版本（只读；缓存失效判定依据，FR-017）。"""
        return self._session.version

    # ------------------------------------------------------------------
    # 调整（校验→入栈→低分先行重渲染）
    # ------------------------------------------------------------------
    def update_adjustment(self, name: str, params: dict) -> None:
        self._require_open()
        adjustment = AdjustmentFactory.create(name, params)  # 未注册/越界 → AdjustmentError
        self._session.append(adjustment)
        self._refresh_previews()

    def undo(self) -> None:
        self._require_open()
        self._session.undo()
        self._refresh_previews()

    def redo(self) -> None:
        self._require_open()
        self._session.redo()
        self._refresh_previews()

    # ------------------------------------------------------------------
    # 渲染（顺序应用指令链；空栈=原图，FR-016）
    # ------------------------------------------------------------------
    def render(self, level: RenderLevel = "full") -> Image.Image:
        self._require_open()
        if level not in ("thumb", "medium", "full"):
            raise ValueError(f"未知渲染级别: {level!r}（合法：thumb/medium/full）")
        cached = self._cache.get(self._session.version, level)
        if cached is not None:
            return cached
        image = self._render_level(level)
        self._cache.put(self._session.version, level, image)
        return image

    def _render_level(self, level: RenderLevel) -> Image.Image:
        image = self._asset.load()  # 空栈返回原图
        for adjustment in self._session.instructions:
            image = adjustment.apply(image, adjustment.params)
        if level == "full":
            return image
        max_side = THUMB_SIZE if level == "thumb" else MEDIUM_SIZE
        if max(image.size) <= max_side:
            return image.copy()
        preview = image.copy()
        preview.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        return preview

    # ------------------------------------------------------------------
    # 导出（委托 Exporter）
    # ------------------------------------------------------------------
    def export(self, path: str | Path, format: str = "jpeg") -> None:
        self._require_open()
        from pylightroom.core.exporter import Exporter

        Exporter.export(self, path, format)

    # ------------------------------------------------------------------
    # 渐进式预览（低分同步先行，高分后台补齐；FR-018/SC-005）
    # ------------------------------------------------------------------
    def _refresh_previews(self) -> None:
        version = self._session.version
        thumb_task = f"preview-thumb-v{version}"
        self._emit_progress(thumb_task, "render", 0.0)
        thumb = self.render("thumb")  # 低分同步先行，不被全图渲染阻塞
        self._emit_progress(thumb_task, "render", 1 / 3)
        self._emit_complete(thumb_task, thumb)
        self._bg_thread = threading.Thread(
            target=self._render_background, args=(version,), daemon=True
        )
        self._bg_thread.start()

    def _render_background(self, version: int) -> None:
        for index, level in enumerate(("medium", "full")):
            if self._session.version != version:
                return  # 会话已变更，本次高分渲染过期，丢弃
            task = f"preview-{level}-v{version}"
            try:
                image = self._render_level(level)
                self._cache.put(version, level, image)
                self._emit_progress(task, "render", (index + 2) / 3)
                self._emit_complete(task, image)
            except Exception as exc:  # 后台失败经事件通道报告，不炸线程
                self._emit_error(task, f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    # 事件出口（None 时静默，FR-024）
    # ------------------------------------------------------------------
    def _emit_progress(self, task_id: str, stage: str, fraction: float) -> None:
        if self._events is not None:
            self._events.on_progress(task_id, stage, fraction)

    def _emit_complete(self, task_id: str, image: Image.Image) -> None:
        if self._events is not None:
            self._events.on_render_complete(task_id, _encode_png(image))

    def _emit_error(self, task_id: str, message: str) -> None:
        if self._events is not None:
            self._events.on_error(task_id, message)

    def _require_open(self) -> None:
        if self._asset is None:
            raise AssetError("未打开任何图像：请先调用 open(path)")
