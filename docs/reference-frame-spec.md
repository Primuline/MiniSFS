# 天体参考系功能

## 概述

双击天体后进入该天体的参考系。此后视角以该天体为中心，新放置的天体初始速度叠加该天体的速度。

## 操作流程

### 进入参考系
- **双击天体** → 进入该天体的参考系
  - 相机跟随该天体
  - 记录该天体作为参考系原点（`reference_body_id`）
  - HUD 显示 "Frame: Star #0"

### 在参考系下放置天体
- 使用 S / P / D / C 工具放置天体时：
  - `bodies[new_id, VX] = set_vx + bodies[ref_id, VX]`
  - `bodies[new_id, VY] = set_vy + bodies[ref_id, VY]`

### 退出参考系
- 按 **Esc** → 退出参考系，`reference_body_id = None`
- 参考系天体消失（碰撞合并） → 自动退出

## 技术实现

### 状态变量
```python
reference_body_id: Optional[int] = None
```

### 进入
DOUBLE_CLICK 处理中添加 `reference_body_id = found_id`（相机 follow 已有）

### 退出
MENU (Esc) 处理中：如果 `reference_body_id` 非 None，清除它并 `continue`（不退出游戏）
物理更新后检查天体是否消失

### 速度叠加
所有放置代码处（CLICK/GRAB_START 中的 Star、Planet/Probe Stage 2、Custom Stage 3）：
```python
if reference_body_id is not None and reference_body_id < bodies.shape[0]:
    bodies[-1, VX] += bodies[reference_body_id, VX]
    bodies[-1, VY] += bodies[reference_body_id, VY]
```

### HUD 显示
`set_reference_frame(body_id, body_type)` / `clear_reference_frame()` 方法
在 info bar 显示 "Frame: Star #0"
