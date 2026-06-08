# 统一放置预览流程 — Star/Planet/Probe 工具

## 概述

将 Star、Planet、Probe 三种工具的放置方式改为与 Custom 工具类似的两步流程：
1. 预览位置（虚线圆跟随鼠标）
2. 设定速度方向（箭头线，长度无上限）

不再像现在这样"点一下直接放出来"。

## 操作流程

### Step 1: 选择工具

点击工具栏 S / P / D 按钮或按 1 / 2 / 3 键：
- 时间冻结（物理暂停）
- 进入放置预览模式
- 参数使用工具默认值（`get_default_body_params`，Custom 工具仍然用弹窗）

### Step 2: 预览位置

- 鼠标移动时，一个**白色虚线圆** + 十字准星跟随鼠标
- 虚线圆半径 = 该工具默认的像素半径（`DEFAULT_RADIUS_*`）
- 点击 **左键** → 固定预览位置，进入 Step 3
- 点击 **右键** → 取消整个操作，时间恢复

### Step 3: 设定速度方向

- 预览圆固定在之前点击的位置
- 从预览圆中心到鼠标当前位置画一条**橙色箭头线**，表示发射方向
- **去掉箭头的长度限制**（现在是 40px max，改为无限长）
- 箭头长度决定速度大小（正比关系）：
  - `speed = speed_per_px × arrow_length_px`
  - `speed_per_px` 是一个可调的转换系数，默认为 `500.0 m/s per pixel`
  - 比如箭头 100px → 速度 50,000 m/s，箭头 200px → 速度 100,000 m/s
- 点击 **左键** → 在预览圆位置放置天体，速度方向为箭头方向，大小按比例计算
- 点击 **右键** → 返回 Step 2（重新选择位置）

### 取消

任意阶段按 **Esc** 取消，时间恢复。

## 技术实现

### Star/Planet/Probe 共用放置状态

在 `src/main.py` 中添加新的状态变量（与 Custom 不冲突）：

```python
simple_placement_stage: int = 0  # 0=未激活, 1=预览位置, 2=设定速度
simple_placement_tool: Optional[str] = None  # "TOOL_STAR"/"TOOL_PLANET"/"TOOL_PROBE"
simple_preview_pos: Optional[Tuple[float, float]] = None
simple_arrow_start: Optional[Tuple[float, float]] = None
```

### 交互控制

`TOOL_STAR` / `TOOL_PLANET` / `TOOL_PROBE` 激活时：
- 冻结时间，进入 `simple_placement_stage = 1`
- 不显示弹窗（Custom 才弹窗）

CLICK 命令处理中新增分支：
```python
if simple_placement_stage > 0:
    # 处理简单放置流程
    if simple_placement_stage == 1:  # 固定位置
        simple_preview_pos = world_pos
        simple_arrow_start = world_pos
        simple_placement_stage = 2
    elif simple_placement_stage == 2:  # 放置
        mass, radius, charge, body_type = get_default_body_params(simple_placement_tool)
        # 计算速度 = 箭头长度 × SPEED_PER_PX
        # 放置天体，恢复时间
```

RIGHT_CLICK 处理：
- Stage 2 → 回退 Stage 1
- Stage 1 → 取消，恢复时间

### 预览渲染

在 `renderer.py` 中**复用**已有的 `draw_placement_preview()` 和 `draw_velocity_arrow()` 方法。

### 速度比例系数

在 `config.py` 中添加：
```python
PLACEMENT_SPEED_PER_PX: float = 500.0  # m/s per pixel
```

### Simple 与 Custom 的互斥

- 如果 `simple_placement_stage > 0`，忽略 `TOOL_CUSTOM` 的激活
- 如果 `custom_placement_stage > 0`，忽略 `S/P/D` 工具的激活
- 取消时同时检查两种状态

## 文件修改清单

| 文件 | 改动 |
|------|------|
| `src/config.py` | 添加 `PLACEMENT_SPEED_PER_PX` |
| `src/main.py` | 添加简单三步放置状态变量 + 交互逻辑 |
| `src/rendering/renderer.py` | 在渲染中绘制 simple 预览圆和箭头（如果激活） |

## 验收标准

1. 选 S → 时间冻结 → 虚线圆跟鼠标
2. 左键固定位置 → 箭头指向鼠标（无长度限制）
3. 再左键 → 放置恒星，沿箭头方向以正比速度发射
4. 右键 / Esc 取消，时间恢复
5. P / D 工具同理
6. Custom 工具不受影响（仍然弹窗）
7. 所有已有测试通过
