# 右键编辑触发条件修正 + 参考系自动缩放

## 1. 右键编辑面板触发条件

**当前问题**：只要选中了天体，在屏幕任意位置右键都会弹出编辑面板。

**目标**：只有右键**点击在天体上**时才弹出编辑面板。右键点空白时不做任何操作（或保持现有的取消选择行为）。

**修复**：在 `src/main.py` 的 RIGHT_CLICK 处理中，把编辑弹窗的触发条件从 `if selected_body_id is not None` 改为 `if found_id is not None`（即右键点在了某个天体上）。同时需要区分：
- 右键点在探测器上 → 启动瞄准（已有逻辑，保持不变）
- 右键点在其他天体上 → 弹出编辑面板
- 右键点在空白处 → 取消选择（`selected_body_id = None`）

具体代码改为：
```python
if found_id is not None and int(bodies[found_id, BODY_TYPE]) == BODY_TYPE_PROBE:
    # 右键探测器 → 启动瞄准（不变）
    ...
elif found_id is not None:
    # 右键其他天体 → 编辑该天体
    selected_body_id = found_id
    ...
    show_edit_dialog(...)
else:
    # 右键空白 → 取消选择
    selected_body_id = None
    ...
```

## 2. 参考系自动缩放

**当前问题**：双击天体进入参考系后，视角以该天体为中心但不改变缩放。

**目标**：进入参考系后自动缩放，让目标天体在屏幕上显示为合适大小（约 50 像素半径）。

**实现**：

在 `src/main.py` 的 DOUBLE_CLICK 处理中，在设置 `reference_body_id` 之后，计算并设置合适的 zoom：

```python
# 计算合适的 zoom，使天体显示为约 50px 半径
target_screen_radius = 50.0  # 像素
body_world_radius = float(bodies[found_id, RADIUS])
if body_world_radius > 0:
    desired_zoom = target_screen_radius * WORLD_SCALE / body_world_radius
    desired_zoom = max(CAMERA_ZOOM_MIN, min(CAMERA_ZOOM_MAX, desired_zoom))
    # 以屏幕中心为缩放中心
    camera.zoom_at(desired_zoom / camera.zoom, WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
```

导入 `CAMERA_ZOOM_MIN, CAMERA_ZOOM_MAX` 如果尚未导入。

## 文件修改

| 文件 | 改动 |
|------|------|
| `src/main.py` | RIGHT_CLICK 触发条件修改 + DOUBLE_CLICK 时自动缩放 |
