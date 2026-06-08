# 自定义粒子工具 — 三步放置流程

## 概述

替换原有的 `TOOL_CUSTOM` 实现。新的自定义粒子工具采用三步交互流程，让玩家精确控制天体的质量、电荷、初始速度和放置位置。

## 操作流程

### 第一步：选择工具并配置参数

1. 玩家点击工具栏的 `C` 按钮或按 `4` 键选择自定义粒子工具
2. **时间冻结**（物理暂停）⚠️ 重要：如果时间不在暂停状态，强制暂停
3. 弹出**参数设置弹窗**，包含四个输入框：
   - **Mass (kg)** — 浮点数输入，默认 `1.0e25`
   - **Charge (C)** — 浮点数输入（可正可负），默认 `0.0`
   - **Speed (m/s)** — 浮点数输入，默认 `1.0e4`
   - 半径自动显示（只读）：`R = factor × sqrt(mass / 1e25)`，范围 2~30px
4. 弹窗底部有 **OK** 和 **Cancel** 两个按钮
5. 点击 **Cancel** → 取消放置，时间恢复
6. 点击 **OK** → 关闭弹窗，进入第二步

### 第二步：选择放置位置（预览）

1. 弹窗关闭后，一个**虚线圆**跟随鼠标移动，表示天体放置后的实际大小（世界坐标映射）
2. 虚线圆的颜色：白色半透明，圆心有十字准星标记
3. 玩家移动鼠标到目标位置
4. 点击 **左键** → 固定预览圆的位置，进入第三步
5. 点击 **右键** → 取消整个操作，时间恢复

### 第三步：设定初始速度方向

1. 预览圆固定在之前点击的位置
2. 从预览圆中心到鼠标当前位置画一条**箭头线**，表示发射方向
3. 箭头长度限制在一个最大半径内（如 200 像素），超过时截断但方向不变
4. 箭头颜色：速度方向为**橙色**，线宽 3px，末端有箭头头
5. 箭头的长度决定速度大小：
   - 最长为 `max_length`（200px）对应配置的 Speed 值
   - 最短为 0px 对应 0 m/s
   - 中间线性插值：`actual_speed = speed × (arrow_length / max_length)`
6. 点击 **左键** →
   - 在预览圆位置放置天体
   - 速度方向为箭头方向，大小为按比例计算后的值
   - 时间恢复
   - 清除预览状态
7. 点击 **右键** → 返回第二步（重新选择位置），预览圆继续跟随鼠标

### 取消操作

玩家在任何步骤按 `Esc` 键取消整个操作，时间恢复，清除所有预览状态。

## 技术实现

### 状态管理

在 `src/main.py` 的主循环中添加三个新的状态变量：

```python
custom_placement_stage: int = 0  # 0=未激活, 1=弹窗配置, 2=选择位置, 3=设定速度
custom_preview_pos: Optional[Tuple[float, float]] = None  # 预览圆的世界坐标
custom_arrow_start: Optional[Tuple[float, float]] = None   # 箭头起点（=预览圆位置）
custom_particle_mass: float = DEFAULT_MASS_PLANET
custom_particle_charge: float = 0.0
custom_particle_speed: float = 1.0e4
```

当工具激活时，游戏 paused + is_grabbing 式的冻结物理。

### 弹窗实现

创建一个简单的参数输入弹窗 `src/rendering/input_dialog.py`：

```python
class InputDialog:
    """简易参数输入弹窗。"""
    def __init__(self, fields: list[dict], title: str):
        # fields = [{"label": "Mass (kg)", "default": "1e25", "type": "float"}, ...]
        ...
    
    def handle_event(self, event) -> Optional[dict]:
        """返回 {field_label: value} 或 None（未完成）"""
    
    def draw(self, surface):
        ...
```

或者直接用已有的 `Button` 类 + 简单的文本输入（用 `pygame.key` 捕获字符输入）。

**简化方案建议**：为了避免复杂的文本输入实现，可以把参数改成可点击调整的形式（像已有的 +/- 按钮），放在一个居中的弹窗面板中：

```
┌──────────────────────────────────┐
│      Custom Particle Config      │
│                                  │
│  Mass    1.0e25  kg   [-]  [+]   │
│  Charge  0.0     C    [-]  [+]   │
│  Speed   1.0e4  m/s   [-]  [+]   │
│  Radius  6  px  (auto)           │
│                                  │
│        [  OK  ]  [ Cancel ]      │
└──────────────────────────────────┘
```

这种方式复用已有的 Button 和 HUD 绘制模式，实现更简单。

### 预览圆渲染

在 `src/rendering/renderer.py` 中添加新方法或修改 `render`：

```python
def draw_placement_preview(self, world_x, world_y, radius_world, camera):
    """绘制虚线放置预览圆 + 十字准星。"""
```

使用 `pygame.draw.circle` 或 `pygame.gfxdraw` 绘制虚线圆。虚线可以用一圈小线段或点模拟。

### 箭头渲染

在 `render` 阶段，当 `custom_placement_stage == 3` 时绘制：

```python
def draw_velocity_arrow(self, start_world, end_screen, actual_speed, max_speed, camera):
    """绘制速度方向箭头。"""
```

- 从 `start_world`（世界坐标）到 `end_screen`（鼠标屏幕位置）转换世界坐标
- 限制最大长度 200px
- 使用 `pygame.draw.line` + 箭头三角形

### 交互控制

主循环中处理 `CLICK` 命令时，根据 `custom_placement_stage` 分支：

```python
if custom_placement_stage > 0:
    # 处理放置流程的鼠标点击
    ...
elif active_tool == "TOOL_CUSTOM":
    # 激活放置流程：打开弹窗
    custom_placement_stage = 1
    ...
```

## 文件修改清单

| 文件 | 改动 |
|------|------|
| `src/rendering/renderer.py` | 新增 `draw_placement_preview()` 和 `draw_velocity_arrow()` 方法 |
| `src/main.py` | 新增放置流程状态变量 + 三阶段交互逻辑 |
| `src/rendering/hud.py` | 移除旧的 `custom_param_buttons` 和参数面板，或在激活工具时触发弹窗 |

## 验收标准

1. 点击 C 工具 → 时间冻结 → 显示参数弹窗
2. 弹窗中可调节 Mass/Charge/Speed，点 OK 关闭
3. 虚线预览圆跟随鼠标，左键固定位置
4. 箭头从固定位置指向鼠标，长度限制 200px
5. 再次点击左键 → 天体放置在预览位置，以箭头方向和比例速度发射
6. 任意阶段 Esc/右键 可取消，时间恢复
7. 所有已有测试通过
