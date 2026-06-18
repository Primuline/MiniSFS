# 探测器火箭控制功能任务书

## 1. 用户需求

用户希望将 `Probe` 从普通探测器升级为带动力源的火箭：

1. 双击探测器进入探测器参考系后，可用方向键上下左右喷气运动。
2. 生成探测器时弹出类似自定义天体的参数窗口，让用户定义总质量、燃料质量、排气速度等，并提供合理默认值。
3. 处于探测器参考系时，在右上角显示剩余燃料，且不能与现有 GUI 重叠。

## 2. 需求理解

本功能只在“参考系目标是探测器”时启用手动喷气。普通星球/恒星参考系仍保持现有方向键平移相机行为。

探测器火箭参数建议包含：

- `total_mass`：初始总质量，单位 kg。
- `fuel_mass`：当前燃料质量，单位 kg。
- `dry_mass`：干质量，单位 kg，满足 `dry_mass = total_mass - fuel_mass`。
- `exhaust_velocity`：排气速度，单位 m/s。
- `mass_flow_rate`：燃料消耗率，单位 kg/s，可给默认值并允许用户编辑，或由 UI 默认固定。

喷气方向约定：

- `Up`：火箭向屏幕/世界上方加速。
- `Down`：火箭向下加速。
- `Left`：火箭向左加速。
- `Right`：火箭向右加速。
- 同时按两个方向键时合成为单位方向向量，例如 `Up + Right` 为右上。

## 3. 物理模型

首版采用连续推力近似，由齐奥尔科夫斯基火箭方程的微分形式得到：

```text
thrust = exhaust_velocity * mass_flow_rate
acceleration = thrust / current_mass
fuel_used = mass_flow_rate * dt
delta_v = direction * acceleration * dt
```

每帧喷气时：

1. 读取当前探测器质量 `current_mass`。
2. 消耗燃料 `fuel_used = min(fuel_mass, mass_flow_rate * effective_dt)`。
3. 使用实际消耗燃料对应的有效 `dt_burn = fuel_used / mass_flow_rate`。
4. 更新速度：`v += direction * exhaust_velocity * fuel_used / current_mass`。
5. 更新质量：`MASS = dry_mass + remaining_fuel_mass`。
6. 燃料为 0 时不再施加推力。

这个公式等价于小时间步下的理想火箭动量近似；如需更精确，可在后续迭代使用：

```text
delta_v = exhaust_velocity * ln(m0 / m1)
```

## 4. 数据模型建议

为了小步改动并降低回归风险，首版不扩展 `BodyState` 的 10 列结构。

建议在 `src/main.py` 维护一个 sidecar：

```python
@dataclass
class ProbeRocketState:
    dry_mass: float
    fuel_mass: float
    exhaust_velocity: float
    mass_flow_rate: float
```

使用 `dict[int, ProbeRocketState]` 以当前 body row index 为 key。因为当前项目删除天体后会压缩数组，必须提供 helper 在删除/碰撞压缩后同步 remap 或清理失效 key。

验收时必须覆盖：

- 删除探测器后不会留下错误燃料显示。
- 非探测器不显示燃料也不接受喷气。
- 新生成探测器有对应 rocket state。

后续如需要稳定 ID，可由 `architect` 另开任务设计 `BodyState` ID 字段或实体 registry。

## 5. UI/交互设计

### 5.1 探测器参数弹窗

当用户选择 `TOOL_PROBE` 并开始放置探测器时，应先弹出探测器参数窗口。

窗口行为参考现有 `ScientificInputDialog` / 自定义粒子弹窗：

- 字段：总质量、燃料质量、排气速度、燃料消耗率、半径。
- 支持科学计数法输入。
- 默认值建议：
  - 总质量：`1.0e5 kg`
  - 燃料质量：`7.0e4 kg`
  - 排气速度：`3.0e3 m/s`
  - 燃料消耗率：`50 kg/s`
  - 半径：沿用当前 probe 默认半径或允许 km 输入。
- 校验：
  - 总质量 > 0
  - 0 <= 燃料质量 < 总质量
  - 排气速度 > 0
  - 燃料消耗率 > 0
  - 半径 > 0

确认后进入现有放置流程：选择位置，再拖拽设定初速度。

### 5.2 方向键喷气

现有方向键用于相机平移。新增规则：

- 如果 `reference_body_id` 指向活跃探测器，则方向键用于探测器喷气，不再平移相机。
- 如果没有进入探测器参考系，方向键保持现有相机平移行为。
- 如果参考系目标不是探测器，方向键保持现有相机平移行为。

### 5.3 剩余燃料显示

处于探测器参考系时，右上角显示燃料信息：

```text
Fuel: 68.4%
Fuel Mass: 6.84e4 kg
```

布局要求：

- 不与现有左上角 status info、左侧工具栏、底部时间控制、右下角比例尺重叠。
- 建议放置在右上角，留出 `20px` 外边距。
- 若未来右上角已有面板，需自动向下偏移或合并到 HUD 的参考系信息区域。

## 6. 涉及模块

预计修改：

- `src/config.py`
  - 新增探测器火箭默认常量。
- `src/main.py`
  - 管理 probe rocket sidecar。
  - 探测器放置流程接入参数窗口。
  - 探测器参考系方向键喷气。
  - 将燃料状态传递给 HUD。
- `src/rendering/hud.py`
  - 新增探测器参数弹窗或复用现有输入弹窗。
  - 新增右上角燃料显示。
- `src/rendering/input_dialog.py`
  - 如现有基础弹窗可复用，则新增 `ProbeInputDialog`。
- `README.md`
  - 更新 Probe 创建和方向键喷气控制说明。
- `docs/probe-rocket-control-spec.md`
  - 若实现完成，将本任务书转为正式功能规格。
- `tests/`
  - 添加参数校验、燃料消耗、HUD 状态或输入命令相关测试。

## 7. 子 Agent 分工

### 7.1 architect

目标：确认数据模型和跨模块边界。

输出：

- 是否采用 sidecar 或扩展 `BodyState`。
- 是否需要稳定 body id。
- 推荐的函数/API 边界。

### 7.2 physics-engine

目标：实现或提供火箭喷气计算的纯函数，避免把物理公式硬编码在 UI 中。

建议写入：

- `src/physics/rocket.py`
- 对应 `tests/test_rocket.py`

输出：

- 燃料消耗与速度增量计算函数。
- 边界测试：无燃料、质量非法、斜向输入归一化。

### 7.3 rendering-ui

目标：实现探测器参数输入窗口、右上角燃料 HUD、方向键上下文行为接入。

注意：

- 不破坏现有自定义粒子窗口。
- 不与现有 GUI 重叠。
- 方向键在探测器参考系下不再触发相机平移。

### 7.4 tester

目标：并行验证实现结果。

测试：

- `pytest tests/ -q`
- 针对 rocket 公式新增单元测试。
- 针对 Probe 参数校验新增测试。
- 手动验证：运行 `python -m src.main`，放置探测器，双击进入参考系，方向键喷气，燃料减少。

## 8. 验收标准

- 能创建带自定义火箭参数的探测器。
- 双击探测器进入参考系后，方向键改变探测器速度且消耗燃料。
- 燃料为 0 时方向键不再产生加速度。
- 探测器质量随燃料消耗降低，但不低于干质量。
- 非探测器参考系方向键仍用于相机平移。
- 右上角燃料显示不与现有 HUD 重叠。
- 全量测试通过：`pytest tests/ -q`。

## 9. 风险与注意事项

- 当前 `BodyState` 没有稳定实体 ID，删除/合并后 row index 会变化，sidecar 必须同步清理或重映射。
- `src/main.py` 已经较大，新增流程应尽量用 helper 函数隔离。
- 探测器喷气会与现有右键发射/拖拽设定速度共存，不能破坏已有流程。
- 如引入新弹窗，需避免和 `custom_dialog_visible`、`_edit_dialog.visible` 状态冲突。

