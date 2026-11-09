"""上传与导出链路测试（T010/T016）：真实引擎 + 临时目录，无浏览器（research D2/D3）。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pylightroom.state import FileState
from pylightroom.ui.pages.index import UploadBroker


def exhaust(gen) -> None:
    for _ in gen:
        pass


class _FakeUpload:
    """starlette UploadFile 的最小替身（filename + async read）。"""

    def __init__(self, filename: str, data: bytes) -> None:
        self.filename = filename
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _StateCtx:
    """get_state 替身：包住给定实例的 async context manager。"""

    def __init__(self, state) -> None:
        self._state = state

    async def __aenter__(self):
        return self._state

    async def __aexit__(self, *exc_info) -> bool:
        return False


def _collect(coro):
    return asyncio.run(coro)


class TestUploadLink:
    def test_upload_saves_and_forwards_open_file(self, tmp_path, monkeypatch, png_sample):
        monkeypatch.chdir(tmp_path)
        broker = UploadBroker(_reflex_internal_init=True)
        # 白盒直调无 EventNamespace：把继承 handler 代理到 FileState 类事件（与运行时转发等价）
        monkeypatch.setattr(
            UploadBroker, "open_file", lambda self, path: FileState.open_file(path), raising=False
        )
        data = Path(png_sample).read_bytes()

        async def run():
            return [spec async for spec in broker.handle_upload([_FakeUpload("sample.png", data)])]

        specs = _collect(run())

        target = tmp_path / "uploaded_files" / "sample.png"
        assert target.exists(), "上传文件未落盘到 uploaded_files/<原文件名>"
        assert target.read_bytes() == data
        assert specs, "上传后未转发 open_file 事件"
        spec = specs[0]
        assert spec.handler.fn.__qualname__.endswith("open_file")
        assert "uploaded_files" in repr(spec.args) and "sample.png" in repr(spec.args)


class TestExportLink:
    def test_export_targets_fixed_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        shared = FileState(_reflex_internal_init=True)
        shared.file_name = "photo.png"
        monkeypatch.setattr(UploadBroker, "get_state", lambda self, cls: _StateCtx(shared))
        broker = UploadBroker(_reflex_internal_init=True)
        broker.export_format = "jpeg"

        async def run():
            return [spec async for spec in broker.handle_export()]

        specs = _collect(run())

        expected = tmp_path / "output" / "photo_edited.jpg"
        assert (tmp_path / "output").is_dir(), "output 目录未被创建"
        assert specs, "导出未产生事件"
        spec = specs[0]
        assert spec.handler.fn.__qualname__.endswith("export_file")
        assert "photo_edited.jpg" in repr(spec.args), f"拼接路径不符 D3：{spec.args!r}"
        assert '"jpeg"' in repr(spec.args)

    def test_export_png_extension(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        shared = FileState(_reflex_internal_init=True)
        shared.file_name = "photo.png"
        monkeypatch.setattr(UploadBroker, "get_state", lambda self, cls: _StateCtx(shared))
        broker = UploadBroker(_reflex_internal_init=True)
        broker.export_format = "png"

        async def run():
            return [spec async for spec in broker.handle_export()]

        specs = _collect(run())
        assert "photo_edited.png" in repr(specs[0].args)

    def test_real_export_writes_file(self, tmp_path, monkeypatch, jpeg_sample, file_state):
        """端到端：桥接层 export_file 真实导出到拼接路径（重名即覆盖，D3）。"""
        monkeypatch.chdir(tmp_path)
        exhaust(file_state.open_file(jpeg_sample))
        target = tmp_path / "output" / f"{Path(jpeg_sample).stem}_edited.jpg"
        (tmp_path / "output").mkdir(exist_ok=True)  # 目录创建由 handle_export 负责（已单测），此处对齐真实时序
        exhaust(file_state.export_file(str(target), "jpeg"))
        assert "sample_edited.jpg" in file_state.export_message, f"成功反馈应含完整保存位置：{file_state.export_message}"
        assert target.exists() and target.stat().st_size > 0
        # 重名覆盖：二次导出仍成功
        exhaust(file_state.export_file(str(target), "jpeg"))
        assert target.exists()
