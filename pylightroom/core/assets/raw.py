"""RawAsset：rawpy 解码管线（research D4）。

rawpy.imread → postprocess(use_camera_wb=True) → 8bit RGB numpy → Pillow RGB。
失败抛含路径与原因的 AssetError（FR-011）；.ARW 主验收，其余 RAW 尽力支持。
"""

from __future__ import annotations

from PIL import Image

from pylightroom.core.assets.base import BaseImageAsset
from pylightroom.core.errors import AssetError


class RawAsset(BaseImageAsset):
    format = "RAW"

    def _decode(self) -> Image.Image:
        try:
            import rawpy
        except ImportError as exc:  # 依赖缺失也是解码失败的一种
            raise AssetError(
                f"RAW 解码失败: {self.path}",
                path=self.path,
                reason=f"rawpy 不可导入: {exc}",
            ) from exc
        try:
            with rawpy.imread(str(self.path)) as raw:
                rgb8 = raw.postprocess(use_camera_wb=True, output_bps=8)
        except AssetError:
            raise
        except Exception as exc:
            raise AssetError(
                f"RAW 解码失败: {self.path}",
                path=self.path,
                reason=f"{type(exc).__name__}: {exc}",
            ) from exc
        return Image.fromarray(rgb8, mode="RGB").convert("RGB")
