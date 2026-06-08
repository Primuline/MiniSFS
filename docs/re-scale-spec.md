# 重新缩放：800 km/px + 新默认值 + 缩放区间扩大

## 修改内容

### 1. WORLD_SCALE
```
800 km/px = 8.0 × 10⁵ m/px
```
修改 `src/config.py`：
```python
WORLD_SCALE: float = 8.0e5  # 800 km per pixel
```

### 2. 工具放置默认像素半径（保持世界半径匹配真实值）

恒星世界半径目标：7.0 × 10⁸ m（= 7 × 10⁵ km）
- 所需像素值：`7.0e8 / 8.0e5 = 875.0` px

行星世界半径目标：6.4 × 10⁶ m（= 6.4 × 10³ km）
- 所需像素值：`6.4e6 / 8.0e5 = 8.0` px (不变)

```python
DEFAULT_RADIUS_STAR: float = 875.0   # 从 20.0 改为 875.0
DEFAULT_RADIUS_PLANET: float = 8.0   # 不变
DEFAULT_RADIUS_PROBE: float = 1.0    # 不变
```

### 3. 缩放区间扩大

当前 `CAMERA_ZOOM_MIN=0.1, CAMERA_ZOOM_MAX=10.0`
新的恒星 875px 在 zoom=1 时填满屏幕（1280px），需要能缩小到看到轨道。

轨道 1亿km = 1e11 m：
- 在 zoom=1：`1e11 / 8e5 = 125000` px（完全看不到）
- 在 zoom=0.01：`125000 * 0.01 = 1250` px（刚好）
- 在 zoom=0.005：`1250 * 0.5 = 625` px（舒服）

```python
CAMERA_ZOOM_MIN: float = 0.0005   # 从 0.1 改
CAMERA_ZOOM_MAX: float = 500.0    # 从 10.0 改（可放大到看行星细节）
```

### 4. 初始相机缩放

Camera 初始化时 zoom 默认为 1.0，但 1.0 下恒星 875px 太大。改为启动时默认 0.01。

在 `src/main.py` 的 main() 中创建 camera 后添加：
```python
# 初始缩放：显示整个恒星+轨道系统
camera.zoom_at(0.008, WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
```

### 5. 初始场景轨道

轨道半径改为 1亿km = 1e11 m：
```python
orbit_radius = 1.0e11  # 1亿km
```

轨道速度相应改变：`v = sqrt(G * M / r) = sqrt(6.67e-11 * 2e30 / 1e11) ≈ 36500 m/s`

### 6. 时间基准速度调整

新 WORLD_SCALE=8e5 下，轨道速度 36500 m/s 时：
在 zoom=0.008：`36500 * 0.008 / 8e5 = 3.65e-4 px/帧`（1x）
需要 ~10 秒一圈（600帧）：
`time_speed = 10 * 60 / (2π * 1e11 / 36500 / 60) ≈ 35000`

但 35000 × 3.65e-4 ≈ 12.8 px/帧 — OK。

```python
BASE_TIME_SPEED = 50000  # 从 3_000_000 改
```

## 文件修改清单

| 文件 | 改动 |
|------|------|
| `src/config.py` | WORLD_SCALE, DEFAULT_RADIUS_STAR, CAMERA_ZOOM_MIN, CAMERA_ZOOM_MAX |
| `src/main.py` | create_default_scene 轨道 1e11m, 初始 zoom, BASE_TIME_SPEED |

## 验收

1. 初始场景恒星 7e8 m，行星 6.4e6 m，轨道 1e11 m，圆周运动
2. 工具放置恒星的 info 面板显示 ~7e8 m
3. 缩放到能看到整个轨道（约 zoom 0.005-0.01）
4. 能放大到看到行星细节（zoom 100+）
5. 所有测试通过
