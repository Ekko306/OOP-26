"""SidecarFile：编辑会话的持久化（JSON v1 协议，US4）。

- 命名规则：同主名换扩展名（photo.jpg → photo.json，Clarifications Q4）
- 写：会话整体序列化，先写临时文件再原子 os.replace（FR-020/D9）
- 读：逐条经 AdjustmentFactory 重建；任一失败整体失败、会话保持原状（FR-022）
- Sidecar 路径与 JSON image_path 均取自 session.image_path；
  session.image_path 为 None 时抛 SidecarError（不可持久化）
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pylightroom.core.adjustments.factory import AdjustmentFactory
from pylightroom.core.errors import SidecarError
from pylightroom.core.history import EditSession

PROTOCOL_VERSION = 1


class SidecarFile:
    """「类型标识 + 参数字典」协议（sidecar-schema.md）的读写门面。"""

    # ------------------------------------------------------------------
    # 命名规则
    # ------------------------------------------------------------------
    @staticmethod
    def sidecar_path_for(image_path: str | Path) -> Path:
        return Path(image_path).with_suffix(".json")

    # ------------------------------------------------------------------
    # 写（原子）
    # ------------------------------------------------------------------
    @staticmethod
    def save(session: EditSession) -> Path:
        if session.image_path is None:
            raise SidecarError("会话未关联原图（image_path 为 None），不可持久化")
        target = SidecarFile.sidecar_path_for(session.image_path)
        payload = {
            "version": PROTOCOL_VERSION,
            "image_path": str(session.image_path),
            "instructions": [adjustment.serialize() for adjustment in session.instructions],
        }
        tmp_path = target.with_name(target.name + ".tmp")
        try:
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp_path, target)  # 同目录原子替换（D9）
        except OSError as exc:
            tmp_path.unlink(missing_ok=True)  # 失败清理，不残留半成品
            raise SidecarError(
                f"Sidecar 写入失败: {target}",
                path=target,
                reason=f"{type(exc).__name__}: {exc}",
            ) from exc
        return target

    # ------------------------------------------------------------------
    # 读（整体失败保持原状）
    # ------------------------------------------------------------------
    @staticmethod
    def load(image_path: str | Path, session: EditSession) -> None:
        target = SidecarFile.sidecar_path_for(image_path)
        try:
            raw_text = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise SidecarError(
                f"Sidecar 不可读: {target}",
                path=target,
                reason=f"{type(exc).__name__}: {exc}",
            ) from exc
        try:
            data = json.loads(raw_text)
        except (json.JSONDecodeError, ValueError) as exc:
            raise SidecarError(
                f"Sidecar 已损坏（非法 JSON）: {target}",
                path=target,
                reason=f"{type(exc).__name__}: {exc}",
            ) from exc
        if not isinstance(data, dict):
            raise SidecarError(
                f"Sidecar 顶层必须为对象: {target}", path=target, reason="结构非法"
            )
        version = data.get("version")
        if not isinstance(version, int) or version > PROTOCOL_VERSION or version < 1:
            raise SidecarError(
                f"Sidecar 协议版本不识别: {version!r}（当前支持 1）",
                path=target,
                reason="前向拒绝",
            )
        instructions_data = data.get("instructions")
        if not isinstance(instructions_data, list):
            raise SidecarError(
                f"Sidecar instructions 必须为数组: {target}",
                path=target,
                reason="结构非法",
            )

        # 先整体重建，任一失败则不触碰会话（sidecar-schema：不留半恢复状态）
        rebuilt: list = []
        for index, item in enumerate(instructions_data):
            if not isinstance(item, dict) or "type" not in item or "params" not in item:
                raise SidecarError(
                    f"Sidecar 指令 #{index} 结构非法: {item!r}",
                    path=target,
                    reason="缺 type 或 params",
                )
            try:
                rebuilt.append(AdjustmentFactory.create(item["type"], item["params"]))
            except Exception as exc:
                raise SidecarError(
                    f"Sidecar 指令 #{index} 重建失败: {item.get('type')!r}",
                    path=target,
                    reason=str(exc),
                ) from exc

        session.instructions.clear()
        session._undo_stack.clear()
        session._redo_stack.clear()
        session.instructions.extend(rebuilt)
        session._version += 1  # 会话状态变更，缓存失效判定随之更新（FR-017）
