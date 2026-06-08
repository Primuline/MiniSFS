# 左键框选功能

## 概述
玩家按住左键拖拽时，如果以空白处为起点（不在任何天体上），画出一个蓝色半透明矩形框，框内天体全部被选中（高亮）。

## 交互

### 触发条件
- 左键按下时没有点击在任何天体上
- 拖拽距离 > 10px 才显示选框（避免和点击混淆）

### 视觉
- 蓝色半透明矩形 (0, 100, 255, 60)
- 边框为实线蓝色 (0, 150, 255)
- 从按下位置到当前鼠标位置

### 选中逻辑
- 天体中心点落在选框内即被选中
- 所有选中的天体显示高亮圈
- 如果有多个天体被选中，在屏幕角落显示 "Selected: 3 bodies"

### 数据管理
- 添加 `selected_body_ids: set[int]` 存储多选结果
- `selected_body_id` 用于单天体操作（如抓取、编辑、跟随），多选不影响它

## 技术实现

### 状态变量
```python
box_select_start: Optional[Tuple[int, int]] = None  # 框选起始屏幕坐标
box_select_end: Optional[Tuple[int, int]] = None     # 框选当前屏幕坐标
selected_body_ids: set = set()                        # 多选天体 ID 集合
```

### 交互流程
1. **MOUSEBUTTONDOWN (左键)**：handler 检测到没点在天体上 → 返回 `BOX_SELECT_START:x,y`
2. **MOUSEMOTION**：如果 box_select_start 不为空 → 更新 end 坐标
3. **MOUSEBUTTONUP (左键)**：如果拖拽距离 > 10px → 计算选框内的天体 → 返回 `BOX_SELECT_END:x1,y1,x2,y2`
   如果拖拽距离 <= 10px → 视为普通点击

现有 handler 中左键按下的逻辑是：先检测是否点在天体上（GRAB_START），否则返回 CLICK。框选应该插入在两者之间——检测是否点在天体上，如果没点上则确认是否要框选还是普通点击。

其实更简单的方式：在 main.py 的 CLICK 处理中，如果 `is_dragging` 为 True 且拖拽距离 > 10px，且在空白处开始，就进入框选模式。

### 渲染
在 `renderer.py` 中添加 `draw_box_selection(surface, start, end)`：
```python
if start and end:
    x1, y1 = min(start[0], end[0]), min(start[1], end[1])
    x2, y2 = max(start[0], end[0]), max(start[1], end[1])
    pygame.draw.rect(surface, (0, 100, 255, 60), (x1, y1, x2-x1, y2-y1))
    pygame.draw.rect(surface, (0, 150, 255), (x1, y1, x2-x1, y2-y1), 1)
```

### 多选高亮
在 `_draw_selection_highlight` 中，除了绘制 `selected_body_id` 的高亮外，也绘制 `selected_body_ids` 中所有天体的高亮。

## 文件修改
| 文件 | 改动 |
|------|------|
| `src/main.py` | 状态变量 + 框选交互逻辑 + 选框渲染调用 |
| `src/rendering/renderer.py` | `draw_box_selection()` 方法 + 多选高亮 |
