# 轨迹预测重写

## 核心要求

重写放置速度设定阶段的轨迹预测，使用角度判断来控制预测范围。

### 物理模型

二体问题：引力源固定不动，待放置天体在引力场中运动。使用 Euler 或 Velocity Verlet 积分。

### 终止条件（按优先级）

1. **碰撞**：天体与引力源表面接触（`dist < star_radius + body_radius`）→ 截断，标记 collision
2. **逃逸**：距离超过初始距离的 `ESCAPE_RATIO` 倍（如 50 倍）→ 截断，标记 escape
3. **绕圈完成**：天体绕引力源的累计角度 ≥ 360° → 截断，标记 orbited
4. **超出屏幕范围**：点在屏幕外超过连续 N 步 → 截断（不再绘制不可见部分）
5. **最大步数**：`max_steps = 2000` 安全上限

### 角度计算

```
每步计算角度变化：
    r_vec = pos - star_pos
    current_angle = atan2(r_vec[1], r_vec[0])
    delta_angle = current_angle - prev_angle
    归一化到 [-π, π] 区间
    total_angle += abs(delta_angle)

当 total_angle >= 2π 时停止（完成 1 圈）
```

这样可以确保**无论速度快慢、轨道大小，最多预测 1 圈**。

### 虚线长度自适应

虚线间隔不依赖物理步长，而是**按屏幕像素重采样**：

1. 积分完成后得到原始轨迹点序列（密度不匀）
2. 将轨迹重采样为**等屏幕像素间距**的点序列（间距 = `DASH_GAP` 像素）
3. 在重采样后的点上绘制虚线：画 `DASH_ON` 像素 → 跳 `DASH_OFF` 像素

```python
DASH_GAP = 4      # 重采样间距（像素）
DASH_ON = 6       # 画多少像素
DASH_OFF = 6      # 跳多少像素
```

这样无论 zoom 多少、轨道大小，虚线密度始终一致。

### 渲染风格

- 颜色：淡蓝色半透明 (100, 180, 255)
- 线宽：2px
- 碰撞末端：红色实心圆 (255, 50, 50) + 外圈
- 逃逸末端：淡蓝色半透明圈
- 正常末端：小蓝点
- 绕圈完成末端：绿色小点（表示可稳定轨道）

### 返回格式

```python
{
    "trajectory": np.ndarray,      # (N, 2) 世界坐标，已重采样
    "collided": bool,
    "escaped": bool,
    "orbited": bool,               # 新增：绕完一圈
}
```

### 性能

单次计算应在 < 0.5ms 内完成。如果超过 2000 步仍未触发任何终止条件，强制截断。

## 文件修改

| 文件 | 改动 |
|------|------|
| `src/physics/forces.py` | 重写 `predict_single_star_trajectory()`：角度终止、重采样 |
| `src/rendering/effects.py` | 简化 `draw_placement_trajectory()`：直接逐段绘制（不再自己做虚线），添加 orbited 标记 |
| `src/config.py` | 添加 `DASH_GAP`, `DASH_ON`, `DASH_OFF` 等常量 |
| `src/main.py` | `_compute_placement_trajectory()` 调用参数不变 |

## 验收

1. 行星轨道速度下显示约 270° 弧线
2. 高速逃逸场景轨迹截断、淡出标记
3. 撞向恒星的轨迹截断、红点标记
4. 虚线间隔在不同 zoom 下保持一致（~6px 画、~6px 跳）
5. 所有测试通过
