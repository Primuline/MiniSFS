# MiniSFS Architecture Notes

This file records durable architecture choices and module boundaries. For older broad overview, also read `MAIN.md`; if it disagrees with this file, inspect current code and update both.

## Module Boundaries

- `src/core/`
  - Owns shared types, `BodyState` column constants, and abstract interfaces.
  - Must not depend on Pygame.
- `src/physics/`
  - Owns force calculation, RK4 integration, collision resolution, trajectory prediction, and pure rocket math.
  - Must not depend on rendering or UI.
- `src/quadtree/`
  - Owns quadtree/Barnes-Hut structures and trail buffering.
- `src/rendering/`
  - Owns Pygame rendering, camera transforms, HUD, dialogs, visual effects, trails, prediction drawing, and UI interaction surfaces.
  - Renderer reads physical state but should not mutate simulation state.
- `src/input/`
  - Converts Pygame events into command strings consumed by the main loop.
- `src/main.py`
  - Currently owns the top-level loop, command orchestration, level entry, selection/reference-frame state, probe sidecar state, and some level helpers.
  - This file is large. Future larger features should consider extracting level/session state only after tests exist.

## Important Architecture Choices

- `BodyState` is a NumPy `float64` array, shape `(N, 10)`, for all simulated bodies.
- Probe rocket fuel/engine/landing-limit data is sidecar state keyed by body row id, not stored in `BodyState`.
- Row ids are not stable through collision removal. Main loop remaps probe rocket sidecar state after physics by nearest matching active probe.
- Level JSON stores physical world units directly, not pixel units.
- Probe visual size compensation is render-only. It must never change stored `RADIUS`.
- Reference-frame behavior must compute true future relative trajectories, not assume reference body constant velocity.
- Landed probes are not removed when impact speed is within limit. Collision handling places probes on the host surface and emits `probe_landed`; above-limit impacts emit `probe_crashed` and deactivate the probe.
- Level win condition is "landed probe resting on a `BODY_TYPE_PLANET` host".

## Packaging Architecture

- PyInstaller config is `MiniSFS.spec`.
- Build artifacts `build/` and `dist/` are ignored.
- The spec collects pygame binaries/data and project resources:
  - `assets -> assets`
  - `src/ttf -> src/ttf`
