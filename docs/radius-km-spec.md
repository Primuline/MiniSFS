# Radius 输入改为科学计数法 (km)

## 改动

自定义弹窗（ScientificInputDialog）和编辑弹窗（EditBodyDialog）中，Radius 从单系数输入框改为 **系数 × 10^指数** 双输入框，单位 km。

### 弹窗布局

```
Mass    [____]  *10^ [____] kg
Charge  [____]  *10^ [____] C
Speed   [____]  *10^ [____] km/s
Radius  [____]  *10^ [____] km    ← 双输入框，单位 km
```

### 物理转换

`radius_world = radius_km × 1000`（km → m）

### 字段定义

FIELD_DEFS 第 6-7 个字段：
```python
("Radius coeff", "7.0", True, False),   # 索引 6
("Radius exp",   "5",   False, False),  # 索引 7
```

默认值 `7.0 × 10^5` km = 7.0e8 m（恒星半径）

### ROW_LABELS / ROW_UNITS

```python
ROW_LABELS = ["Mass", "Charge", "Speed", "Radius"]
ROW_UNITS = ["kg", "C", "km/s", "km"]
```

### 返回值

```python
{"mass": float, "charge": float, "speed": float, "radius": float}  # radius 单位 m
```

### 面板高度

原 ScientificInputDialog PANEL_HEIGHT=265，EditBodyDialog PANEL_HEIGHT=235，
需要再增加约 35px（多一个指数框）。

### 具体文件修改

| 文件 | 改动 |
|------|------|
| `src/rendering/input_dialog.py` | ScientificInputDialog 和 EditBodyDialog 的 Radius 改为双输入框 |
