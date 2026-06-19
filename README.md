# MiniSFS - Mini Space Flight Simulator

MiniSFS is a 2D space flight sandbox and level-based orbital mechanics game.
It uses SI-unit N-body physics, geometric monochrome rendering, and a probe
rocket model with finite fuel.

## Features

- N-body gravity and Coulomb force simulation with RK4 integration.
- Optional Barnes-Hut quadtree acceleration.
- Sandbox mode for placing stars, planets, probes, and charged/custom bodies.
- Level mode with a 2 x 4 selector. Levels 1 and 2 are implemented.
- Reference-frame camera mode by double-clicking a body.
- True relative trajectory prediction in reference frames.
- Relative trails in reference frames; trails clear when switching frames.
- Probe rocket controls with fuel, exhaust velocity, mass flow, radius, and
  landing speed limit.
- Probe landing: safe impacts leave the probe on the surface; impacts above
  the landing speed limit crash/remove the probe.
- Right-click editing for existing bodies and probes.
- Monochrome pixel UI: black background, white geometric glyphs, pixel borders,
  and project font files under `src/ttf/`.
- PyInstaller spec for Windows executable builds.

## Controls

| Action | Control |
|:--|:--|
| Pan camera | Middle-click drag |
| Zoom | Mouse wheel |
| Grab/move body in sandbox | Left-click drag body |
| Select body/probe | Left-click body |
| Enter reference frame | Double-click body |
| Probe thrust | Arrow keys when a probe is selected or in probe reference frame |
| Edit body parameters | Right-click body |
| Edit probe rocket/body parameters | Right-click probe |
| Cancel active measurement/placement | Right-click |
| Cancel placement / deselect | Right-click empty space |
| Pause/resume | `Space` or HUD pause button |
| Reset camera | `R` |
| Toggle grid | `G` |
| Toggle labels | `L` |
| Toggle shortcut panel | `H` |
| Toggle trails | `T` |
| Delete selected body | `Del` / `Backspace` |

## Toolbar

| Button | Shortcut | Function |
|:--|:--|:--|
| `S` | `1` | Place static star |
| `P` | `2` | Place planet, then drag to set initial velocity |
| `D` | `3` | Configure and place probe |
| `C` | `4` | Configure and place custom charged body |
| `Len` | - | Measure distance between two snapped/world points |
| `Ang` | - | Measure angle ABC in degrees |
| `G` | `G` | Toggle coordinate grid |
| `L` | `L` | Toggle body labels |

Level mode disables sandbox editing tools.

## Time Control

| Button | Function |
|:--|:--|
| `||` / `>` | Pause/resume |
| `<<` | Slow time by 2x |
| `1x` | Restore 1x |
| `>>` | Speed time by 2x |

The time multiplier is bounded from `1/64x` to `64x`.

## Levels

- **Level 1**: Earth-Moon-like transfer. The probe starts on the central body
  and must land on the planet. Level 1 probe engine tuning is stronger and
  lower-flow than the sandbox default.
- **Level 2**: Simplified Sun-Earth-Mars transfer. The probe starts near Earth
  on a Hohmann-like injection path and must land on Mars.

Fixed levels use a probe landing speed limit of `1 km/s`. If the probe crashes
or disappears in a level, the failure popup offers Retry and Menu.

Level 2 probe defaults:

| Parameter | Value |
|:--|:--|
| Total mass | `2.5 t` |
| Fuel mass | `1 t` |
| Exhaust velocity | `300 km/s` |
| Mass flow | `1 mg/s` |
| Landing speed limit | `1 km/s` |

## Installation

```bash
pip install pygame numpy pytest
```

Python 3.10+ is recommended.

## Running

```bash
python -m src.main
```

The app opens on the mode menu. Choose Sandbox Mode for the editable simulation
or Level Mode for the level selector.

## Testing

```bash
pytest tests -q
```

Focused examples:

```bash
pytest tests/test_level_1_scene.py tests/test_mode_menu.py -q
pytest tests/test_physics.py -q
```

## Packaging

Build from an environment where `import pygame` succeeds:

```bash
python -m PyInstaller --noconfirm --clean MiniSFS.spec
```

`build/` and `dist/` are ignored and should not be committed.

## Project Structure

```text
MiniSFS/
├── assets/levels/          # Level JSON files
├── src/
│   ├── main.py             # Main loop and current game orchestration
│   ├── config.py           # Constants and defaults
│   ├── core/               # BodyState types and interfaces
│   ├── physics/            # Forces, integration, collisions, rocket math
│   ├── quadtree/           # Barnes-Hut and trail buffer
│   ├── rendering/          # Renderer, camera, HUD, dialogs, effects
│   └── input/              # Pygame event to command handling
├── tests/                  # Pytest suite
├── .codex/                 # Chief/sub-agent docs and project memory
├── MAIN.md                 # Architecture overview
└── MiniSFS.spec            # PyInstaller config
```

## Core Data Model

Simulation bodies are stored as a NumPy `float64` array with shape `(N, 10)`.
Column constants live in `src/core/types.py`:

| Index | Field | Unit / Meaning |
|---:|:--|:--|
| 0 | `X` | meters |
| 1 | `Y` | meters |
| 2 | `VX` | m/s |
| 3 | `VY` | m/s |
| 4 | `MASS` | kg |
| 5 | `CHARGE` | C |
| 6 | `RADIUS` | meters |
| 7 | `BODY_TYPE` | `0` star, `1` planet, `2` probe, `3` charged |
| 8 | `IS_STATIC` | `0/1` |
| 9 | `IS_ACTIVE` | `0/1` |

Probe rocket state is sidecar data keyed by body row id.

## License

MIT
