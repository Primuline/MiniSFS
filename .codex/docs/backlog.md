# MiniSFS Backlog

This file records durable unfinished work and follow-up candidates. Keep it short and actionable.

## Product Backlog

- Level system beyond Level 1:
  - more levels in the 2 x 4 selector
  - scoring rules
  - restart/next-level controls in result popup
- Move more level/game state out of `src/main.py` once behavior stabilizes.
- Revisit README and MAIN.md; parts are stale after mode menu, Level 1, probe rocket, and packaging changes.
- Consider a stable body id in `BodyState` or sidecar mapping to avoid nearest-neighbor remap after row removal.
- Add more manual/visual validation guidance for monochrome UI and probe visual scaling.

## Technical Backlog

- Decide whether `src/game/` should become active architecture or remain placeholder while `src/main.py` owns gameplay orchestration.
- Add packaging docs to README once PyInstaller flow is stable across machines.
- Review old `.codex/worktrees/` directories and remove stale local worktrees only after confirming no unmerged work remains.
- Consider replacing `pkg_resources` warning source only if pygame/package ecosystem makes it practical.

## Current Known State

- Branch `feat/ux-optimization` is ahead of `origin/feat/ux-optimization` by at least one commit after `ed18fee`.
- Last full test run after Level 1 objective/result work: `pytest tests -q` -> `158 passed, 1 warning`.

