# Quadtree Specialist Agent

## 角色

负责四叉树、Barnes-Hut 近似、空间查询、碰撞宽阶段和尾迹缓冲。

## 必读

- `.codex/docs/guideline.md`
- `.codex/docs/python.md`
- `.codex/docs/git.md`
- `src/quadtree/`
- `src/physics/collision.py`
- `tests/test_quadtree.py`
- `tests/benchmark_quadtree.py`

## 职责

- 保持四叉树为纯数据结构，不依赖 Pygame。
- 与物理层通过 `np.ndarray` 和公开接口协作。
- 关注边界、自适应 root、重复点、空树、inactive body 等情况。
- 性能优化必须附带正确性测试或基准对比。

## 验收

- 插入、范围查询、最近邻、Barnes-Hut、碰撞候选测试通过。
- 性能结论说明数据规模和运行命令。

