# Chief Agent 并行委派流程

## 1. 接收需求

Chief Agent 先把用户输入转化为任务说明：

- 用户目标
- 非目标
- 涉及模块
- 验收标准
- 风险点
- 需要的测试或验证

必要时先写入 `.codex/tasks/<task-name>.md`，再分派执行。

## 2. 选择子 Agent

根据任务性质选择角色：

- 跨模块接口或目录变化：`architect`
- 物理算法、积分、碰撞、轨迹：`physics-engine`
- 空间索引、Barnes-Hut、尾迹：`quadtree-specialist`
- Pygame 画面、相机、HUD、交互反馈：`rendering-ui`
- 关卡、状态机、玩法、评分：`game-designer`
- 单元测试、集成测试、性能基准：`tester`

同一需求可以拆给多个 agent 并行，例如一个实现 agent 与一个 tester agent。

## 3. 建立隔离工作区

推荐模式：

```powershell
git worktree add ../MiniSFS-<task-agent> -b <type>/<task-agent>
```

每个子 agent 在自己的 worktree 中工作。Chief Agent 负责记录分支名、工作区路径和任务边界。

## 4. 子 Agent 启动提示

Chief Agent 给子 agent 的任务应包含：

- 必读文档列表。
- 任务背景和目标。
- 允许修改的文件范围。
- 不允许修改的文件范围。
- 验收标准。
- 必须运行的测试命令。
- 汇报格式。

## 5. 合并与验证

Chief Agent 收到子 agent 结果后：

1. 阅读变更摘要。
2. 对照任务文档检查验收标准。
3. 运行必要测试或委派 `tester` 复验。
4. 汇总冲突、风险、未完成项。
5. 决定继续迭代、合并、或回退任务方向。

