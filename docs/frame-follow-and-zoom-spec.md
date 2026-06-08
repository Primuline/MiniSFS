# 参考系持续跟随 + 退出恢复缩放

## 1. 持续跟随

**当前问题**：双击天体进入参考系时只调用了一次 `camera.follow()`，后续帧没有更新相机位置，天体移动后视角不会跟随。

**修复**：在主循环的每帧末尾（物理更新后、渲染前），如果 `reference_body_id` 不为 None，更新相机位置以跟随该天体：

```python
# 每帧跟随参考系天体
if reference_body_id is not None and reference_body_id < bodies.shape[0]:
    if bodies[reference_body_id, IS_ACTIVE] == 1.0:
        wx = float(bodies[reference_body_id, X])
        wy = float(bodies[reference_body_id, Y])
        camera.follow(wx, wy)
```

这段代码应放在参考系天体消失检查之后（或与之结合）。

## 2. 退出恢复缩放

**进入时备份**：在 `DOUBLE_CLICK` 处理中，进入参考系前保存当前的 zoom 值：
```python
_saved_zoom_before_frame: float = camera.zoom  # 保存当前 zoom
```

**退出时恢复**：在退出参考系时（Esc、天体消失），将 zoom 恢复为保存的值，同时保持相机中心在当前参考系天体的位置：

```python
# 恢复 zoom
zoom_to_restore = _saved_zoom_before_frame
if camera.zoom != zoom_to_restore:
    camera.zoom_at(zoom_to_restore / camera.zoom, WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
```

注意：恢复 zoom 时使用 `camera.zoom_at()` 以屏幕中心为缩放中心，确保画面不跳变。

## 文件修改

| 文件 | 改动 |
|------|------|
| `src/main.py` | 添加 `_saved_zoom_before_frame` 变量；DOUBLE_CLICK 时保存 zoom；每帧跟随参考系天体；Esc/消失退出时恢复 zoom |
