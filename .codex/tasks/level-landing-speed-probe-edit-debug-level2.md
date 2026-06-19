# Task: level landing speed, probe edit, debug mode, and Level 2

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
- `.codex/agents/physics-engine.md`
- `.codex/agents/tester.md`

## 背景

用户报告并请求：

1. 关卡结算界面弹出后按 Esc 应回到 Level 菜单，而不是回到关卡。
2. 右键探测器时目前出现黄色和蓝色线段跟随鼠标。代码显示这是现有“右键探测器瞄准/发射”功能，不是普通参数编辑。
3. 如果该右键行为不符合当前功能预期，则新增：右键点击探测器也应能修改探测器参数，并且显示当前参数。
4. 给探测器新增“落地速度限制”。落地相对速度超过限制时，探测器直接消失。
5. 沙盒模式落地速度限制默认尽可能大。
6. 关卡模式落地速度限制为 `1 km/s`。
7. 关卡开头提示栏应提示该速度限制。
8. 关卡游玩过程中若探测器消失，应弹出失败窗口，提供 `Retry` 和 `返回菜单` 两个选项。
9. 加入 debug 模式。用户输入在“debug模式下”后中断，具体显示/行为暂未定义；不要猜成大型功能。先实现最小可用开关或标为待澄清。
10. 关卡 2：按地球到火星转移设计。

## 采用的关卡 2 参数来源和简化

本关卡使用游戏化的圆轨道近似，而不是完整星历。

来源：

- NASA/JPL planetary physical parameters: `https://ssd.jpl.nasa.gov/planets/phys_par.html`
- NASA Earth facts: `https://science.nasa.gov/earth/facts/`
- NASA Mars facts: `https://science.nasa.gov/mars/facts/`

采用值：

- Sun mass: about `1.9891e30 kg`
- Earth mass/radius: about `5.9722e24 kg`, `6378.1 km`
- Mars mass/radius: about `6.4169e23 kg`, `3389.9 km`
- Earth orbit radius: about `1.50196428e11 m`
- Mars orbit radius: about `2.28e11 m`

Simplified Hohmann-like circular setup computed from the above:

- Earth circular speed: about `2.9730e4 m/s`
- Mars circular speed: about `2.4130e4 m/s`
- Transfer injection speed at Earth orbit: about `3.2646e4 m/s`
- Transfer delta-v from Earth orbit: about `2.915e3 m/s`
- Transfer time: about `259.5 days`
- Initial Mars phase lead: about `44.0 degrees`

## 目标

- 修复 Level 成功结算弹窗 Esc 路由：
  - 成功/失败结果弹窗上的 Esc 不应恢复当前关卡。
  - 成功结果弹窗 Esc 应返回 Level 菜单。
- 将关卡消息弹窗扩展为可配置按钮：
  - objective: `OK`
  - success: `OK` 或返回菜单，Esc 返回菜单
  - failure: `Retry` 和 `返回菜单`
- 探测器右键参数编辑：
  - 右键探测器打开探测器参数弹窗，而不是进入旧的瞄准线状态。
  - 弹窗必须显示当前探测器参数：
    - total mass = current dry mass + current fuel mass
    - fuel mass = current fuel mass
    - dry mass = existing sidecar dry mass
    - exhaust velocity
    - mass flow rate
    - radius
    - landing speed limit if implemented in the same dialog
  - 确认后更新 `BodyState[MASS]`, `BodyState[RADIUS]`, and probe sidecar state consistently.
- 落地速度限制：
  - Extend probe sidecar state with `landing_speed_limit`.
  - Default sandbox limit should be effectively unbounded, e.g. `float("inf")` or a large finite value if dialog validation cannot handle infinity.
  - Level probes use `1000.0 m/s`.
  - On probe collision/landing, compare relative speed to host before snapping velocity to host.
  - If relative speed exceeds limit, mark probe inactive/remove through normal inactive compaction and emit/record a crash event.
  - Level mode should treat probe disappearance/crash as failure and show Retry/Menu popup.
- Level 1 objective popup includes the `1 km/s` landing speed warning.
- Level 2:
  - Level select enables Level 2.
  - Add `assets/levels/level_2.json`.
  - Add loader or generic level creation path for Level 2.
  - Use simplified Sun-Earth-Mars transfer setup above.
  - Disable sandbox editing in Level 2 like Level 1.
  - Define Level 2 success as landed probe on Mars-like `BODY_TYPE_PLANET`.
  - Define Level 2 failure as probe crash/disappearance.
- Debug mode:
  - Because user did not finish the behavior description, do not implement an expansive debug UI.
  - Acceptable minimal implementation: a `DEBUG_MODE` flag/toggle or no-op scaffolding documented for follow-up.
  - If any visible behavior is added, it must be easy to disable and should not overlap GUI.

## 非目标

- Do not implement full patched-conic or ephemeris-grade Earth-Mars mission planning.
- Do not refactor all level/game state out of `src/main.py` unless required.
- Do not change `BodyState` shape unless an architect task explicitly approves it.
- Do not restore right-click probe aiming unless a new explicit input binding is selected.

## 允许修改范围

- `src/main.py`
- `src/physics/collision.py`
- `src/rendering/hud.py`
- `src/rendering/input_dialog.py`
- `src/config.py`
- `assets/levels/*.json`
- `tests/*.py`
- `.codex/docs/*.md`
- `.codex/tasks/current-state.md`

## 禁止修改范围

- No destructive git operations.
- Do not create worktrees outside `.codex/worktrees/`.
- Do not commit build artifacts.
- Do not silently change world units: radii and positions remain meters.

## 验收标准

- Clicking Level 1 does not crash.
- Level success popup Esc returns to Level menu and does not resume the completed level.
- Right-click probe opens current probe parameter dialog; no yellow/blue aim lines appear from that action.
- Editing a probe preserves mass consistency:
  - `BodyState[MASS] == dry_mass + fuel_mass`
  - `RADIUS` uses meters
  - fuel HUD uses updated sidecar state
- Probe landing under speed limit lands as before.
- Probe landing above speed limit removes/crashes probe.
- In Level 1/2, probe crash triggers failure dialog with Retry and menu actions.
- Retry restarts the current level cleanly.
- Returning to menu opens Level select.
- Level 2 appears in the 2 x 4 grid and can start.
- Level 2 initial bodies are Sun, Earth, Mars, and probe with physically plausible masses/radii/orbital speeds.
- Relevant focused tests and full `pytest tests -q` pass.

## 测试命令

```powershell
pytest tests\test_level_1_scene.py tests\test_mode_menu.py -q
pytest tests\test_physics.py -q
pytest tests -q
```

Add focused tests for:

- level result popup Esc/action routing
- probe parameter editing prefill/update
- landing speed crash vs safe landing
- Level 2 scene constants and level selector enabling

## 分工建议

- `physics-engine`: collision/crash event and landing speed limit mechanics.
- `rendering-ui`: HUD result/failure dialog buttons and probe edit dialog fields/prefill.
- `game-designer`: Level 1/2 state flow, retry/menu routing, level data.
- `tester`: focused regression tests and final full test run.

## 汇报格式

- Files changed
- Behavior changed
- Tests run
- Risks
- Open questions
