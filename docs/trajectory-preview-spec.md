# 放置速度设定时的轨迹预览

## 概述

在 Planet/Probe/Custom 工具的 Stage 2/3（设定速度方向）时，实时显示预测轨迹。
轨迹基于当前设定的速度方向/大小和引力源计算。

## 参考系规则

| 场景 | 引力源 | 说明 |
|:-----|:--------|:-----|
| 在星体参考系内 | 该参考系天体 | 只考虑该天体的引力 |
| 在全局参考系 | 最近的恒星 | 寻找 `BODY_TYPE_STAR` 类型天体（若没有恒星则直线） |

## 轨迹计算

### 物理模型
使用开普勒轨道/数值积分计算轨迹：
- 简化为**二体问题**（引力源 + 待放置天体）
- 引力源视为固定点（质量极大）
- 待放置天体从预览位置以设定速度开始运动

### 数值积分
使用 RK4 或简单的递推，步数约 200 步：
```python
def predict_kepler_trajectory(pos, vel, star_pos, star_mass, steps=200, dt=1e5):
    trajectory = [pos]
    for _ in range(steps):
        r = pos - star_pos
        dist_sq = r[0]**2 + r[1]**2 + SOFTENING**2
        acc = -G * star_mass * r / (dist_sq * np.sqrt(dist_sq))
        vel += acc * dt
        pos += vel * dt
        trajectory.append(pos.copy())
        # 碰撞检测
        if dist_sq < (star_radius + body_radius)**2:
            break
        # 逃逸检测
        if np.sqrt(pos[0]**2 + pos[1]**2) > 10 * initial_distance:
            break
    return np.array(trajectory)
```

### 边界处理
- **碰撞**：轨迹在坠入恒星的表面处截断（绘制闪烁的红点标记）
- **逃逸**：轨迹在飞出 10 倍初始距离后截断（绘制淡出虚线）
- **椭圆**：绘制完整一圈

## 渲染

- 轨迹线：**淡蓝色半透明虚线**，线宽 2px
- 碰撞标记：到达恒星表面时画红色闪烁圆点
- 逃逸标记：末端淡出
- 预览位置到轨迹起点之间有一条连接线（白色半透明）

## 技术实现

### 新增函数
在 `src/physics/forces.py` 或 `src/physics/engine.py` 中添加：

```python
def predict_single_star_trajectory(
    pos: np.ndarray,      # shape (2,) 预览位置
    vel: np.ndarray,      # shape (2,) 设定速度
    star_pos: np.ndarray, # shape (2,) 引力源位置
    star_mass: float,     # 引力源质量
    star_radius: float,   # 引力源半径
    body_radius: float,   # 放置天体的半径
    g: float,             # 引力常数
    softening: float,     # 软化参数
    steps: int = 200,
    dt: float = 1e5,
) -> dict:
    """返回 {"trajectory": np.ndarray, "collided": bool, "escaped": bool}"""
```

### 调用位置

在 `src/main.py` 的渲染部分，当 Stage 2/3 并且有预览位置和箭头方向时，计算并绘制轨迹。

新增状态变量：
```python
placement_trajectory: Optional[Dict] = None  # 当前放置预览的轨迹
```

每次 Stage 2 的鼠标移动时重新计算：
```python
# 获取引力源
if reference_body_id is not None:
    star_idx = reference_body_id
    star_pos = bodies[star_idx, [X, Y]]
    star_mass = bodies[star_idx, MASS]
else:
    # 找最近的恒星
    star_idx = find_nearest_star(...)
    if star_idx is not None:
        star_pos = bodies[star_idx, [X, Y]]
        star_mass = bodies[star_idx, MASS]
    else:
        placement_trajectory = None
        continue

placement_trajectory = predict_single_star_trajectory(...)
```

### 辅助函数
```python
def find_nearest_star(pos, bodies) -> Optional[int]:
    """在 bodies 中找最近的 BODY_TYPE_STAR 类型天体。"""
```

## 文件修改清单

| 文件 | 改动 |
|------|------|
| `src/physics/engine.py` 或 `src/physics/forces.py` | 新增 `predict_single_star_trajectory()` |
| `src/main.py` | 新增 `placement_trajectory` 状态；Stage 2/3 鼠标移动时计算；渲染阶段绘制 |
| `src/rendering/renderer.py` | 新增 `draw_placement_trajectory()` 方法 |

## 验收标准

1. Planet Stage 2 时显示淡蓝色轨迹预测线
2. 参考系下轨迹以该星体为引力源
3. 全局参考系下以最近的恒星为引力源
4. 碰撞恒星时轨迹截断，显示红点
5. 逃逸时轨迹淡出
6. 无恒星时显示直线
7. 所有已有测试通过
