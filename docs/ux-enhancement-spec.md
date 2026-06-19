# MiniSFS Current UX Specification

This document describes the current user-facing UX for demonstration and
manual verification. Older shortcut and visual notes are intentionally removed.

## Visual Style

- Black background.
- White geometric bodies and monochrome pixel borders.
- Fonts are loaded from `src/ttf/`.
- Stars/planets/probes are represented by simple geometric glyphs.

## Mode Flow

- The app opens on a mode menu.
- Sandbox Mode starts the editable default scene.
- Level Mode opens a 2 x 4 selector. Levels 1 and 2 are enabled.
- `Esc` backs out of level select, closes overlays/tools where applicable, or
  returns to the mode menu from gameplay.
- `R` resets the current mode:
  - sandbox returns to the default scene and default camera
  - level mode restarts the current level

## Toolbar

The left toolbar contains:

| Button | Keyboard | Behavior |
|---|---|---|
| `S` | `1` | Place static star |
| `P` | `2` | Place planet, then drag to set velocity |
| `D` | `3` | Configure and place probe |
| `C` | `4` | Configure and place custom charged body |
| `Ln` | none | Length measurement |
| `An` | none | Angle measurement |
| `G` | `G` | Toggle grid |
| `L` | `L` | Toggle labels |

In fixed levels, creation/editing tools are disabled. Measurement, grid, and
label tools remain available.

## Measurement Tools

Measurement tools do not modify physics state.

Length measurement:

- Enabling the tool pauses the game and remembers the prior pause state.
- Left-click fixes point A.
- The preview line runs from A to the mouse and displays distance.
- Left-click fixes point B and keeps the completed result visible.
- Additional left-clicks start more length measurements without leaving the tool.
- Right-click cancels an incomplete measurement; right-click with no incomplete
  measurement exits the tool and clears measurement results.

Angle measurement:

- Left-click fixes A, then B, then C.
- The overlay draws AB and BC and labels angle ABC in degrees.
- Multiple completed angles can be kept visible during the same tool session.

Both tools snap clicks to nearby active body centers.

## HUD

- The selected-body info panel is shown in the upper-right and refreshes every
  frame from current `BodyState`.
- Probe fuel appears on the right when a probe is selected/controlled.
- The top-left status panel shows body count, time multiplier, FPS, and mouse
  world coordinates.
- The scale bar is shown near the lower-right.

## Time Control

- Bottom controls are pause/resume, slow by 2x, restore 1x, and speed up by 2x.
- The multiplier range is `1/64x` to `64x`.
- Old numeric speed shortcuts are not active.

## Shortcut Overlay

`H` toggles a monochrome shortcut overlay. The current entries are:

- `Space`: Pause/Resume
- `G`: Toggle Grid
- `L`: Toggle Labels
- `H`: Toggle Shortcuts
- `R`: Reset Mode
- `Del`: Delete Body
- `1~4`: Place Tools
- `Ln/An`: Measure
- `Right-Click`: Edit/Cancel
- `Scroll`: Zoom
- `Dbl-Click`: Reference Frame
- `Middle-Drag`: Pan/Grab
- `Esc`: Back/Cancel

## Levels

Level 1:

- Earth-Moon-like transfer.
- Probe starts on the central body.
- Landing speed limit is `1 km/s`.

Level 2:

- Simplified Sun-Earth-Mars transfer.
- Probe starts near Earth but clear of immediate Earth recollision.
- Probe defaults:
  - total mass `500 t`
  - fuel mass `400 t`
  - exhaust velocity `100 km/s`
  - mass flow `10 kg/s`
  - landing speed limit `10 km/s`

If a level probe crashes or disappears, the failure popup offers Retry and Menu.

## Validation Commands

```powershell
python -m py_compile src\main.py src\input\handler.py src\rendering\effects.py src\rendering\hud.py
pytest tests -q
```
