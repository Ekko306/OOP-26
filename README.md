# PyLightroom

面向对象程序设计课程项目：简化版 Adobe Lightroom（Web 应用）。当前已完成**核心引擎层**——纯 Python、零界面框架依赖的图像处理引擎。

## 核心引擎（pylightroom/core）

- **8 类调整策略**：亮度 / 对比度 / 饱和度 / 锐度 / 色温 / 直方图均衡 / 裁剪 / 旋转（色彩类参数统一 0.0–2.0，1.0 中性；几何参数自然单位）
- **5 种格式**：JPEG / PNG（透明合成白底）/ BMP / WebP + RAW（主验收 .ARW）
- **非破坏性编辑**：指令栈 + 撤销/重做 + 栈顶同类合并；原图像素永不修改
- **Sidecar 持久化**：`photo.jpg` → `photo.json`，原子写，重开恢复
- **三级预览**：256px / 1024px / 全图，低分先行、高分后台补齐（版本号缓存失效）
- **导出**：JPEG / PNG，失败不留半成品；导出同时持久化原图关联 Sidecar
- **直方图**：RGB 三通道 256 bin 统计

### 快速上手

```bash
uv venv
uv pip install -r requirements.txt
```

```python
from pylightroom.core import ImageProcessor

p = ImageProcessor()
p.open("photo.jpg")
p.update_adjustment("brightness", {"factor": 1.3})
p.update_adjustment("contrast", {"factor": 0.9})
p.undo()                                  # 撤销
p.render("thumb")                         # 三级渲染：thumb / medium / full
p.export("out.png", "png")                # 成品 + 原图关联 photo.json

# 重开恢复
from pylightroom.core import SidecarFile
SidecarFile.load("photo.jpg", p._session)
```

### 扩展新调整（开闭原则）

```python
from pylightroom.core import AdjustmentFactory
from pylightroom.core.adjustments.base import BaseAdjustment

class VignetteAdjustment(BaseAdjustment):
    name = "vignette"
    param_schema = {"factor": {"min": 0.0, "max": 2.0, "default": 1.0}}
    def apply(self, image, params): ...

AdjustmentFactory.register(VignetteAdjustment)  # 存量代码零修改
```

### 架构红线与验证

```bash
uv run python scripts/check_arch_redline.py   # core 零界面框架引用（PASS）
$env:PYTHONUTF8 = '1'; uv run python -m pytest tests/ -v   # 全量测试
```

RAW 样片测试：设置环境变量 `PYLIGHTROOM_ARW_SAMPLE` 指向 .ARW 文件（缺失时对应用例自动 skip）。

## 文档

- 技术设计：[docs/PyLightroom技术设计文档.md](docs/PyLightroom技术设计文档.md)
- 核心规格与任务：[specs/001-core-engine-layer/](specs/001-core-engine-layer/spec.md)
- API 契约：[specs/001-core-engine-layer/contracts/core-api.md](specs/001-core-engine-layer/contracts/core-api.md)
- 项目准则：[.specify/memory/constitution.md](.specify/memory/constitution.md)
