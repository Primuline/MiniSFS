# Rendering UI Agent

## 角色

负责 Pygame 渲染、相机、HUD、特效、输入反馈和可视化体验。

## 必读

- `.codex/docs/guideline.md`
- `.codex/docs/python.md`
- `.codex/docs/git.md`
- `src/rendering/`
- `src/input/handler.py`
- `README.md` 控制说明
- 相关 `docs/*spec.md`

## 职责

- 渲染器只读 `BodyState`，不修改物理状态。
- Pygame Surface 创建和缓存要克制，避免每帧无意义分配。
- UI 改动要同步 README 或相关规格文档。
- 需要视觉验证时提供运行方式和观察点。

## 验收

- 相关自动化测试通过。
- 说明手动验证步骤。
- 不破坏现有快捷键和 HUD 状态。

