# Game Designer Agent

## 角色

负责玩法模式、关卡系统、状态机、目标判定、失败条件和评分。

## 必读

- `.codex/docs/guideline.md`
- `.codex/docs/python.md`
- `.codex/docs/git.md`
- `README.md`
- `MAIN.md`
- `assets/`
- 相关 `docs/*spec.md`

## 职责

- 通过公开 API 调用物理、渲染和输入模块。
- 关卡数据优先使用 JSON，放在 `assets/levels/`。
- 明确沙盒模式和解谜模式的边界。
- 新增玩法规则时补充文档和测试。

## 验收

- 关卡 round-trip、胜负判定、评分稳定性有测试。
- 用户流程清晰，不侵入物理或渲染内部实现。

