# Current State for Compact Handoff

Update this file before compacting if the current task state changes. A future Chief Agent should read this immediately after `.codex/AGENT.md`.

## Branch and Git State

- Current branch: `feat/ux-optimization`.
- Remote tracking branch: `origin/feat/ux-optimization`.
- Latest completed commit before the current uncommitted feature work:
  - `86b6d79 fix: initialize level message font`
- Current work adds Level 2, probe landing speed limits, right-click probe editing, and level success/failure routing.

## Recently Completed Work

- Added PyInstaller packaging config:
  - `MiniSFS.spec`
  - `.gitignore` ignores `build/` and `dist/`
  - packaging should be done from an environment where `import pygame` works
- Restored probe visual compensation after fixing the real radius placement bug.
- Fixed probe placement radius conversion so small physical radii are preserved.
- Added Level 1 objective and result popups.
- Tuned Level 1 probe engine:
  - exhaust velocity `* 50`
  - mass flow `// 50`
- Level 1 clears when a probe lands on a `BODY_TYPE_PLANET`.
- Current uncommitted feature work:
  - `assets/levels/level_2.json`
  - fixed-level probe landing speed limit of `1000 m/s`
  - sandbox probe landing speed limit default of `1.0e30 m/s`
  - `probe_crashed` collision events for above-limit impacts
  - Level failure dialog with Retry/Menu actions
  - Level success Esc/Menu returns to Level Select
  - right-click probe opens parameter editing instead of aim lines

## Tests Last Run

```powershell
pytest tests\test_level_1_scene.py tests\test_mode_menu.py -q
pytest tests\test_physics.py tests\test_mode_menu.py tests\test_level_1_scene.py tests\test_rendering_probe_ui.py -q
pytest tests -q
```

Result:

```text
167 passed, 1 warning
```

## Next Recommended Actions

1. Commit the Level 2 / landing speed / probe edit work.
2. Push `feat/ux-optimization` only if the user asks.
3. Clarify debug mode behavior before implementing more than minimal scaffolding.
