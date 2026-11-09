"""测试夹具：程序化生成样图 + 像素断言助手 + RAW 样片路径。

所有样图均程序化生成（pytest tmp_path），不依赖仓库内二进制样片；
RAW 样片由环境变量 PYLIGHTROOM_ARW_SAMPLE 提供路径，缺失时对应用例 skip。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# 像素断言助手
# ---------------------------------------------------------------------------


def mean_channel_values(image: Image.Image) -> tuple[float, float, float]:
    """返回 RGB 三通道均值 (r, g, b)。"""
    rgb = image.convert("RGB")
    hist = rgb.histogram()
    n = rgb.size[0] * rgb.size[1]
    means = []
    for offset in (0, 256, 512):
        weighted = sum(v * c for v, c in enumerate(hist[offset : offset + 256]))
        means.append(weighted / n)
    return (means[0], means[1], means[2])


def pixel_equal(a: Image.Image, b: Image.Image) -> bool:
    """逐像素严格相等判定（统一 RGB 表示后比较）。"""
    if a.size != b.size:
        return False
    from PIL import ImageChops

    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    return diff.getbbox() is None


def assert_pixel_equal(a: Image.Image, b: Image.Image, msg: str = "") -> None:
    assert pixel_equal(a, b), msg or "图像像素不一致"


# ---------------------------------------------------------------------------
# 样图夹具
# ---------------------------------------------------------------------------


@pytest.fixture
def rgb_image() -> Image.Image:
    """程序化小尺寸 RGB 图：左半暖色渐变、右半冷色渐变，含足够纹理。"""
    img = Image.new("RGB", (64, 48))
    px = img.load()
    for y in range(48):
        for x in range(64):
            if x < 32:
                px[x, y] = (180 + x, 60 + y, 40)
            else:
                px[x, y] = (40, 80 + (x - 32), 170 + (y // 2))
    return img


@pytest.fixture
def gradient_image() -> Image.Image:
    """水平灰度渐变图（0→255），用于对比度/直方图类断言。"""
    img = Image.new("L", (256, 16))
    px = img.load()
    for x in range(256):
        for _y in range(16):
            px[x, _y] = x
    return img.convert("RGB")


@pytest.fixture
def jpeg_sample(tmp_path: Path, rgb_image: Image.Image) -> Path:
    p = tmp_path / "sample.jpg"
    rgb_image.save(p, "JPEG", quality=95)
    return p


@pytest.fixture
def png_sample(tmp_path: Path, rgb_image: Image.Image) -> Path:
    p = tmp_path / "sample.png"
    rgb_image.save(p, "PNG")
    return p


@pytest.fixture
def png_transparent_sample(tmp_path: Path) -> Path:
    """带透明通道的 PNG：左半不透明红色、右半完全透明。"""
    img = Image.new("RGBA", (32, 32), (255, 0, 0, 0))
    px = img.load()
    for y in range(32):
        for x in range(16):
            px[x, y] = (255, 0, 0, 255)
    p = tmp_path / "transparent.png"
    img.save(p, "PNG")
    return p


@pytest.fixture
def bmp_sample(tmp_path: Path, rgb_image: Image.Image) -> Path:
    p = tmp_path / "sample.bmp"
    rgb_image.save(p, "BMP")
    return p


@pytest.fixture
def webp_sample(tmp_path: Path, rgb_image: Image.Image) -> Path:
    p = tmp_path / "sample.webp"
    rgb_image.save(p, "WEBP")
    return p


@pytest.fixture
def corrupted_file(tmp_path: Path) -> Path:
    """损坏的伪 JPEG（内容为乱码字节）。"""
    p = tmp_path / "corrupted.jpg"
    p.write_bytes(b"\x00\x01\x02not-an-image\xff\xff")
    return p


@pytest.fixture
def arw_sample() -> Path:
    """RAW 主验收样片（.ARW）路径：经环境变量提供，缺失时 skip。"""
    raw_path = os.environ.get("PYLIGHTROOM_ARW_SAMPLE", "")
    if not raw_path or not Path(raw_path).is_file():
        pytest.skip("未提供 .ARW 样片（设置 PYLIGHTROOM_ARW_SAMPLE 环境变量）")
    return Path(raw_path)
