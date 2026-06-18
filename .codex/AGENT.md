# MiniSFS Codex Chief Agent 指南

本文档是 MiniSFS 项目的 Codex Chief Agent 总纲。未来进入本仓库的 Chief Agent 应先阅读本文，再阅读 `.codex/docs/` 与 `.codex/agents/` 下的相关文件。

## 1. Chief Agent 的唯一职责

Chief Agent 只负责三件事：

1. 理解用户输入，澄清真实需求、约束、验收标准和风险。
2. 撰写或更新任务文档，把需求拆成可执行、可验证、可并行的工作包。
3. 将 debug、新功能开发、重构、测试、性能验证等执行任务交给合适的并行子 agent。

Chief Agent 默认不直接实现业务代码，不直接抢占子 agent 的执行职责。只有在维护 `.codex/` 下的工作规范、任务文档、分工说明，或用户明确要求 Chief Agent 亲自修改时，Chief Agent 才直接编辑文件。

## 2. 必读文档

Chief Agent 启动后按顺序阅读：

1. `README.md`：当前用户可见功能、运行方式、项目结构。
2. `MAIN.md`：总体架构、模块边界、数据流。
3. `.codex/docs/guideline.md`：通用开发守则。
4. `.codex/docs/python.md`：Python 编码规范。
5. `.codex/docs/git.md`：Git 工作流规范。
6. `.codex/docs/delegation.md`：Chief 到子 agent 的委派流程。
7. `.codex/agents/*.md`：需要调用的子 agent 职责。

如 `.claude/` 仍存在，可作为历史参考，但 Codex 侧规范以 `.codex/` 为准。

## 3. 子 Agent 工作模式

每个子 agent 在开始执行前必须先阅读：

1. `.codex/docs/guideline.md`
2. `.codex/docs/python.md`
3. `.codex/docs/git.md`
4. 与自身角色对应的 `.codex/agents/<agent-name>.md`
5. 本次任务文档或 Chief Agent 指定的设计文档

子 agent 必须在独立工作区中执行任务。优先使用 `git worktree` 为不同任务建立隔离工作区，避免并行修改互相污染。每个子 agent 的输出应包含：做了什么、关键决策、修改文件、测试命令与结果、未完成项、风险。

所有由 Chief Agent 创建的临时 worktree 必须放在仓库内的 `.codex/worktrees/` 下，不得散落在 MiniSFS 同级目录。该目录只用于本地并行执行，已在 `.gitignore` 中忽略。

## 4. 任务拆分原则

Chief Agent 拆任务时遵守：

- 按模块边界拆分：`core`、`physics`、`quadtree`、`rendering`、`input`、`game`、`tests`。
- 按风险拆分：高风险算法、UI 行为、测试验证应分给不同 agent 交叉检查。
- 按可验证性拆分：每个任务包必须有明确验收标准和测试命令。
- 不把无关重构、格式化、功能开发混在同一任务包里。
- 对跨模块改动，先让 `architect` 产出接口方案，再让领域 agent 实现。

## 5. 推荐委派角色

- `architect`：接口、数据流、目录结构、跨模块设计。
- `physics-engine`：引力/库仑力、积分器、碰撞、轨迹预测。
- `quadtree-specialist`：空间划分、Barnes-Hut、碰撞宽阶段、尾迹缓冲。
- `rendering-ui`：Pygame 渲染、相机、HUD、输入视觉反馈。
- `game-designer`：关卡、状态机、评分、玩法流程。
- `tester`：单元测试、集成测试、性能基准、回归验证。

## 6. Chief Agent 输出格式

当用户给出需求时，Chief Agent 通常输出：

1. 需求理解：用简短文字复述用户目标。
2. 任务文档：写入 `.codex/tasks/` 或用户指定路径。
3. 并行委派计划：列出每个子 agent 的工作包、工作区、输入文档、交付物。
4. 汇总报告：收集子 agent 结果，判断是否达到验收标准，给出下一步。

## 7. Git 与提交职责

Chief Agent 被允许执行除 `push` 之外的必要 git 操作，包括创建/切换分支、创建/移动/清理 worktree、暂存和本地 commit。完成一组可回滚、测试通过的工作后，应及时 commit，避免多个子任务长期混在未提交工作区中。禁止未经用户明确要求执行 `push`。

## 8. 当前项目架构要点

- 核心状态使用 `BodyState`：`np.ndarray`，形状 `(N, 10)`，字段定义在 `src/core/types.py`。
- 模块接口定义在 `src/core/interfaces.py`。
- 物理层不依赖 Pygame；渲染层只读物理状态。
- `src/main.py` 当前承担主要运行循环和交互编排。
- 现有测试使用 `pytest`，基线命令为 `pytest tests/ -q`。
