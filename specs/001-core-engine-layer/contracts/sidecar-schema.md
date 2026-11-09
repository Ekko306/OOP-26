# Contract: Sidecar 参数文件 Schema（v1）

**Feature**: 001-core-engine-layer | **Date**: 2026-11-09

Sidecar 是编辑会话的唯一持久化形态，命名规则：同主名换扩展名（`photo.jpg` → `photo.json`，Clarifications Q4）。原图文件永不写入。

## JSON 结构

```json
{
  "version": 1,
  "image_path": "photos/photo.jpg",
  "instructions": [
    { "type": "brightness", "params": { "factor": 1.3 } },
    { "type": "crop",       "params": { "box": [0, 0, 800, 600] } },
    { "type": "rotate",     "params": { "angle": 90 } },
    { "type": "histogram_equalization", "params": { "factor": 1.5 } }
  ]
}
```

## 字段定义

| 字段 | 类型 | 约束 |
| ---- | ---- | ---- |
| `version` | int | 协议版本，当前固定 `1`；读到更高版本抛 SidecarError（前向拒绝） |
| `image_path` | string | 相对或绝对路径，标识关联原图（仅记录，不校验存在性——图可移动） |
| `instructions` | array | 有序；空数组合法（空会话）；每元素见下 |

## 指令元素

| 字段 | 类型 | 约束 |
| ---- | ---- | ---- |
| `type` | string | 注册于 AdjustmentFactory 的策略名（core-api.md §3）；未知值抛 SidecarError，不静默丢弃（FR-022） |
| `params` | object | 键值须符合该策略 param_schema；几何参数按自然单位（像素框/角度），色彩参数 0.0–2.0 |

## 读写规则

- **写**：会话整体序列化；先写临时文件再原子 `os.replace`；Sidecar 与成品导出同时产生（FR-019）
- **读**：逐条经 `AdjustmentFactory.create(type, params)` 重建并注入会话；任何一条失败则整体失败，会话保持原状（不留半恢复状态）
- **往返不变量**：save → load 后指令栈逐条 type 与 params 完全一致（SC-002）
