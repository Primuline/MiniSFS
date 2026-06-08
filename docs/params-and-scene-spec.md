# 自定义+编辑弹窗添加半径选项 + 默认参数修改 + 初始场景修改

## 1. 弹窗添加半径选项

### ScientificInputDialog（自定义粒子弹窗）
增加一行 Radius 输入（科学计数法，像素值）：
```
Mass    [____]  *10^ [____] kg
Charge  [____]  *10^ [____] C
Speed   [____]  *10^ [____] km/s
Radius  [____]        [px]    ← 新增，默认值从质量自动计算
```

只有一个系数输入框（无指数），因为是像素值通常在 2-30 之间。
默认值：`CUSTOM_RADIUS_FACTOR * sqrt(mass / CUSTOM_MASS_DEFAULT)`，范围 2~30px。
字段索引：6 (radius_coeff)。

返回值中新增 `"radius"` 键。

### EditBodyDialog（编辑已有天体弹窗）
增加一行 Radius：
```
Mass    [____]  *10^ [____] kg
Charge  [____]  *10^ [____] C
Radius  [____]        [px]    ← 新增，预填当前天体半径(像素值)
```

像素值输入，范围 2~30px。

### 放置时使用
- Custom 工具 Stage 3 放置时：使用 `dialog_result["radius"]` 计算 `radius_world = radius_pixel * WORLD_SCALE`
- 编辑天体 OK 时：除了更新质量/电荷，也更新 RADIUS 列

## 2. 默认参数修改

### config.py
```python
DEFAULT_MASS_STAR: float = 2.0e30
DEFAULT_RADIUS_STAR: float = 7.0e5  # 像素值，但用于 get_default_body_params 的返回
DEFAULT_MASS_PLANET: float = 6.0e26
DEFAULT_RADIUS_PLANET: float = 6.4e3
```

注意：`DEFAULT_RADIUS_*` 是像素值，`make_body` 时乘以 `WORLD_SCALE` 转世界单位。
所以半径为 7.0e5 像素 × 1e9 m/px = 7e14 m —— 太大了。
应该直接改为世界单位半径，或者在 `get_default_body_params` 中返回世界单位。

重新考虑：config 中的 `DEFAULT_RADIUS_STAR` 当前是像素值（20.0），在 `get_default_body_params` 中返回，然后在 main.py 中 `radius * WORLD_SCALE` 转世界单位。

用户给的是 `7.0 10^5`——这应该是千米？
- 太阳实际半径 ≈ 6.96e5 km = 6.96e8 m
- 地球实际半径 ≈ 6371 km = 6.371e6 m

用户写的是 `7.0 × 10^5` 和 `6.4 × 10^3`——单位可能是 km。

所以：
- 恒星世界半径：7.0e5 km = 7.0e8 m
- 行星世界半径：6.4e3 km = 6.4e6 m

在 config 中直接存世界单位（m），然后修改 `get_default_body_params` 返回世界单位半径（不再乘以 WORLD_SCALE）。

或者在 config 中存 km 值，乘以 1000 转 m。

### get_default_body_params
改为 radius 直接返回米（世界单位），因为用户期望的是真实物理尺寸。

### 探测器
质量设为 1.0 kg，半径设为 1.0 m。

## 3. 初始场景修改

只保留一个恒星和一个行星：
- 恒星：质量 2.0e30 kg，半径 7.0e8 m（= 7e5 km），位置 (0, 0)，静态
- 行星：质量 6.0e26 kg，半径 6.4e6 m（= 6.4e3 km），轨道半径 1.496e11 m（= 1 AU），圆周运动

`orbital_speed = sqrt(G * M / r) = sqrt(6.67e-11 * 2e30 / 1.496e11) ≈ 29800 m/s`

```python
star = make_body(x=0, y=0, mass=2.0e30, radius=7.0e8, body_type=BODY_TYPE_STAR, is_static=True)
planet = make_body(x=1.496e11, y=0, vx=0, vy=29800, mass=6.0e26, radius=6.4e6, body_type=BODY_TYPE_PLANET)
```

## 文件修改清单
| 文件 | 改动 |
|------|------|
| `src/config.py` | 修改默认质量/半径值 |
| `src/main.py` | 修改 `create_default_scene()` |
| `src/rendering/input_dialog.py` | ScientificInputDialog 和 EditBodyDialog 添加 Radius 字段 |
| `src/rendering/hud.py` | 更新 get_default_body_params 返回值 |
