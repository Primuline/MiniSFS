# Task: Level 2 immediate probe loss

## 必读文档

- `.codex/AGENT.md`
- `.codex/docs/guideline.md`
- `.codex/docs/python.md`
- `.codex/docs/git.md`
- `.codex/docs/project-memory.md`
- `.codex/docs/architecture.md`
- `.codex/docs/contracts.md`
- `.codex/docs/testing.md`
- `.codex/docs/pitfalls.md`
- `.codex/agents/physics-engine.md`
- `.codex/agents/game-designer.md`
- `.codex/agents/tester.md`

## 背景

用户反馈上一轮后 Level 2 刚进入仍提示“探测器消失”。上一轮已清理旧
`last_collision_events`，并让 probe 初始不与 Earth 静态重叠，但问题仍存在。

## 目标

- 查明 Level 2 开局失败是否由第一步物理碰撞导致。
- 修复 Level 2 初始状态，使点击任务 OK 后不会立即触发 `probe_crashed` 或无 active probe。
- 保持用户指定 Level 2 probe 参数：
  - total `2500 kg`
  - fuel `1000 kg`
  - dry `1500 kg`
  - exhaust `300000 m/s`
  - mass flow `1.0e-6 kg/s`
  - landing limit `1000 m/s`
- 补充回归测试覆盖 Level 2 开局若干物理步内不应失败。

## 非目标

- 不重新设计完整 Earth-Mars 任务或星历。
- 不修改全局碰撞规则以掩盖关卡初始条件问题。
- 不扩大 debug mode。

## 允许修改范围

- `assets/levels/level_2.json`
- `src/main.py`
- `tests/*.py`
- `.codex/docs/*.md`
- `.codex/tasks/current-state.md`

## 验收标准

- Level 2 初始 bodies 经过至少一次 `PhysicsEngine.update()` 后仍有 active probe。
- 初始若干短物理步内不产生 `probe_crashed`。
- `pytest tests -q` 通过。

## 汇报格式

- Files changed
- Behavior changed
- Tests run
- Risks
- Open questions
