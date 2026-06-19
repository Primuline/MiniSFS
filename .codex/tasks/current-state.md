# Current State for Compact Handoff

Update this file before compacting if the current task state changes. A future
Chief Agent should read this immediately after `.codex/AGENT.md`.

## Branch and Git State

- Current branch: `feat/ux-optimization`.
- Remote tracking branch: `origin/feat/ux-optimization`.
- Latest completed commit before final-step work:
  - `cc72e26 fix: reset current mode with R`
- Current uncommitted work:
  - deletion of `src/game/__init__.py` requested/confirmed by the user
  - README/MAIN/docs refresh for current UX and project memory
  - `.codex/docs` consistency updates for Level 2 probe and landing limit values

## Product State

- Sandbox mode starts an editable default scene.
- Level mode uses a 2 x 4 selector; Levels 1 and 2 are enabled.
- Level 1: Earth-Moon-like transfer, `1 km/s` landing speed limit.
- Level 2: Sun-Earth-Mars-like transfer, `500 t` total mass, `400 t` fuel,
  `100 km/s` exhaust velocity, `10 kg/s` mass flow, `10 km/s` landing limit.
- Toolbar includes placement, length measurement, angle measurement, grid, and labels.
- `R` resets the current mode: sandbox returns to default, level mode restarts current level.

## Last Known Test Baseline

Before final-step work:

```text
pytest tests -q -> 173 passed, 1 warning
```

Run full tests again before release.

## Final-Step Next Actions

1. Finish documentation refresh.
2. Run full tests.
3. Build executable with PyInstaller.
4. Smoke-test the packaged executable.
5. Commit all changes, including `src/game/__init__.py` deletion.
6. Push `feat/ux-optimization`.
7. Create a GitHub release and upload the `.exe`.
