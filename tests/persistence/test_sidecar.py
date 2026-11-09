"""US4 Sidecar 持久化测试：命名规则、往返无损、损坏/未知类型/版本、原子写（FR-020–FR-022）。"""

from __future__ import annotations

import json

import pytest

from pylightroom.core.adjustments.basic import BrightnessAdjustment, ContrastAdjustment
from pylightroom.core.adjustments.geometry import CropAdjustment, RotateAdjustment
from pylightroom.core.errors import SidecarError
from pylightroom.core.history import EditSession
from pylightroom.core.persistence import SidecarFile


@pytest.fixture
def session(tmp_path):
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"fake-original-bytes")  # 原图占位，永不被写入
    session = EditSession(image_path=image_path)
    session.append(BrightnessAdjustment({"factor": 1.3}))
    session.append(ContrastAdjustment({"factor": 0.9}))
    return session


class TestNamingRule:
    def test_same_stem_new_extension(self):
        assert SidecarFile.sidecar_path_for("photo.jpg") == SidecarFile.sidecar_path_for(
            "photo.jpg"
        )
        assert str(SidecarFile.sidecar_path_for("photo.jpg")).endswith("photo.json")

    def test_various_extensions(self):
        assert SidecarFile.sidecar_path_for("a/b/img.arw").name == "img.json"
        assert SidecarFile.sidecar_path_for("noext").name == "noext.json"
        assert SidecarFile.sidecar_path_for("x.jpeg").name == "x.json"

    def test_save_writes_beside_original(self, session):
        target = SidecarFile.save(session)
        assert target.name == "photo.json"
        assert target.parent == session.image_path.parent


class TestSaveContent:
    def test_json_protocol_v1(self, session):
        target = SidecarFile.save(session)
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert data["image_path"] == str(session.image_path)
        assert data["instructions"] == [
            {"type": "brightness", "params": {"factor": 1.3}},
            {"type": "contrast", "params": {"factor": 0.9}},
        ]

    def test_original_file_untouched(self, session):
        before = session.image_path.read_bytes()
        SidecarFile.save(session)
        assert session.image_path.read_bytes() == before, "原图永不写入（FR-021）"

    def test_save_without_image_path_raises(self):
        with pytest.raises(SidecarError):
            SidecarFile.save(EditSession())

    def test_overwrite_existing_no_tmp_left(self, session):
        """同名参数文件已存在：保存覆盖旧文件且不残留临时文件（Edge Cases）。"""
        SidecarFile.save(session)
        session.append(RotateAdjustment({"angle": 90}))
        target = SidecarFile.save(session)
        data = json.loads(target.read_text(encoding="utf-8"))
        assert len(data["instructions"]) == 3, "覆盖保存应包含全部 3 条指令"
        leftovers = [p.name for p in target.parent.iterdir() if p.suffix == ".tmp"]
        assert leftovers == []


class TestRoundTrip:
    def test_full_round_trip_instruction_identical(self, session):
        SidecarFile.save(session)
        restored = EditSession()
        SidecarFile.load(session.image_path, restored)
        assert len(restored.instructions) == len(session.instructions)
        for before, after in zip(session.instructions, restored.instructions):
            assert before.serialize() == after.serialize(), "逐条 type+params 完全一致（SC-002）"

    def test_round_trip_with_geometry(self, session):
        session.append(CropAdjustment({"box": (1, 2, 30, 20)}))
        session.append(RotateAdjustment({"angle": 45.5}))
        SidecarFile.save(session)
        restored = EditSession()
        SidecarFile.load(session.image_path, restored)
        assert restored.instructions[-1].params["angle"] == 45.5
        assert restored.instructions[-2].params["box"] == (1.0, 2.0, 30.0, 20.0)

    def test_load_clears_existing_session_state(self, session):
        SidecarFile.save(session)
        fresh = EditSession()
        fresh.append(RotateAdjustment({"angle": 10}))
        SidecarFile.load(session.image_path, fresh)
        assert [a.name for a in fresh.instructions] == ["brightness", "contrast"]


class TestLoadFailures:
    def test_corrupted_json_raises(self, session):
        SidecarFile.save(session)
        sidecar = SidecarFile.sidecar_path_for(session.image_path)
        sidecar.write_text("{broken json!!", encoding="utf-8")
        restored = EditSession()
        restored.append(RotateAdjustment({"angle": 10}))
        with pytest.raises(SidecarError):
            SidecarFile.load(session.image_path, restored)
        # 失败时会话保持原状（sidecar-schema 读写规则）
        assert [a.name for a in restored.instructions] == ["rotate"]

    def test_unknown_type_raises_not_silently_dropped(self, session):
        SidecarFile.save(session)
        sidecar = SidecarFile.sidecar_path_for(session.image_path)
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data["instructions"].append({"type": "vignette", "params": {"factor": 1.2}})
        sidecar.write_text(json.dumps(data), encoding="utf-8")
        restored = EditSession()
        with pytest.raises(SidecarError):
            SidecarFile.load(session.image_path, restored)
        assert restored.instructions == [], "整体失败，不留半恢复状态"

    def test_higher_version_rejected(self, session):
        SidecarFile.save(session)
        sidecar = SidecarFile.sidecar_path_for(session.image_path)
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data["version"] = 2
        sidecar.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(SidecarError):
            SidecarFile.load(session.image_path, EditSession())

    def test_missing_file_raises(self, tmp_path):
        ghost = tmp_path / "ghost.jpg"
        ghost.write_bytes(b"x")
        with pytest.raises(SidecarError):
            SidecarFile.load(ghost, EditSession())


class TestAtomicWrite:
    def test_failed_replace_no_tmp_left(self, session, monkeypatch):
        """异常注入：os.replace 失败时不残留临时文件、目标不被破坏（FR-020/D9）。"""
        SidecarFile.save(session)
        target = SidecarFile.sidecar_path_for(session.image_path)
        good_content = target.read_text(encoding="utf-8")

        import os

        def boom(*_args, **_kwargs):
            raise OSError("injected failure")

        monkeypatch.setattr(os, "replace", boom)
        session.append(RotateAdjustment({"angle": 30}))
        with pytest.raises(SidecarError):
            SidecarFile.save(session)
        leftovers = [p.name for p in target.parent.iterdir() if ".tmp" in p.name]
        assert leftovers == [], "失败不得残留临时文件"
        assert target.read_text(encoding="utf-8") == good_content, "旧 Sidecar 保持可用"
