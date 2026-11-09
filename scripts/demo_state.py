"""桥接层端到端冒烟（quickstart §4，无浏览器）：打开 → 滑块 → 撤销 → 导出 → 错误路径。

运行：uv run python scripts/demo_state.py    预期输出 SMOKE ALL PASS
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from pylightroom.state import session as session_module
from pylightroom.state.file_state import FileState


def _exhaust(events) -> None:
    for _ in events:
        pass


def _make_sample(directory: Path) -> Path:
    image = Image.new("RGB", (400, 300))
    px = image.load()
    for y in range(300):
        for x in range(400):
            px[x, y] = (x % 256, y % 256, (x + y) % 256)
    path = directory / "smoke.png"
    image.save(path, "PNG")
    return path


def main() -> int:
    session_module.set_session(None)
    state = FileState(_reflex_internal_init=True)
    session = session_module.get_session()

    with tempfile.TemporaryDirectory() as tmp:
        sample = _make_sample(Path(tmp))

        # 1. 打开链路：渐进预览、直方图 256 bin、默认值、文件名
        _exhaust(state.open_file(str(sample)))
        assert state.has_image and state.file_name == "smoke.png"
        assert state.preview_data_url.startswith("data:image/png;base64,")
        assert len(state.histogram) == 3 and all(
            len(bins) == 256 for bins in state.histogram.values()
        )
        assert state.adjustment_values["brightness"] == {"factor": 1.0}
        assert state.adjustment_schemas, "schemas 应来自注册表"
        print("[1/6] open_file 链路 OK")

        # 2. 滑块：低分先行 → full 替换，参数与值同步
        full_before = state.preview_data_url
        frames = []
        for _ in state.on_slider_change("brightness", 1.5):
            frames.append(state.preview_data_url)
        assert frames and frames[0] != full_before
        assert state.preview_data_url == "data:image/png;base64," + _png_b64(
            session.processor.render("full")
        )
        assert session.processor.current_params() == {"brightness": {"factor": 1.5}}
        assert state.busy is False
        print("[2/6] on_slider_change 渐进更新 OK")

        # 3. 快速连发：新者胜，终态收敛最后值
        _exhaust(state.on_slider_change("brightness", 1.2))
        _exhaust(state.on_slider_change("brightness", 1.8))
        assert session.processor.current_params() == {"brightness": {"factor": 1.8}}
        print("[3/6] 快速连发收敛 OK")

        # 4. 撤销：连续同名滑块为同一合并段（001 契约），一次 undo 整段回退
        _exhaust(state.undo())
        assert session.processor.current_params() == {}
        assert state.adjustment_values["brightness"] == {"factor": 1.0}  # 默认回补
        _exhaust(state.redo())
        current = session.processor.current_params()
        assert current == {"brightness": {"factor": 1.8}}
        assert all(
            state.adjustment_values[name] == params
            for name, params in current.items()
        )  # 生效名逐项一致（缺席名按 schema 默认回补）
        print("[4/6] undo/redo 同步 OK")

        # 5. 导出：成品 + Sidecar + 成功消息
        out = Path(tmp) / "smoke-out.jpg"
        _exhaust(state.export_file(str(out)))
        assert out.is_file() and state.export_message.startswith("已导出")
        assert state.exporting is False
        print("[5/6] export_file 成功路径 OK")

        # 6. 错误路径：不支持格式打开 → 可读错误，既有视图保持；错误后恢复正常
        good_view = (state.preview_data_url, state.file_name)
        _exhaust(state.open_file(str(Path(tmp) / "missing.tiff")))
        assert state.error_message != ""
        assert (state.preview_data_url, state.file_name) == good_view
        _exhaust(state.on_slider_change("brightness", 1.3))  # 错误后恢复正常
        assert state.error_message == ""
        print("[6/6] 错误隔离与恢复 OK")

    session_module.set_session(None)
    print("SMOKE ALL PASS")
    return 0


def _png_b64(image: Image.Image) -> str:
    import base64
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


if __name__ == "__main__":
    raise SystemExit(main())
