# 参考系、拖尾、模式入口与黑白几何 GUI 任务书

## 1. 用户输入

### Bug

1. 进入参考系后天体确实在中心，但如果此时暂停，天体会向行进方向的反方向偏移。

### 需求

1. 参考系拖尾：在参考系下，天体拖尾应改为相对参考天体的拖尾，而不是绝对世界坐标拖尾。切换参考系时清除所有拖尾即可。
2. 进入游戏界面时分为两个模式：
   - 关卡模式：暂时不管。
   - 沙盒模式：点击后进入当前初始界面。
3. GUI 优化：
   - 优化所有现有 GUI。
   - 去掉星空背景。
   - 用简洁黑白几何图形代表实体：星星用圆，恒星用旋转的正 17 边形，探测器用三角形。
   - 其它 GUI 使用黑白像素边框。
   - 字体文件已放入 `src/ttf/`。

## 2. 现状与约束

- 当前 `src/main.py` 直接进入 `GAME_STATE_PLAYING`，没有入口模式菜单。
- 参考系由 `reference_body_id` 管理，相机每帧调用 `camera.update_follow()`。
- `camera.update_follow()` 支持速度前馈；暂停时若仍传入非零 `dt`，会导致镜头预测目标未来位置，引发画面偏移。
- 当前拖尾由 `TrailBuffer` 存储世界坐标，渲染器直接按世界坐标绘制。
- 当前背景由 `StarField` 绘制，实体绘制含彩色、发光、渐变和阴影。
- 当前字体多处使用 `pygame.font.Font(None, size)`；可改为加载 `src/ttf/ark-pixel-10px-monospaced-latin.ttf`，必要时对中文使用 `zh_cn` 字体。

## 3. 需求理解与设计建议

### 3.1 参考系暂停偏移

修复策略：

- 在参考系跟随逻辑中，暂停或抓取时不进行速度前馈。
- 建议：

```python
follow_dt = 0.0 if is_paused or is_grabbing else TIME_STEP * time_speed
camera.update_follow(ref_wx, ref_wy, ref_vx, ref_vy, follow_dt)
```

这样暂停时镜头只向当前位置收敛，不再预测未来位置。

### 3.2 参考系拖尾

要求“相对参考天体的拖尾”。首版建议采用渲染前转换，不修改 `TrailBuffer` 存储结构：

- 进入任何参考系时：`trail_buffer.clear_all()`。
- 切换参考系时：`trail_buffer.clear_all()`。
- 退出参考系时：`trail_buffer.clear_all()`。
- 在参考系内记录/渲染时，把其它天体轨迹转换到当前参考天体附近：

```text
relative_point = trail_point - reference_current_position
display_point = relative_point + reference_current_position
```

由于切换参考系会清空拖尾，首版可接受使用“当前参考天体位置”作为统一参考原点。更精确的历史相对拖尾需要同时记录参考天体历史位置，可作为后续任务。

验收现象：

- 进入参考系后旧拖尾消失。
- 参考系内新拖尾不会因相机跟随而显示为绝对世界轨迹。
- 切换/退出参考系后拖尾再次清空。

### 3.3 模式入口

新增启动菜单：

- 初始 `game_state = GAME_STATE_MENU`。
- 显示两个模式按钮：
  - `Level Mode`：暂时 disabled 或点击后无操作/显示 coming soon。
  - `Sandbox Mode`：点击后创建当前默认场景并进入 `GAME_STATE_PLAYING`。
- 保留现有沙盒初始界面作为 Sandbox Mode 的结果。
- `Esc` 在菜单中退出游戏；在游戏中保持现有逻辑。

### 3.4 黑白几何 GUI

视觉目标：

- 背景：纯黑或接近纯黑，不绘制星空粒子背景。
- 实体：
  - 普通星星/行星：白色空心或实心圆。
  - 恒星：白色旋转正 17 边形，可基于 `pygame.time.get_ticks()` 旋转。
  - 探测器：白色三角形，方向可沿速度方向。
  - 带电粒子：圆形加 `+` / `-` 标识，黑白表达。
- GUI：
  - 黑底、白色 1px 或 2px 像素边框。
  - 禁用彩色渐变、半透明彩色面板、发光效果。
  - 按钮、弹窗、HUD、工具栏、时间控制统一黑白像素风。
- 字体：
  - 优先 `src/ttf/ark-pixel-10px-monospaced-latin.ttf`。
  - 如中文显示需要，使用 `src/ttf/ark-pixel-10px-monospaced-zh_cn.ttf`。
  - 建议新增一个字体 helper，避免在多个文件里硬编码字体路径。

## 4. 子 Agent 分工

### 4.1 rendering-ui: 参考系 bug 与拖尾

负责：

- 修复暂停时参考系镜头前馈偏移。
- 进入/切换/退出参考系时清空拖尾。
- 实现参考系相对拖尾显示。
- 添加小范围测试或手动验证说明。

预计修改：

- `src/main.py`
- 必要时 `src/rendering/renderer.py` 或 `src/rendering/effects.py`
- 相关测试

### 4.2 rendering-ui: 模式入口

负责：

- 添加启动菜单。
- 沙盒模式进入当前默认场景。
- 关卡模式暂时 disabled/coming soon。
- 保持 Esc 行为清晰。

预计修改：

- `src/main.py`
- `src/rendering/hud.py` 或新增菜单绘制 helper
- `README.md`
- 相关测试

### 4.3 rendering-ui: 黑白几何 GUI

负责：

- 移除星空背景绘制。
- 重绘实体为黑白几何形状。
- 将 HUD、按钮、弹窗、快捷键面板、燃料面板等改为黑白像素边框风格。
- 接入 `src/ttf/` 字体。

预计修改：

- `src/rendering/renderer.py`
- `src/rendering/effects.py`
- `src/rendering/hud.py`
- `src/rendering/input_dialog.py`
- `src/config.py`
- `README.md`
- 必要测试

### 4.4 tester

负责：

- 设计并运行回归测试。
- 覆盖参考系暂停、拖尾清空、菜单状态、字体加载、UI helper。
- 若视觉验证无法自动化，提供手动验证清单。

## 5. 验收标准

- 暂停时参考系目标不会因速度前馈偏离中心。
- 进入、切换、退出参考系时拖尾清空。
- 参考系中显示相对参考天体的拖尾。
- 启动后先显示模式选择；点击 Sandbox Mode 进入当前默认沙盒界面。
- Level Mode 显示但暂不进入完整关卡流程。
- 星空背景消失。
- 实体使用黑白几何图形绘制。
- GUI 统一黑白像素边框风格。
- 字体从 `src/ttf/` 加载，并有 fallback。
- 全量测试通过：`pytest tests/ -q`。

## 6. Git 注意事项

当前工作区已有上一轮探测器火箭功能的未提交改动，以及用户既有的 `src/game/__init__.py` 删除状态。所有子 agent 必须：

- 不回滚或覆盖既有改动。
- 明确报告自己的修改文件。
- 避免跨任务混改。
- 完成后由 Chief Agent 统一汇总。

