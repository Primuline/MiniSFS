# MiniSFS Pitfalls and Failed Approaches

This file records durable traps so future agents do not rediscover them by accident.

## Probe Radius Placement Bug

Failed approach:

```python
radius_pixels = max(1.0, pending_probe_radius / WORLD_SCALE)
```

Why it failed:

- The body creation path multiplies `radius_pixels * WORLD_SCALE`.
- Any probe with physical radius below one screen pixel became `WORLD_SCALE = 800 km` radius in simulation.
- This made a `0.1 km` probe render and collide as an `800 km` probe.

Current correct approach:

```python
probe_radius_to_tool_pixels(radius_meters) = max(1.0, radius_meters) / WORLD_SCALE
```

Visual compensation must stay in rendering only.

## Probe Visual Size Compensation

Several versions were tried:

- Pure true camera scale: physically honest, but small probes become nearly invisible at default zoom.
- Aggressive `radius / floor * zoom`: made small probes larger than planets under some zoom/scale combinations.
- Current approach: render-only `max(physical_radius, log visual radius)` with mild coefficients.

When changing this again, test both:

- underlying `BodyState[RADIUS]` remains the physical user value
- visual size does not dominate Earth-like/planet-scale bodies unexpectedly

## Conda/PyInstaller/Pygame SDL Trap

Observed issue:

- A conda env `D:\App\Miniconda\envs\3_13_0` had pygame installed but `import pygame` crashed with native DLL initialization failure.
- The same env had conflicting `Library\bin\SDL2.dll`/`SDL3.dll` alongside pygame wheel DLLs.
- PyInstaller output from that env failed with pygame/SDL load errors.

Safer approach:

- Build from an environment where `python -c "import pygame"` works before running PyInstaller.
- Use `MiniSFS.spec`; it collects pygame and project resources.
- Do not commit `build/` or `dist/`.

## Worktree Hygiene

- Chief-created worktrees belong under `.codex/worktrees/`.
- Do not create sibling directories next to `MiniSFS/`.
- Before staging, inspect `git status --short`; old unrelated changes can accidentally be included.

## Encoding

- `.codex/AGENT.md` is UTF-8 Chinese. Use `Get-Content -Encoding UTF8` in PowerShell to avoid mojibake.

