# 右键编辑天体参数 + 恒星放置简化 + 默认值调整

## 1. 恒星放置简化

当前 S/P/D 工具都是两步流程（预览位置 → 设定速度方向）。改为：
- **S (Star) 工具**：选择后时间冻结，只预览位置（虚线圆跟随鼠标），左键点击直接放置。
  放置时 `make_body(..., is_static=True)`，且**不经过速度设定步骤**。
- **P (Planet) / D (Probe) 工具**：保持现有两步流程不变（预览位置 → 设定速度方向）。

修改在 `src/main.py` 中的 `simple_placement_stage` 控制：
- TOOL_STAR 激活时 → `simple_placement_stage = 1`（冻结，预览）
- CLICK 在 Stage 1 时判断 tool 类型：
  - 如果是 TOOL_STAR → 直接放置（`is_static=True`），取消时间冻结，结束流程
  - 如果是 TOOL_PLANET / TOOL_PROBE → 进入 Stage 2（设定速度方向）
- CLICK 在 Stage 2 时（只有 P/D 会到 Stage 2）→ 用箭头方向速度放置

## 2. 自定义默认值

修改 `src/rendering/input_dialog.py` 中 `FIELD_DEFS`：
```
Mass coeff: 1.0, Mass exp: 26
Charge coeff: 0.0, Charge exp: 0
Speed coeff: 5.0, Speed exp: 1
```
同时更新 `src/config.py` 中的 `CUSTOM_MASS_DEFAULT` = `1.0e26`。

## 3. 右键编辑天体参数

### 触发条件

当玩家**选中了一个天体**（`selected_body_id is not None`），且在空白处（或即使在天体上）**右键点击**时：
- 如果当前已经在天体上右键点击（`found_id is not None`），选择那个天体并进行编辑
- 如果右键在空白处，但有选中的天体，编辑当前选中天体
- 弹出编辑弹窗，包含质量和电荷的输入（**没有速率**），使用科学计数法输入

### 弹窗

复用 `ScientificInputDialog` 或创建一个简化版本 `EditBodyDialog`，包含：
- Mass: 系数 × 10^指数 (kg) — 预填当前天体的质量值
- Charge: 系数 × 10^指数 (C) — 预填当前天体的电荷值
- 没有 Speed 输入
- OK / Cancel 按钮

弹窗技术实现：可以修改 `ScientificInputDialog` 使其支持配置字段数量（3 字段或 2 字段），或者新建 `EditBodyDialog` 类。

### 确认后的行为

OK 后：
- 将天体的质量设为新值
- 将天体的电荷设为新值
- 半径自动更新：`radius = CUSTOM_RADIUS_FACTOR * sqrt(mass / CUSTOM_MASS_DEFAULT)`（像素），再转世界单位
- 关闭弹窗

Cancel → 关闭弹窗，不做任何修改。

## 文件修改清单

| 文件 | 改动 |
|------|------|
| `src/main.py` | S 工具跳过 Stage 2；右键选中天体时弹出编辑弹窗 |
| `src/rendering/input_dialog.py` | 添加 `EditBodyDialog` 类（只有 Mass/Charge）或使 `ScientificInputDialog` 可配置字段数 |
| `src/config.py` | `CUSTOM_MASS_DEFAULT` → `1.0e26` |
| `src/rendering/hud.py` | 可能需要集成 EditBodyDialog 的事件和绘制（类似 input_dialog） |

## 验收标准

1. 选 S 工具 → 虚线圆跟随 → 左键直接放置静态恒星（无箭头步骤）
2. 自定义默认值：1.0×10²⁶ kg, 0 C, 5×10¹ km/s
3. 选中天体后右键 → 弹窗编辑质量/电荷
4. 修改后天体半径自动更新
5. 所有测试通过
