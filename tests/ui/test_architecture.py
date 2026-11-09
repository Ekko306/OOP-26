"""架构红线 AST 静态断言（specs/003-ui-presentation-layer/contracts/ui-api.md §5）。

只扫描源码 AST，不 import 被检模块——被检代码违规时测试本身不受影响。
覆盖 SC-005/SC-006/SC-007 的 CI 证据（ui 侧五条规则）。
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYLIGHTROOM_DIR = REPO_ROOT / "pylightroom"
UI_DIR = PYLIGHTROOM_DIR / "ui"
COMPONENTS_DIR = UI_DIR / "components"
PAGES_DIR = UI_DIR / "pages"
RXCONFIG = REPO_ROOT / "rxconfig.py"

IMAGE_LIB_TOPLEVELS = {"PIL", "cv2", "rawpy"}


def _py_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py")) if directory.exists() else []


def _import_specs(path: Path) -> set[str]:
    """返回该文件的 import 目标模块名集合（含 `from X import Y` 中的 Y 作为 'X:Y' 项）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    specs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                specs.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                specs.add(node.module)
            for alias in node.names:
                specs.add(f"{node.module or ''}:{alias.name}")
    return specs


def _violations(files: list[Path], predicate) -> dict[str, set[str]]:
    """对每个文件求 import 集合的谓词，返回 {文件: 违规 import 集}。"""
    result: dict[str, set[str]] = {}
    for path in files:
        bad = predicate(_import_specs(path))
        if bad:
            result[str(path.relative_to(REPO_ROOT))] = bad
    return result


def _toplevel(module: str) -> str:
    return module.split(":")[0].split(".")[0]


def _is_pylightroom_submodule(module: str, sub: str) -> bool:
    """匹配 pylightroom.<sub>（import 直接式或 from X import Y 别名式）。"""
    return module == f"pylightroom.{sub}" or module.startswith(f"pylightroom.{sub}.") or module.endswith(f":{sub}")


# ---------------------------------------------------------------------------
# 规则 ①：ui/ 零图像处理库
# ---------------------------------------------------------------------------


def test_ui_imports_no_image_processing_library():
    violations = _violations(
        _py_files(UI_DIR),
        lambda specs: {s for s in specs if _toplevel(s) in IMAGE_LIB_TOPLEVELS},
    )
    assert not violations, f"ui/ 出现图像处理库 import：{violations}"


# ---------------------------------------------------------------------------
# 规则 ②：ui/ 零 pylightroom.core 直引
# ---------------------------------------------------------------------------


def test_ui_imports_no_core():
    violations = _violations(
        _py_files(UI_DIR),
        lambda specs: {
            s for s in specs if s == "pylightroom.core" or s.startswith("pylightroom.core.") or s.endswith(":core")
        },
    )
    assert not violations, f"ui/ 直引核心引擎：{violations}"


# ---------------------------------------------------------------------------
# 规则 ③：components/ 零 pylightroom.state import（哑组件）
# ---------------------------------------------------------------------------


def test_components_import_no_state():
    violations = _violations(
        _py_files(COMPONENTS_DIR),
        lambda specs: {s for s in specs if _is_pylightroom_submodule(s, "state")},
    )
    assert not violations, f"components/ 出现桥接层 import：{violations}"


# ---------------------------------------------------------------------------
# 规则 ④：import reflex 仅存在于 state/、ui/ 与 rxconfig.py（plan D6 配置文件）
# ---------------------------------------------------------------------------


def test_reflex_import_confined_to_state_ui_and_rxconfig():
    allowed_prefixes = ("pylightroom/state", "pylightroom/ui", "rxconfig.py")
    violations: dict[str, set[str]] = {}
    for path in _py_files(PYLIGHTROOM_DIR) + ([RXCONFIG] if RXCONFIG.exists() else []):
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        if rel.startswith(allowed_prefixes):
            continue
        bad = {s for s in _import_specs(path) if _toplevel(s) == "reflex"}
        if bad:
            violations[rel] = bad
    assert not violations, f"reflex import 越出 state/ui/rxconfig：{violations}"


# ---------------------------------------------------------------------------
# 规则 ⑤：UI 侧引用 pylightroom.state 的模块仅 pages/index.py
# ---------------------------------------------------------------------------


def test_state_import_in_ui_confined_to_index_page():
    violations = _violations(
        _py_files(UI_DIR),
        lambda specs: {s for s in specs if _is_pylightroom_submodule(s, "state")},
    )
    unexpected = {f: mods for f, mods in violations.items() if not f.replace("\\", "/").endswith("pages/index.py")}
    assert not unexpected, f"pylightroom.state 被 index.py 以外的 UI 模块引用：{unexpected}"
