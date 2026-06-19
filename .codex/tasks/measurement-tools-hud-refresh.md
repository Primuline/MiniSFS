# Task: measurement tools and live HUD refresh

## 必读文档

- `.codex/AGENT.md`
- `.codex/docs/guideline.md`
- `.codex/docs/python.md`
- `.codex/docs/git.md`
- `.codex/docs/project-memory.md`
- `.codex/docs/architecture.md`
- `.codex/docs/contracts.md`
- `.codex/docs/testing.md`
- `.codex/agents/rendering-ui.md`
- `.codex/agents/tester.md`

## 背景

用户报告并请求：

1. 右上角天体信息状态栏没有实时更新。
2. TOOLS 栏新增：
   - 长度测量：点击工具后暂停。左键固定 A，绘制 A 到鼠标线段并标注长度；左键固定 B 后保留 AB 和长度直到退出；右键取消当前绘制或退出测量。
   - 角度测量：点击工具后暂停。左键依次固定 A、B、C，绘制 AB、BC 并标注角 ABC 度数；右键取消当前绘制或退出测量。
   - 自动吸附到天体。
   - G/L 对应网格和信息显示也加入 TOOLS。
3. 更新或清除 H 快捷键菜单中的快捷键。

## 目标

- 选中天体的信息面板每帧反映当前 `BodyState`。
- HUD toolbar 有 length/angle/grid/labels 工具按钮。
- 测量工具使用世界坐标，渲染时随相机缩放/平移正确显示。
- 测量点自动吸附到靠近鼠标的天体中心。
- 测量工具开启时暂停；退出测量时恢复进入工具前的暂停状态。
- H 快捷键菜单不展示过期快捷键。

## 非目标

- 不修改物理规则。
- 不改 Level 2 新数值之外的关卡设计。
- 不实现复杂测量对象管理或保存。

## 允许修改范围

- `src/main.py`
- `src/rendering/hud.py`
- `src/rendering/effects.py`
- `src/rendering/renderer.py`
- `tests/*.py`
- `.codex/docs/*.md`
- `.codex/tasks/current-state.md`

## 验收标准

- 右上信息栏随选中天体的坐标/速度/质量变化实时刷新。
- 长度测量可预览和固定线段，显示长度。
- 角度测量可预览和固定角，显示角度（degrees）。
- 右键取消当前测量或退出工具。
- 网格/标签按钮与 G/L 快捷键使用同一状态。
- 相关测试通过。

## 汇报格式

- Files changed
- Behavior changed
- Tests run
- Risks
- Open questions
