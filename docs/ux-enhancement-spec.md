# UX 增强规格文档 — MiniSFS

## 概述

对 MiniSFS 进行 5 项体验优化。所有功能默认关闭或自动工作，用户通过快捷键切换，互不干扰。

---

## 1. 坐标网格 (Grid Overlay)

**触发**: `G` 键切换 `show_grid` 布尔值  
**绘制函数**: `draw_grid(surface, camera, color, alpha)` 在 effects.py 中  
**绘制层**: 在所有天体**之后**、HUD **之前**渲染

### 渲染规则
- 网格间距：根据 `camera.zoom` 自适应
  - zoom < 0.01 → 间距 1e12 m (100 万 km 级)
  - zoom < 0.1 → 间距 1e11 m
  - zoom < 1.0 → 间距 1e10 m
  - zoom < 10 → 间距 1e9 m
  - 否则 → 间距 1e8 m
- 从相机视野左上角开始绘制，覆盖整个屏幕
- 线宽 1px，颜色 `(40, 40, 80, 120)`（来自 `GRID_COLOR` / `GRID_ALPHA` config）
- 使用 `_draw_alpha_line`（effects.py 已有）绘制半透明线

### 实现
```python
def draw_grid(surface, camera):
    color = (*GRID_COLOR, GRID_ALPHA)
    left, top, right, bottom = camera.get_screen_rect_world()
    
    zoom = camera.zoom
    if zoom < 0.01:      spacing = 1e12
    elif zoom < 0.1:     spacing = 1e11
    elif zoom < 1.0:     spacing = 1e10
    elif zoom < 10:      spacing = 1e9
    else:                spacing = 1e8
    
    start_x = math.floor(left / spacing) * spacing
    start_y = math.floor(top / spacing) * spacing
    
    x = start_x
    while x <= right:
        sx, _ = camera.world_to_screen(x, 0)
        _draw_alpha_line(surface, color, (sx, 0), (sx, camera.height), 0.5)
        x += spacing
    
    y = start_y
    while y <= bottom:
        _, sy = camera.world_to_screen(0, y)
        _draw_alpha_line(surface, color, (0, sy), (camera.width, sy), 0.5)
        y += spacing
```

---

## 2. 比例尺 (Scale Bar)

**绘制位置**: HUD 右下角，`SCALE_BAR_X`/`SCALE_BAR_Y`  
**始终显示**: 不依赖 toggle（除非隐藏所有 HUD）

### 渲染规则
- 根据当前 zoom 计算一条"好看"的世界距离
- 目标：`200 * zoom * WORLD_SCALE` 在屏幕上约 200px  
- 取整到 1/2/5 的整数倍（如 1e9, 2e9, 5e9, 1e10…）
- 绘制一条水平条，**两端竖线**，中间标注文字
- 文字格式: "1 亿 km" / "100 万 km" / "10 万 km"

### 实现 (HUDManager 中)
```python
def _draw_scale_bar(self, surface, camera):
    raw = 200 * camera.zoom * camera.world_scale  # 约 200px 对应的世界距离
    
    # 取整到 1/2/5 倍数
    magnitude = 10 ** math.floor(math.log10(raw))
    normalized = raw / magnitude
    if normalized < 1.5:     scaled = 1 * magnitude
    elif normalized < 3.5:   scaled = 2 * magnitude
    elif normalized < 7.0:   scaled = 5 * magnitude
    else:                    scaled = 10 * magnitude
    
    screen_length = scaled / (camera.zoom * camera.world_scale)
    
    x = self.width - SCALE_BAR_X - int(screen_length)
    y = self.height - SCALE_BAR_Y
    
    # 水平线
    pygame.draw.line(surface, (200,200,220), (x, y), (x + int(screen_length), y), 2)
    # 两端竖线
    pygame.draw.line(surface, (200,200,220), (x, y-3), (x, y+3), 2)
    pygame.draw.line(surface, (200,200,220), (x + int(screen_length), y-3), (x + int(screen_length), y+3), 2)
    
    # 文字
    if scaled >= 1e12:
        text = f"{scaled/1e12:.0f} 万亿 km"
    elif scaled >= 1e9:
        text = f"{scaled/1e9:.0f} 亿 km"
    elif scaled >= 1e6:
        text = f"{scaled/1e6:.0f} 百万 km"
    elif scaled >= 1e3:
        text = f"{scaled/1e3:.0f} 千 km"
    else:
        text = f"{scaled:.0f} m"
    
    text_surf = self._font_small.render(text, True, (200,200,220))
    tr = text_surf.get_rect(midtop=(x + int(screen_length)//2, y+6))
    surface.blit(text_surf, tr)
```

---

## 3. 平滑相机跟随 (Smooth Camera Follow)

**改动文件**: `camera.py`  
**机制**: 参考系模式下，`main.py` 每帧不直接调用 `camera.follow(wx, wy)`，而是用 lerp 逐步逼近目标位置。

### 实现

在 `Camera` 类中新增方法：
```python
def update_follow(self, target_x: float, target_y: float, lerp_factor: float = None):
    """平滑跟随目标位置。"""
    if lerp_factor is None:
        lerp_factor = CAMERA_FOLLOW_LERP
    self.center_x += (target_x - self.center_x) * lerp_factor
    self.center_y += (target_y - self.center_y) * lerp_factor
```

在 `main.py` 中，参考系跟随改为：
```python
# 旧：camera.follow(wx, wy)
# 新：
camera.update_follow(wx, wy)
```

注意：`follow()` 方法保留不变（用于 R 键重置、瞬移等场景）。

---

## 4. 天体标签 (Body Labels)

**触发**: `L` 键切换 `show_labels` 布尔值  
**绘制函数**: `draw_body_labels(surface, bodies, camera)` 在 effects.py 中  
**绘制层**: 在天体之后、HUD 之前渲染

### 渲染规则
- 遍历所有活跃天体，调用 `camera.world_to_screen()` 计算屏幕位置
- 如果天体的屏幕半径 < `LABEL_MIN_SCREEN_RADIUS` (3px)，跳过
- 标签文字格式：`"Star #0"` / `"Planet #1"` / `"Probe #2"`
- 文字在天体上方 `LABEL_OFFSET_Y` (-12) 像素处
- 背景：半透明黑色矩形（`LABEL_BG_ALPHA=100`），padding 2px
- 文字颜色：根据天体类型
  - Star: (255, 220, 100)
  - Planet: (100, 200, 255)  
  - Probe: (200, 220, 255)
  - Charged: (255, 100, 100)

### 实现
```python
def draw_body_labels(surface, bodies, camera):
    for i in range(bodies.shape[0]):
        if bodies[i, IS_ACTIVE] == 0.0: continue
        sx, sy = camera.world_to_screen(float(bodies[i, X]), float(bodies[i, Y]))
        radius = float(bodies[i, RADIUS])
        screen_radius = camera.world_distance_to_screen(radius)
        if screen_radius < LABEL_MIN_SCREEN_RADIUS: continue
        
        btype = int(bodies[i, BODY_TYPE])
        type_names = {0: "Star", 1: "Planet", 2: "Probe", 3: "Charged"}
        label = f"{type_names.get(btype, '?')} #{i}"
        
        type_colors = {0: (255, 220, 100), 1: (100, 200, 255), 2: (200, 220, 255), 3: (255, 100, 100)}
        text_color = type_colors.get(btype, (200, 200, 200))
        
        font = pygame.font.Font(None, LABEL_FONT_SIZE)
        text_surf = font.render(label, True, text_color)
        tr = text_surf.get_rect(midbottom=(sx, sy + LABEL_OFFSET_Y))
        
        bg = pygame.Surface((tr.width+4, tr.height+4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, LABEL_BG_ALPHA))
        surface.blit(bg, (tr.x-2, tr.y-2))
        surface.blit(text_surf, tr)
```

---

## 5. 快捷键面板 (Shortcuts Overlay)

**触发**: `H` 键切换 `show_shortcuts` 布尔值  
**绘制函数**: `draw_shortcuts_overlay(surface)` 在 effects.py 中  
**绘制层**: 最顶层（HUD 之上）

### 渲染规则
- 半透明黑色背景覆盖屏幕 80%
- 居中显示快捷键列表
- 文本颜色白色，标题稍大
- 按列排列，每行一对 `"键位 — 功能"`

### 快捷键列表
```
=== 快捷键 ===
Space  — 暂停/继续      R  — 重置视角
G      — 网格开关        L  — 天体标签开关
H      — 关闭此面板      F  — 2x 加速
6      — 4x 加速        7  — 8x 加速
0      — 1x 倍速        T  — 尾迹开关
1~4    — 工具选择        Del — 删除选中
右键   — 编辑/瞄准      滚轮 — 缩放
双击   — 参考系跟随     拖拽 — 移动天体
Esc    — 退出菜单/取消

按 H 或 Esc 关闭此面板
```

### 实现
```python
def draw_shortcuts_overlay(surface):
    # 半透明背景
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (0, 0))
    
    title_font = pygame.font.Font(None, 28)
    font = pygame.font.Font(None, 18)
    
    title = title_font.render("快捷键 (按 H 或 Esc 关闭)", True, (255,255,255))
    tr = title.get_rect(midtop=(WINDOW_WIDTH//2, 60))
    surface.blit(title, tr)
    
    shortcuts = [
        ("Space", "暂停/继续"), ("R", "重置视角"),
        ("G", "网格开关"), ("L", "天体标签"),
        ("6", "4x 加速"), ("7", "8x 加速"),
        ("0", "1x 倍速"), ("T", "尾迹开关"),
        ("1~4", "工具选择"), ("Del", "删除选中"),
        ("右键", "编辑/瞄准"), ("滚轮", "缩放"),
        ("双击", "参考系跟随"), ("拖拽", "移动天体"),
        ("Esc", "退出菜单/取消"),
    ]
    
    col1_x = WINDOW_WIDTH//2 - 180
    col2_x = WINDOW_WIDTH//2 + 20
    start_y = 110
    
    for i, (key, desc) in enumerate(shortcuts):
        col = i % 2
        row = i // 2
        x = col1_x if col == 0 else col2_x
        y = start_y + row * 30
        
        key_surf = font.render(key, True, (255, 220, 100))
        surface.blit(key_surf, (x, y))
        desc_surf = font.render(desc, True, (200, 200, 220))
        surface.blit(desc_surf, (x + 70, y))
```

---

## 6. FPS / 状态信息 (HUD Info)

**改动文件**: `hud.py` 新增 `_draw_status_info()`  
**位置**: 屏幕左上角 (8, 8)  
**始终可见**（默认），不依赖 toggle

### 显示内容
```
天体: 12  |  倍速: 4x  |  FPS: 60
鼠标: (1.23e11, 4.56e10) m
```

- 第一行：天体数、当前倍速、FPS
- 第二行：鼠标世界坐标（仅当鼠标在游戏区域时显示）
- 背景：半透明暗色矩形

### 传递数据
`main.py` 在每帧调用 `hud.draw()` 之前更新：
```python
hud.set_status_info(
    num_bodies=bodies.shape[0],
    time_speed=time_multiplier,
    fps=clock.get_fps(),
    mouse_world_pos=(mouse_wx, mouse_wy),
)
```

---

## 快捷键总表 (handler.py 改动)

| 键 | 命令 | 功能 |
|---|------|------|
| `G` | `TOGGLE_GRID` | 切换网格显示 |
| `L` | `TOGGLE_LABELS` | 切换天体标签 |
| `H` | `TOGGLE_SHORTCUTS` | 切换快捷键面板 |
| `6` | `FAST_4X` | 4x 加速（原 g） |
| `7` | `FAST_8X` | 8x 加速（原 h） |
| `F` | `FAST_2X` | 2x 加速（不变） |
| `T` | `TOGGLE_TRAILS` | 尾迹开关（不变） |

注意：`G` 原先没有绑定，`L` 原先没有绑定，`H` 原先绑定了 `FAST_8X` → 改为 `TOGGLE_SHORTCUTS`。  
`FAST_4X` 从 `g` 移到 `6`，`FAST_8X` 从 `h` 移到 `7`。

---

## 实现顺序 & 依赖

```
config.py  (新增常量) ──→  handler.py  (新增键绑定)
     │                          │
     ├──→ effects.py (grid, labels, shortcuts)
     │         │
     │         └──→ renderer.py (集成绘制)
     │
     ├──→ camera.py (smooth follow)
     │
     └──→ hud.py (status info, scale bar)
               │
               └──→ main.py (集成所有 + toggle states)
```

所有任务的常量、命令字符串、函数签名在此文档中约定，子 agent 可**并行**实现。
