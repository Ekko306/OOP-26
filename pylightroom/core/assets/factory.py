"""AssetFactory：按扩展名分发（开闭扩展点，准则 IV / FR-009）。"""

from __future__ import annotations

from pathlib import Path

from pylightroom.core.assets.base import BaseImageAsset
from pylightroom.core.assets.raster import BmpAsset, JpegAsset, PngAsset, WebPAsset
from pylightroom.core.assets.raw import RawAsset
from pylightroom.core.errors import AssetError


class AssetFactory:
    """扩展名 → 资产子类注册表。"""

    _registry: dict[str, type[BaseImageAsset]] = {}

    @classmethod
    def create(cls, path: str | Path) -> BaseImageAsset:
        target = Path(path)
        extension = target.suffix.lower()
        asset_cls = cls._registry.get(extension)
        if asset_cls is None:
            raise AssetError(
                f"unsupported format: {extension!r}（{target}，"
                f"已注册：{sorted(cls._registry)}）",
                path=target,
                reason=f"扩展名 {extension!r} 无注册资产类型",
            )
        return asset_cls(target)

    @classmethod
    def register(
        cls, extensions: tuple[str, ...], asset_cls: type[BaseImageAsset]
    ) -> type[BaseImageAsset]:
        """注册扩展点：新增格式仅「新增子类 + 注册」（FR-026）。"""
        if not (isinstance(asset_cls, type) and issubclass(asset_cls, BaseImageAsset)):
            raise AssetError(f"register 仅接受 BaseImageAsset 子类，得到 {asset_cls!r}")
        for extension in extensions:
            normalized = extension.lower()
            if not normalized.startswith("."):
                normalized = f".{normalized}"
            cls._registry[normalized] = asset_cls
        return asset_cls

    @classmethod
    def registered_extensions(cls) -> list[str]:
        return sorted(cls._registry)


# 内置注册：JPEG/PNG/BMP/WebP + RAW（.ARW 主验收；.cr2/.nef/.dng/.orf/.rw2/.raf 尽力支持，research D4）
AssetFactory.register((".jpg", ".jpeg"), JpegAsset)
AssetFactory.register((".png",), PngAsset)
AssetFactory.register((".bmp",), BmpAsset)
AssetFactory.register((".webp",), WebPAsset)
AssetFactory.register((".arw", ".cr2", ".nef", ".dng", ".orf", ".rw2", ".raf"), RawAsset)
