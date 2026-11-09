"""核心引擎层端到端验证脚本（T047，quickstart §4 步骤 1–9 + §5 插件验证）。

运行：uv run python scripts/demo.py

- 全部样图程序化生成于系统临时目录，脚本结束自动清理
- 每步打印 PASS/FAIL/SKIP，任一步失败进程退出码非零
- 覆盖 SC-001（纯命令行全流程）、SC-005（低分预览先行）与 FR-012（原图字节不变）
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

# 独立脚本引导：把仓库根加入 sys.path，保证 `uv run python scripts/demo.py` 可直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pylightroom.core import (
    AdjustmentError,
    AdjustmentFactory,
    AssetFactory,
    BaseAdjustment,
    EditSession,
    HistoryError,
    HistogramCalculator,
    ImageProcessor,
    SidecarError,
    SidecarFile,
)
from pylightroom.core.adjustments.basic import BrightnessAdjustment

SAMPLE_WIDTH, SAMPLE_HEIGHT = 400, 300


class DemoEvents:
    """轻量事件记录器：捕获回调顺序，作为低分先行（SC-005）的证据。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.completed: list[str] = []

    def on_progress(self, task_id: str, stage: str, fraction: float) -> None:
        pass

    def on_render_complete(self, task_id: str, image_bytes: bytes) -> None:
        with self._lock:
            self.completed.append(task_id)

    def on_error(self, task_id: str, message: str) -> None:
        pass


def _pixel_equal(a: Image.Image, b: Image.Image) -> bool:
    if a.size != b.size:
        return False
    return ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is None


def _generate_sample(path: Path) -> None:
    """程序化生成验证用 JPEG：对角渐变（含亮区，保证合并语义可判别）。"""
    img = Image.new("RGB", (SAMPLE_WIDTH, SAMPLE_HEIGHT))
    px = img.load()
    for y in range(SAMPLE_HEIGHT):
        for x in range(SAMPLE_WIDTH):
            px[x, y] = (
                x * 255 // SAMPLE_WIDTH,
                (x + y) * 255 // (SAMPLE_WIDTH + SAMPLE_HEIGHT),
                y * 255 // SAMPLE_HEIGHT,
            )
    img.save(path, "JPEG", quality=95)


def _wait_full_completed(events: DemoEvents, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(task_id.startswith("preview-full") for task_id in events.completed):
            return True
        time.sleep(0.02)
    return False


def _expect(exc_type: type[Exception], func) -> bool:
    try:
        func()
    except exc_type:
        return True
    return False


def main() -> int:
    results: list[tuple[str, str]] = []

    def record(title: str, ok: bool, detail: str = "", *, skip: bool = False) -> None:
        mark = "SKIP" if skip else ("PASS" if ok else "FAIL")
        results.append((title, mark))
        print(f"[{mark}] {title}" + (f" —— {detail}" if detail else ""))

    workspace = Path(tempfile.mkdtemp(prefix="pylightroom-demo-"))
    sample = workspace / "sample.jpg"
    _generate_sample(sample)
    original_hash = hashlib.sha256(sample.read_bytes()).hexdigest()
    original = AssetFactory.create(sample).load()
    print(f"工作目录: {workspace}")
    print(f"样图: sample.jpg {original.size[0]}x{original.size[1]} (JPEG)\n")

    events = DemoEvents()
    processor = ImageProcessor(events=events)
    try:
        # 步骤 1：加载
        processor.open(sample)
        record(
            "1 加载",
            processor.version == 0,
            f"open(sample.jpg) 无异常，version={processor.version}",
        )

        # 步骤 2：调整（低分预览先行，SC-005）
        processor.update_adjustment("brightness", {"factor": 1.3})
        thumb_first = bool(events.completed) and events.completed[0].startswith("preview-thumb")
        ok = thumb_first and _wait_full_completed(events)
        order = [task_id.rsplit("-v", 1)[0] for task_id in events.completed]
        record("2 调整·低分先行", ok, "回调顺序: " + " → ".join(order))

        # 步骤 3：同类合并（指令数保持 1，后值覆盖）
        processor.update_adjustment("brightness", {"factor": 1.5})
        processor.undo()  # 只弹一条：若未合并，栈内仍余 brightness(1.3)
        merged_single = _pixel_equal(processor.render("full"), original)
        processor.redo()
        after_redo = _pixel_equal(
            processor.render("full"),
            BrightnessAdjustment({"factor": 1.5}).apply(original, {"factor": 1.5}),
        )
        record(
            "3 同类合并",
            merged_single and after_redo,
            "undo 一步即回原图（指令数=1）；redo 后与单独应用 1.5 像素一致",
        )

        # 步骤 4：撤销/重做
        processor.undo()
        empty_is_original = _pixel_equal(processor.render("full"), original)
        boundary_ok = _expect(HistoryError, processor.undo)
        processor.redo()
        restored = _pixel_equal(
            processor.render("full"),
            BrightnessAdjustment({"factor": 1.5}).apply(original, {"factor": 1.5}),
        )
        record(
            "4 撤销/重做",
            empty_is_original and boundary_ok and restored,
            "undo→空栈=原图；空栈再 undo 抛 HistoryError；redo 恢复",
        )

        # 步骤 5：直方图
        hist = HistogramCalculator.compute(processor.render("full"))
        channels = ("r", "g", "b")
        hist_ok = (
            set(hist) == set(channels)
            and all(len(hist[ch]) == 256 for ch in channels)
            and sum(sum(hist[ch]) for ch in channels) == SAMPLE_WIDTH * SAMPLE_HEIGHT * 3
        )
        record("5 直方图", hist_ok, "r/g/b 各 256 bin，计数总和 = 400×300×3")

        # 步骤 6：导出 + Sidecar
        out = workspace / "out.png"
        processor.export(out, "png")
        sidecar = SidecarFile.sidecar_path_for(sample)
        with Image.open(out) as exported:
            exported.load()
            export_ok = _pixel_equal(
                exported,
                BrightnessAdjustment({"factor": 1.5}).apply(original, {"factor": 1.5}),
            )
        ok = (
            out.is_file()
            and sidecar.is_file()
            and not out.with_suffix(".json").exists()
            and export_ok
        )
        record(
            "6 导出+Sidecar",
            ok,
            "out.png 生成、sample.json 更新、成品目录无 out.json、像素=逐条手工应用",
        )

        # 步骤 7：会话恢复
        saved = json.loads(sidecar.read_text(encoding="utf-8"))
        session = EditSession(image_path=sample)
        SidecarFile.load(sample, session)
        reloaded = [item.serialize() for item in session.instructions]
        ok = (
            reloaded == saved["instructions"]
            and len(session.instructions) == 1
            and session.instructions[0].params["factor"] == 1.5
        )
        record("7 会话恢复", ok, "新会话加载 sample.json：type+params 逐条一致")

        # 步骤 8：RAW（可选，样片缺失时 SKIP）
        raw_path = os.environ.get("PYLIGHTROOM_ARW_SAMPLE", "")
        if raw_path and Path(raw_path).is_file():
            raw_processor = ImageProcessor()
            raw_processor.open(raw_path)
            raw_processor.update_adjustment("brightness", {"factor": 1.3})
            rendered = raw_processor.render("full")
            record(
                "8 RAW 同管线",
                rendered.mode == "RGB" and rendered.size[0] > 0,
                f"{Path(raw_path).name} 经同一管线渲染 "
                f"{rendered.size[0]}x{rendered.size[1]} (RGB)",
            )
        else:
            record("8 RAW 同管线", True, "未设置 PYLIGHTROOM_ARW_SAMPLE（见 T045）", skip=True)

        # 步骤 9：异常路径
        ok = (
            _expect(
                AdjustmentError,
                lambda: processor.update_adjustment("ghost-filter", {"factor": 1.2}),
            )
            and _expect(
                AdjustmentError,
                lambda: processor.update_adjustment("brightness", {"factor": 2.5}),
            )
        )
        corrupt_image = workspace / "corrupt.jpg"
        corrupt_image.touch()
        corrupt_image.with_suffix(".json").write_text("{ not valid json", encoding="utf-8")
        ok = ok and _expect(
            SidecarError,
            lambda: SidecarFile.load(corrupt_image, EditSession(image_path=corrupt_image)),
        )
        record(
            "9 异常路径",
            ok,
            "未知调整名/越界参数 → AdjustmentError；损坏 JSON → SidecarError；进程未崩溃",
        )

        # 步骤 10（§5）：开闭原则插件验证
        class VignetteAdjustment(BaseAdjustment):
            name = "vignette"
            param_schema = {"factor": {"min": 0.0, "max": 2.0, "default": 1.0}}

            def apply(self, image: Image.Image, params: dict) -> Image.Image:
                if params["factor"] <= 1.0:
                    return image.copy()  # 1.0 中性
                width, height = image.size
                inset_x = int(width * 0.12 * (params["factor"] - 1.0))
                inset_y = int(height * 0.12 * (params["factor"] - 1.0))
                # 亮区=椭圆内（mask 255 保留原图），椭圆外四角变黑 → 暗角
                mask = Image.new("L", (width, height), 0)
                ImageDraw.Draw(mask).ellipse(
                    (inset_x, inset_y, width - inset_x, height - inset_y), fill=255
                )
                black = Image.new("RGB", (width, height), (0, 0, 0))
                return Image.composite(image, black, mask)

        AdjustmentFactory.register(VignetteAdjustment)
        before = processor.render("full")
        processor.update_adjustment("vignette", {"factor": 1.6})
        after = processor.render("full")
        record(
            "10 插件注册（§5）",
            after.size == before.size and not _pixel_equal(after, before),
            "VignetteAdjustment 定义于脚本内部，仅 register() 即可用于管线，存量文件零改动",
        )

        # 步骤 11：原图字节不变（FR-012）
        final_hash = hashlib.sha256(sample.read_bytes()).hexdigest()
        record(
            "11 原图不可变（FR-012）",
            final_hash == original_hash,
            "SHA-256 前后一致：原始图片文件字节未变",
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    passed = sum(1 for _, mark in results if mark == "PASS")
    skipped = sum(1 for _, mark in results if mark == "SKIP")
    failed = sum(1 for _, mark in results if mark == "FAIL")
    print(f"\n结果: {passed} PASS / {skipped} SKIP / {failed} FAIL")
    print("DEMO ALL PASS" if failed == 0 else "DEMO FAILED")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
