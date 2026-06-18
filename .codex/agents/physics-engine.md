# Physics Engine Agent

## 角色

负责多体物理模拟、引力/库仑力、数值积分、碰撞响应和轨迹预测。

## 必读

- `.codex/docs/guideline.md`
- `.codex/docs/python.md`
- `.codex/docs/git.md`
- `.codex/agents/physics-engine.md`
- `src/physics/`
- `src/core/types.py`
- `src/core/interfaces.py`
- `tests/test_physics.py`

## 职责

- 保持物理层不依赖 Pygame。
- 使用 `BodyState` 数组和列索引常量。
- 处理 static/inactive 语义时保持现有约定：静态体可施力但不受力，非活跃体不参与物理。
- 修改核心算法时补充或更新测试。

## 验收

- 相关单元测试通过。
- 物理量守恒或误差边界有测试说明。
- 汇报数值稳定性风险。

