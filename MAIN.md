# MiniSFS Architecture Overview

MiniSFS is a 2D space flight sandbox and level game. It combines SI-unit
N-body physics, a Pygame renderer, a monochrome pixel HUD, and fixed mission
scenes loaded from JSON.

This document is the broad architecture overview. For compact-safe operational
memory, also read `.codex/docs/`.

## Directory Structure

```text
MiniSFS/
├── assets/
│   └── levels/              # Level JSON files
├── src/
│   ├── main.py              # Main loop, mode flow, level orchestration
│   ├── config.py            # Constants and default parameters
│   ├── core/
│   │   ├── types.py         # BodyState columns and factory helpers
│   │   └── interfaces.py    # Abstract module interfaces
│   ├── physics/
│   │   ├── engine.py        # PhysicsEngine update/prediction facade
│   │   ├── forces.py        # Gravity and Coulomb forces
│   │   ├── integrators.py   # Euler, RK4, Velocity Verlet
│   │   ├── collision.py     # Collision and probe landing/crash response
│   │   └── rocket.py        # Pure rocket burn math
│   ├── quadtree/
│   │   ├── quadtree.py      # Spatial tree
│   │   ├── barnes_hut.py    # Barnes-Hut force approximation
│   │   └── trail.py         # TrailBuffer
│   ├── rendering/
│   │   ├── renderer.py      # Body drawing and visual selection
│   │   ├── camera.py        # World/screen transform and following
│   │   ├── hud.py           # Menus, toolbar, dialogs, status panels
│   │   ├── effects.py       # Trails, prediction, labels, grid
│   │   └── input_dialog.py  # Numeric parameter dialogs
│   └── input/
│       └── handler.py       # Pygame event to command conversion
├── tests/                   # Pytest tests
├── .codex/                  # Agent rules, durable memory, task packets
├── README.md
├── MAIN.md
└── MiniSFS.spec             # PyInstaller build config
```

## Module Boundaries

| Module | Owns | Must avoid |
|:--|:--|:--|
| `src.core` | Shared types, column constants, abstract interfaces | Pygame |
| `src.physics` | Forces, integration, collisions, trajectory prediction, rocket math | Rendering/UI dependencies |
| `src.quadtree` | Spatial data structures, Barnes-Hut, trail buffer | Pygame-specific behavior |
| `src.rendering` | Pygame drawing, camera, HUD, dialogs, visual effects | Mutating physical state |
| `src.input` | Event-to-command conversion | Physics/rendering internals |
| `src.main` | Current top-level orchestration, levels, selection, probe sidecars | Large unrelated refactors |

The old placeholder `src/game/` package has been removed. Current gameplay
orchestration lives mostly in `src/main.py`.

## Core Data Model

All simulated bodies are exchanged as `BodyState`, a NumPy `float64` array with
shape `(N, 10)`.

| Column | Constant | Unit / Meaning |
|---:|:--|:--|
| 0 | `X` | meters |
| 1 | `Y` | meters |
| 2 | `VX` | m/s |
| 3 | `VY` | m/s |
| 4 | `MASS` | kg |
| 5 | `CHARGE` | C |
| 6 | `RADIUS` | meters |
| 7 | `BODY_TYPE` | `0` star, `1` planet, `2` probe, `3` charged |
| 8 | `IS_STATIC` | `0` dynamic, `1` static |
| 9 | `IS_ACTIVE` | `0` inactive, `1` active |

World coordinates, velocities, masses, radii, and charges use SI units. Pixel
conversion is a rendering concern handled by `WORLD_SCALE` and `Camera`.

## Probe Sidecar State

Probe rocket data is not stored in `BodyState`; it is sidecar state keyed by
current body row id:

- `dry_mass`
- `fuel_mass`
- `initial_fuel_mass`
- `exhaust_velocity`
- `mass_flow_rate`
- `landing_speed_limit`

`BodyState[MASS]` should match `dry_mass + fuel_mass` when a probe sidecar is
present. Because collision removal can reorder rows, `src/main.py` remaps probe
sidecars after physics updates.

Probe radius remains physical data in meters. Any minimum visible size or
visual compensation belongs only in rendering code.

## Physics Flow

Each gameplay frame:

1. Input events become command strings.
2. `src/main.py` applies commands to mode, tool, camera, dialog, and selection state.
3. If not paused, `PhysicsEngine.update()` advances bodies using RK4/substeps.
4. Collision handling produces events such as `probe_landed` and `probe_crashed`.
5. Probe sidecars are remapped and landing limits are resynced.
6. Trails are recorded, excluding landed probes.
7. Level success/failure is checked.
8. Renderer and HUD draw the frame.

Reference-frame trajectory prediction must compute future reference-body
positions and draw true relative future trajectories, not constant-velocity
approximations.

## Collision and Landing Rules

- Star/planet and planet/planet collisions use the existing merge/absorb rules.
- Probe impacts compare pre-snap relative speed to the probe landing speed limit.
- Safe probe impact emits `probe_landed` and leaves the probe standing on the host surface.
- Above-limit probe impact emits `probe_crashed` and deactivates/removes the probe.
- Fixed levels treat probe crash/disappearance as failure.

## Modes and Levels

The first screen is a mode menu:

- Sandbox Mode starts the editable simulation.
- Level Mode opens a 2 x 4 level selector.

Level files live in `assets/levels/` and store physical values directly in
meters, kg, and m/s.

Implemented levels:

- Level 1: Earth-Moon-like transfer; land on the planet.
- Level 2: simplified Sun-Earth-Mars transfer; land on Mars.

Fixed levels disable sandbox creation/editing tools. Level 1 uses a `1 km/s`
landing speed limit; Level 2 uses a `10 km/s` landing speed limit.

## UI and Rendering

The current UI direction is monochrome and geometric:

- black background
- white pixel borders
- circular planets/stars, rotating polygonal star glyphs, triangular probes
- font assets from `src/ttf/`
- toolbar utility buttons for length measurement, angle measurement, grid, and labels
- `R` resets the current mode: sandbox returns to the default scene, levels restart

Right-clicking an existing body opens parameter editing. Right-clicking a probe
opens probe parameter editing; old right-click probe aiming is no longer the
current behavior.

## Testing

Baseline:

```powershell
pytest tests -q
```

Focused commands:

```powershell
pytest tests\test_level_1_scene.py tests\test_mode_menu.py -q
pytest tests\test_physics.py -q
pytest tests\test_rendering_monochrome_ui.py tests\test_rendering_probe_ui.py -q
```

Core physics and collision changes should have focused regression tests. UI
changes should have either state/helper tests or headless Pygame smoke tests.

## Packaging

`MiniSFS.spec` is the PyInstaller entry point. Build only from an environment
where `python -c "import pygame"` succeeds. `build/` and `dist/` are ignored and
must not be committed.

## Durable Project Memory

`.codex/docs/` is the source of compact-safe project memory:

- `project-memory.md`: product direction and user preferences
- `architecture.md`: current architecture choices
- `contracts.md`: API/data/unit contracts
- `testing.md`: test commands and baselines
- `pitfalls.md`: known traps and failed approaches
- `backlog.md`: TODO and follow-up work
