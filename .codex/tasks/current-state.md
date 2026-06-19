# Current State for Compact Handoff

Update this file before compacting if the current task state changes. A future
Chief Agent should read this immediately after `.codex/AGENT.md`.

## Branch and Git State

- Current branch: `feat/ux-optimization`.
- Remote tracking branch: `origin/feat/ux-optimization`.
- Latest completed commit before current uncommitted work:
  - `9d0dcde fix: prevent level 2 probe immediate crash`
- Current uncommitted work includes Level 2 probe tuning plus measurement tools and live HUD refresh.

## Current Task Work

Current task packet:

- `.codex/tasks/measurement-tools-hud-refresh.md`

Changes:

- Level 2 probe tuning changed to total `500000 kg`, fuel `400000 kg`,
  dry `100000 kg`, exhaust `100000 m/s`, mass flow `10 kg/s`, landing limit
  `10000 m/s`.
- Selected body info panel is refreshed every frame from current `BodyState`.
- Toolbar includes length measurement, angle measurement, grid toggle, and labels toggle.
- Measurement tools pause while active, snap to nearby active body centers, draw world-space
  measurement overlays, and restore previous pause state on exit.
- H shortcut overlay has been updated to remove stale right-drag and old speed shortcuts.
- README toolbar/control notes include the new measurement buttons.
- `R` resets the current mode: sandbox returns to the default scene, while level mode restarts the current level.
- Durable docs updated:
  - `.codex/docs/project-memory.md`
  - `.codex/docs/contracts.md`
  - `.codex/tasks/current-state.md`

## Tests Last Run

```powershell
python -m py_compile src\main.py
python -m py_compile src\main.py src\rendering\hud.py src\rendering\effects.py
pytest tests\test_mode_menu.py tests\test_rendering_monochrome_ui.py tests\test_integration.py -q
pytest tests\test_level_1_scene.py tests\test_mode_menu.py tests\test_rendering_monochrome_ui.py tests\test_integration.py -q
pytest tests -q
```

Result:

```text
focused UI/input: 46 passed, 1 warning
focused level/UI/input: 57 passed, 1 warning
full: 173 passed, 1 warning
```

The warning is the known pygame/pkg_resources deprecation.

## Next Recommended Actions

1. Commit finished work.
2. Push only if the user explicitly asks.
