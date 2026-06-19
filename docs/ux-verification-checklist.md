# MiniSFS Current UX Verification Checklist

Run with:

```powershell
python -m src.main
```

## Mode Flow

- [ ] App opens on the mode menu.
- [ ] Sandbox Mode enters the editable default scene.
- [ ] Level Mode opens a 2 x 4 selector.
- [ ] Level 1 and Level 2 are enabled; other slots are disabled.
- [ ] `Esc` backs out of level select to the mode menu.

## Reset

- [ ] In sandbox, press `R`; the default scene, camera position, zoom, selection,
      trails, measurement overlays, pause state, and speed reset.
- [ ] In Level 1 or Level 2, press `R`; the current level restarts from its
      initial state.

## Toolbar

- [ ] `S`/`1` selects star placement.
- [ ] `P`/`2` selects planet placement.
- [ ] `D`/`3` opens probe parameter dialog before placement.
- [ ] `C`/`4` opens custom charged body dialog before placement.
- [ ] Fixed levels disable creation/editing tools.
- [ ] Measurement, grid, and label toolbar buttons remain usable in levels.

## Measurement

- [ ] `Ln` pauses the game and starts length measurement.
- [ ] First left-click fixes A; moving the mouse previews A-to-mouse distance.
- [ ] Second left-click fixes B; the AB distance remains on screen.
- [ ] Additional left-clicks create more distance measurements without leaving
      the tool.
- [ ] Right-click while a measurement is incomplete cancels only that partial
      measurement.
- [ ] Right-click with no incomplete measurement exits the tool and clears all
      measurement overlays.
- [ ] `An` similarly measures multiple ABC angles in degrees.
- [ ] Measurement clicks snap to nearby body centers.

## HUD And Overlays

- [ ] Selecting a moving body updates the upper-right info panel live.
- [ ] `G` or toolbar `G` toggles the coordinate grid.
- [ ] `L` or toolbar `L` toggles body labels.
- [ ] `H` toggles the shortcut overlay.
- [ ] Shortcut overlay text has no overlapping rows or columns.
- [ ] Top-left status shows body count, speed, FPS, and mouse world position.
- [ ] Scale bar remains visible and unobstructed.

## Probe And Level Flow

- [ ] Selecting a probe shows fuel information.
- [ ] Arrow keys thrust the selected/controlled probe.
- [ ] Safe probe landing leaves the probe on the body surface.
- [ ] Above-limit impact triggers level failure with Retry/Menu.
- [ ] Level 1 landing limit is `1 km/s`.
- [ ] Level 2 landing limit is `10 km/s`; default probe is `500 t` total mass,
      `400 t` fuel, `100 km/s` exhaust velocity, and `10 kg/s` mass flow.

## Automated Baseline

```powershell
pytest tests -q
```

Current expected baseline: all tests pass with one known pygame/pkg_resources
deprecation warning.
