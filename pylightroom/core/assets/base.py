"""BaseImageAsset 抽象基类：资产族契约（继承体系二，准则 II）。

load() 为模板方法：统一异常包装（→ AssetError，FR-011）与结果缓存；
子类只实现 _decode()，返回统一 Pillow RGB 表示（FR-008，research D2）。
thumbnail() 提供三级预览：256px / 1024px / 全图（FR-010，D5）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image

from pylightroom.core.errors import AssetError

THUMB_SIZE = 256
MEDIUM_SIZE = 1024


class BaseImageAsset(ABC):
    """一张被编辑的图：路径、格式、元数据与多级预览。"""

    format: str = "UNKNOWN"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.exif: dict = {}
        self._decoded: Image.Image | None = None

    # ------------------------------------------------------------------
    # 模板方法：异常包装 + 缓存
    # ------------------------------------------------------------------
    def load(self) -> Image.Image:
        if self._decoded is None:
            try:
                image = self._decode()
            except AssetError:
                raise
            except Exception as exc:  # 统一包装为格式化异常（含路径与原因，FR-011）
                raise AssetError(
                    f"图像解码失败: {self.path}",
                    path=self.path,
                    reason=f"{type(exc).__name__}: {exc}",
                ) from exc
            if not isinstance(image, Image.Image):
                raise AssetError(
                    f"图像解码失败: {self.path}",
                    path=self.path,
                    reason=f"_decode 返回了非法类型 {type(image).__name__}",
                )
            self._decoded = image
            self.exif = self._build_exif(image)
        return self._decoded

    def _build_exif(self, image: Image.Image) -> dict:
        """元数据：尺寸、格式、拍摄时间（可得时）。"""
        metadata: dict = {"size": image.size, "format": self.format}
        datetime_original = getattr(self, "_captured_at", None)
        if datetime_original:
            metadata["datetime"] = datetime_original
        return metadata

    @abstractmethod
    def _decode(self) -> Image.Image:
        """子类实现：解码并返回统一 Pillow RGB 表示。"""

    # ------------------------------------------------------------------
    # 三级预览（FR-010）
    # ------------------------------------------------------------------
    def thumbnail(self) -> dict[str, Image.Image]:
        base = self.load()
        return {
            "thumb": self._downscale(base, THUMB_SIZE),
            "medium": self._downscale(base, MEDIUM_SIZE),
            "full": base,
        }

    @staticmethod
    def _downscale(image: Image.Image, max_side: int) -> Image.Image:
        """不放大：小图直接返回副本。"""
        if max(image.size) <= max_side:
            return image.copy()
        preview = image.copy()
        preview.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        return preview
