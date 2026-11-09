"""Exporter：全图渲染 → 成品 + 原图关联 Sidecar（US5，D9）。

顺序：渲染全图 → 持久化 Sidecar → 写临时文件 → 原子 os.replace。
任一步失败清理临时文件并抛 ExportError，不留半成品（FR-020）。
Sidecar 持久化到原图关联路径（photo.jpg → photo.json），成品自身不生成（FR-019/FR-021）。
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

from pylightroom.core.errors import ExportError

_FORMATS = {"jpeg": "JPEG", "png": "PNG"}
_JPEG_QUALITY = 95


class Exporter:
    """消费渲染结果写出成品文件与参数文件。"""

    @staticmethod
    def export(processor, path: str | Path, format: str = "jpeg") -> None:
        from pylightroom.core.persistence import SidecarFile  # 延迟导入避免循环依赖

        pil_format = _FORMATS.get(str(format).lower())
        if pil_format is None:
            raise ExportError(
                f"unsupported export format: {format!r}（合法：jpeg/png）",
                path=path,
                reason="格式不在支持列表",
            )
        target = Path(path)
        tmp_path = target.with_name(target.name + ".tmp")
        try:
            image: Image.Image = processor.render("full")
            SidecarFile.save(processor._session)  # 先持久化会话（原图关联 Sidecar）
            save_kwargs = {"quality": _JPEG_QUALITY} if pil_format == "JPEG" else {}
            image.save(tmp_path, format=pil_format, **save_kwargs)
            os.replace(tmp_path, target)  # 同目录原子替换（D9）
        except ExportError:
            tmp_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            tmp_path.unlink(missing_ok=True)  # 失败清理，不留半成品（FR-020）
            raise ExportError(
                f"导出失败: {target}",
                path=target,
                reason=f"{type(exc).__name__}: {exc}",
            ) from exc
