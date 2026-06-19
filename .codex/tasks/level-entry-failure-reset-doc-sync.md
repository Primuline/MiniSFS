# Task: level entry failure reset, Level 2 probe tuning, README/MAIN sync

## 必读文档

- `.codex/AGENT.md`
- `.codex/docs/guideline.md`
- `.codex/docs/python.md`
- `.codex/docs/git.md`
- `.codex/docs/delegation.md`
- `.codex/docs/project-memory.md`
- `.codex/docs/architecture.md`
- `.codex/docs/contracts.md`
- `.codex/docs/testing.md`
- `.codex/docs/pitfalls.md`
- `.codex/agents/game-designer.md`
- `.codex/agents/rendering-ui.md`
- `.codex/agents/tester.md`

## 背景

用户报告：

1. 某次关卡中探测器消失后，之后无法进入任何关卡，每次进入都会提示“探测器消失”。
2. 关卡 2 刚进入就提示“探测器消失”。
3. README 与 MAIN 已落后于 `.codex/docs/`，需要按新文档修正。
4. 关卡 2 默认探测器参数应为：
   - total mass `2.5 t`
   - fuel mass `1 t`
   - exhaust velocity `300 km/s`
   - mass flow `1 mg/s`
   - landing speed limit `1 km/s`

## 目标

- 重新进入任意关卡时，清空旧的失败/成功状态、旧碰撞事件、旧探测器 sidecar、旧 HUD 失败弹窗状态。
- Level 2 开局不能因为上一关残留事件或初始碰撞误判直接失败。
- Level 2 探测器 sidecar 使用指定参数，单位换算为 SI：
  - total mass `2500 kg`
  - fuel mass `1000 kg`
  - dry mass `1500 kg`
  - exhaust velocity `300000 m/s`
  - mass flow `1e-6 kg/s`
  - landing speed limit `1000 m/s`
- README 与 MAIN 同步当前事实：模式菜单、Level 1/2、右键探测器编辑、探测器落地/坠毁规则、时间控制、拖拽/平移、单色几何 UI、打包说明等。

## 非目标

- 不重新设计 debug mode；上一轮已记录为待澄清。
- 不重构整个 `src/main.py`。
- 不修改 `BodyState` shape。
- 不恢复右键探测器瞄准线。

## 允许修改范围

- `src/main.py`
- `src/config.py`
- `assets/levels/level_2.json`
- `tests/*.py`
- `README.md`
- `MAIN.md`
- `.codex/docs/*.md`
- `.codex/tasks/current-state.md`

## 禁止修改范围

- 不执行破坏性 git 操作。
- 不创建 `.codex/worktrees/` 外的工作区。
- 不提交 `build/` 或 `dist/`。
- 不让关卡参数使用非 SI 内部单位。

## 验收标准

- Level 1/2 开始时不会继承上一局“探测器消失”失败弹窗。
- Level 2 刚进入不会直接失败。
- Level 2 probe rocket state 与用户指定参数一致。
- README/MAIN 不再描述旧的右键探测器瞄准、旧时间倍率、旧碰撞规则为当前行为。
- 相关 focused tests 与 `pytest tests -q` 通过。

## 测试命令

```powershell
pytest tests\test_level_1_scene.py tests\test_mode_menu.py tests\test_physics.py -q
pytest tests -q
```

## 分工建议

- `game-designer`: 检查并修复关卡进入/失败状态清理与 Level 2 参数。
- `tester`: 为关卡重进、Level 2 初始状态、Level 2 probe 参数补充回归测试。
- `documentation`: README/MAIN 由 Chief 或文档 worker 同步。

## 汇报格式

- Files changed
- Behavior changed
- Tests run
- Risks
- Open questions
