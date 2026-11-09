"""SC-006 开闭原则插件演示：不修改任何存量文件，新增调整子类经注册即刻可用。

本文件是 FR-009/FR-026 的验收测试：VignetteAdjustment 定义于测试内部，
仅调用 AdjustmentFactory.register() 后即可经工厂创建与应用；
配套 scripts/check_arch_redline.py 验证注册后 git 工作区仍无 core 存量改动。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from pylightroom.core.adjustments.base import BaseAdjustment
from pylightroom.core.adjustments.factory import AdjustmentFactory
from pylightroom.core.errors import AdjustmentError

REPO_ROOT = Path(__file__).resolve().parents[2]


class VignetteAdjustment(BaseAdjustment):
    """演示用插件策略：暗角强度，factor 0.0（无暗角）–2.0（最强）。"""

    name = "vignette"
    param_schema = {"factor": {"min": 0.0, "max": 2.0, "default": 1.0}}

    def apply(self, image: Image.Image, params: dict) -> Image.Image:
        if params["factor"] == 0.0:
            return image.copy()
        width, height = image.size
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        margin = int(min(width, height) * 0.15 * params["factor"])
        draw.ellipse(
            (-margin, -margin, width + margin, height + margin), fill=255
        )
        black = Image.new("RGB", (width, height), (0, 0, 0))
        return Image.composite(image, black, mask)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """插件注册污染全局注册表：测试后恢复原状，保证其他用例的「未注册名」语义。"""
    saved = dict(AdjustmentFactory._registry)
    yield
    AdjustmentFactory._registry.clear()
    AdjustmentFactory._registry.update(saved)


class TestOpenClosedExtension:
    def test_register_then_factory_create(self):
        AdjustmentFactory.register(VignetteAdjustment)
        instance = AdjustmentFactory.create("vignette", {"factor": 1.5})
        assert isinstance(instance, VignetteAdjustment)
        assert "vignette" in AdjustmentFactory.registered_names()

    def test_plugin_usable_in_pipeline(self, rgb_image):
        AdjustmentFactory.register(VignetteAdjustment)
        out = VignetteAdjustment({"factor": 1.5}).apply(rgb_image, {"factor": 1.5})
        assert out.size == rgb_image.size
        assert out.mode == "RGB"
        # 暗角生效：角落像素应比中心暗
        assert sum(out.load()[2, 2]) < sum(out.load()[32, 24])

    def test_polymorphic_substitution(self, rgb_image):
        """里氏替换：插件子类可无差别进入指令栈语义（merge/serialize）。"""
        plugin = VignetteAdjustment({"factor": 1.0})
        assert plugin.merge(VignetteAdjustment({"factor": 1.8})) is True
        assert plugin.params["factor"] == 1.8
        rebuilt = VignetteAdjustment.deserialize(plugin.serialize())
        assert rebuilt.params["factor"] == 1.8

    def test_existing_files_untouched(self):
        """注册制扩展不改存量代码（FR-026）：经注册点扩展时 core/ 存量文件内容零变化。

        以「注册前后 core/ 源文件内容快照」为断言对象。002 起不再以 git
        工作区状态为准——core 允许计划内 additive 演进（新增只读查询方法等），
        见 specs/002-bridge-state-layer/research.md D1/D2。
        """
        core_dir = REPO_ROOT / "pylightroom" / "core"
        snapshot = {
            str(path.relative_to(REPO_ROOT)): path.read_bytes()
            for path in sorted(core_dir.rglob("*.py"))
        }
        AdjustmentFactory.register(VignetteAdjustment)
        AdjustmentFactory.create("vignette", {"factor": 1.5})  # 扩展即刻可用
        after = {
            str(path.relative_to(REPO_ROOT)): path.read_bytes()
            for path in sorted(core_dir.rglob("*.py"))
        }
        assert after == snapshot, "注册制扩展修改了存量 core 文件"
