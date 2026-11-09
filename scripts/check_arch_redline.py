"""架构红线检查：pylightroom/core/ 全部 .py 不得引用界面框架（准则 I，FR 核心约束）。

用法：uv run python scripts/check_arch_redline.py
退出码 0 = PASS；1 = 违规（打印违例明细）。M4 验收 CI 断言对象。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# 准则 I：界面框架与 Web 框架一律禁止出现在 core 导入链
FORBIDDEN_MODULES = ("reflex",)
# 匹配 import 语句与 from ... import；reflex.var 反射调用同样视为引用
IMPORT_PATTERN = re.compile(
    r"^\s*(?:import|from)\s+(?P<module>[\w.]+)", re.MULTILINE
)
ATTRIBUTE_PATTERN = re.compile(r"\breflex\s*\.")

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / "pylightroom" / "core"


def check() -> list[str]:
    violations: list[str] = []
    for py_file in sorted(CORE_DIR.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        for match in IMPORT_PATTERN.finditer(source):
            root_module = match.group("module").split(".")[0]
            if root_module in FORBIDDEN_MODULES:
                line_no = source[: match.start()].count("\n") + 1
                violations.append(
                    f"{py_file.relative_to(REPO_ROOT)}:{line_no}: import {match.group('module')}"
                )
        for match in ATTRIBUTE_PATTERN.finditer(source):
            line_no = source[: match.start()].count("\n") + 1
            violations.append(
                f"{py_file.relative_to(REPO_ROOT)}:{line_no}: 属性引用 reflex.*"
            )
    return violations


def main() -> int:
    violations = check()
    if violations:
        print("FAIL — 架构红线违规（core 引用了界面框架）：")
        for item in violations:
            print(f"  {item}")
        return 1
    scanned = len(list(CORE_DIR.rglob("*.py")))
    print(f"PASS — pylightroom/core/ 共 {scanned} 个文件，零界面框架引用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
