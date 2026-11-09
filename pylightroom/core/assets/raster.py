"""栅格资产：JPEG/PNG/BMP/WebP（Pillow 直读，research D2）。

PNG 含透明通道时解码为统一 RGB 表示并合成白底（core-api §4）。
"""

from __future__ import annotations

from PIL import Image

from pylightroom.core.assets.base import BaseImageAsset


class _RasterAsset(BaseImageAsset):
    """Pillow 可直读的栅格格式的公共实现。"""

    pil_format: str = "UNKNOWN"

    def _decode(self) -> Image.Image:
        with Image.open(self.path) as img:
            img.load()
            self._captured_at = self._read_capture_time(img)
            return self._normalize(img)

    def _normalize(self, img: Image.Image) -> Image.Image:
        return img.convert("RGB")

    def _read_capture_time(self, img: Image.Image) -> str | None:
        try:
            exif = img.getexif()
        except Exception:  # 元数据缺失不影响主流程
            return None
        # 36867 = DateTimeOriginal；306 = DateTime
        return exif.get(36867) or exif.get(306)


class JpegAsset(_RasterAsset):
    format = "JPEG"
    pil_format = "JPEG"


class PngAsset(_RasterAsset):
    format = "PNG"
    pil_format = "PNG"

    def _normalize(self, img: Image.Image) -> Image.Image:
        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        )
        if not has_alpha:
            return img.convert("RGB")
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        return background


class BmpAsset(_RasterAsset):
    format = "BMP"
    pil_format = "BMP"


class WebPAsset(_RasterAsset):
    format = "WEBP"
    pil_format = "WEBP"
