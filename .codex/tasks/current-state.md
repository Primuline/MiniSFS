# Current State for Compact Handoff

Update this file before compacting if the current task state changes. A future
Chief Agent should read this immediately after `.codex/AGENT.md`.

## Branch and Git State

- Current branch: `feat/ux-optimization`.
- Remote tracking branch: `origin/feat/ux-optimization`.
- Latest completed commit before this task:
  - `f4ded4e feat: add landing speed limits and level 2`
- This task is ready to commit as a bugfix/docs sync.

## Current Task Work

Task packet:

- `.codex/tasks/level-entry-failure-reset-doc-sync.md`

Changes:

- Fix level re-entry after probe crash/disappearance:
  - `_start_level()` clears stale `physics_engine.last_collision_events`
  - `_start_level()` clears/rebuilds `physics_engine.probe_landing_speed_limits`
  - `_return_to_level_menu()` clears physics probe/collision residuals
- Fix Level 2 immediate failure:
  - probe starts near Earth but clear of collision overlap
  - Level 2 probe sidecar uses total `2500 kg`, fuel `1000 kg`,
    dry `1500 kg`, exhaust `300000 m/s`, mass flow `1.0e-6 kg/s`,
    landing speed limit `1000 m/s`
- README and MAIN have been rewritten to match current `.codex/docs` behavior.
- Durable docs updated:
  - `.codex/docs/project-memory.md`
  - `.codex/docs/contracts.md`
  - `.codex/docs/pitfalls.md`

## Tests Last Run

```powershell
python -m py_compile src\main.py
pytest tests\test_level_1_scene.py tests\test_mode_menu.py tests\test_physics.py -q
pytest tests -q
```

Result:

```text
focused: 53 passed, 1 warning
full: 169 passed, 1 warning
```

The warning is the known pygame/pkg_resources deprecation.

## Next Recommended Actions

1. Commit the finished bugfix/docs sync.
2. Push only if the user explicitly asks.
