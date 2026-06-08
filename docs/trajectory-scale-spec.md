# 轨迹预测参数适配新缩放

## 背景
WORLD_SCALE 已从 1e9 改为 8e5 (800 km/px)，轨迹预测的步数和 dt 需要重新校准。

## 当前参数

`_compute_placement_trajectory()` 中：
```python
if speed > 1e5:
    traj_steps = 600; traj_dt = 20000
elif speed > 1e4:
    traj_steps = 400; traj_dt = 10000
else:
    traj_steps = 300; traj_dt = 5000
```

`predict_single_star_trajectory()` 默认值：
```python
steps = 300, dt = 5000.0
```

`PLACEMENT_SPEED_PER_PX = 500.0` (m/s per screen pixel)

## 校准

轨道速度参考值：`√(G × 2e30 / 1e11) ≈ 36500 m/s`
轨道周期 ≈ 2π × 1e11 / 36500 ≈ 1.72e7 s ≈ 200 天

轨迹预测应该展示约 1-2 圈的轨迹：
- 36500 m/s 下，一圈约 1.72e7 秒
- dt=5000s → 每步 1.8e8 m ≈ 0.18% 轨道 → 300 步 ≈ 54% 轨道（半圈）OK

但高速场景 (1e5+) 时 dt=20000 偏大：
- 1e5 m/s × 20000s = 2e9 m/步 → 太快了
- 应该改为 dt=5000 × (1e4/speed) 或者用固定比例

## 需调整的文件

`src/main.py` 的 `_compute_placement_trajectory()`

## 验收
1. 低速 (speed < 1e4) 轨迹显示约 1 圈
2. 中速 (1e4-1e5) 轨迹显示约 0.5-1 圈
3. 高速 (1e5+) 轨迹显示约 0.25-0.5 圈
4. 不出现跳跃/断裂
5. 所有测试通过
