"""T020/T025：架构红线测试——层间依赖静态断言（FR-014/SC-007，quickstart §3）。

纯 Python + AST 遍历源码（不 import 被检模块），可进 CI：
- 准则 I / FR-014：core/ 零 UI 框架（reflex）
- SC-007：reflex 引用仅存在于 state/（唯一例外层）
- D7 / FR-016：state/ 零重型图像库（PIL/cv2/rawpy）
"""

from __future__ import annotations

import ast
from pathlib import Path

PYLIGHTROOM = Path(__file__).resolve().parents[2] / "pylightroom"

UI_FRAMEWORKS = {"reflex"}
HEAVY_IMAGE_LIBS = {"PIL", "cv2", "rawpy"}


def _imported_roots(path: Path) -> set[str]:
    """AST 解析单文件全部 import 的顶层包名（含函数内/try 块导入）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _sources(relative: str) -> list[Path]:
    return sorted((PYLIGHTROOM / relative).rglob("*.py"))


def test_core_never_imports_ui_framework():
    """准则 I / FR-014：核心引擎层零界面框架依赖（含惰性导入链上的直接 import）。"""
    offenders = [
        str(path) for path in _sources("core") if _imported_roots(path) & UI_FRAMEWORKS
    ]
    assert offenders == [], f"core/ 出现 UI 框架导入: {offenders}"


def test_reflex_confined_to_state_layer():
    """SC-007：reflex 仅可被 state/ 引用（桥接层是唯一例外）。"""
    state_dir = PYLIGHTROOM / "state"
    offenders = [
        str(path)
        for path in sorted(PYLIGHTROOM.rglob("*.py"))
        if _imported_roots(path) & UI_FRAMEWORKS and state_dir not in path.parents
    ]
    assert offenders == [], f"state/ 之外出现 reflex 导入: {offenders}"


def test_state_has_no_heavy_image_libs():
    """D7 / FR-016：桥接层只做胶水，不触碰重型图像库（直方图亦经引擎 D7）。"""
    offenders = [
        str(path)
        for path in _sources("state")
        if _imported_roots(path) & HEAVY_IMAGE_LIBS
    ]
    assert offenders == [], f"state/ 出现重型图像库导入: {offenders}"
