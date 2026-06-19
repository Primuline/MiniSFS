# MiniSFS Contracts

This file records durable API and data contracts that future agents should not silently break.

## BodyState Contract

`BodyState` is a `numpy.ndarray` with `dtype=np.float64`, shape `(N, 10)`.

Columns are defined in `src/core/types.py`:

| Column | Constant | Unit / Meaning |
|---:|---|---|
| 0 | `X` | meters |
| 1 | `Y` | meters |
| 2 | `VX` | m/s |
| 3 | `VY` | m/s |
| 4 | `MASS` | kg |
| 5 | `CHARGE` | C |
| 6 | `RADIUS` | meters |
| 7 | `BODY_TYPE` | numeric body type |
| 8 | `IS_STATIC` | 0/1 |
| 9 | `IS_ACTIVE` | 0/1 |

Body types:

- `BODY_TYPE_STAR = 0`
- `BODY_TYPE_PLANET = 1`
- `BODY_TYPE_PROBE = 2`
- `BODY_TYPE_CHARGED = 3`

## Unit Contract

- World coordinates and body radii are meters.
- Camera conversion is `screen = world / WORLD_SCALE * zoom`, with `WORLD_SCALE = 8.0e5 m/px`.
- Dialogs may display radius in km, but must convert back to meters before writing to state.
- Tool placement may use legacy "radius pixels" internally, but probe radius conversion must preserve small physical radii:
  - `probe_radius_to_tool_pixels(radius_meters) = max(1.0, radius_meters) / WORLD_SCALE`
  - Never use `max(1.0, radius_meters / WORLD_SCALE)` for probe placement; that turns sub-pixel probes into `800 km` world-radius probes.

## Probe Rocket Contract

- `ProbeRocketState` sidecar fields:
  - `dry_mass`
  - `fuel_mass`
  - `initial_fuel_mass`
  - `exhaust_velocity`
  - `mass_flow_rate`
- Total mass in `BodyState[MASS]` should match dry mass + current fuel mass when thrust is applied.
- Rocket burn math lives in `src/physics/rocket.py`.
- Default probe settings are stored in `src/config.py`.
- Level-specific engine tuning should use helper functions such as `make_level_1_probe_rocket_state()` rather than mutating global defaults.

## Level Contract

- Level files live under `assets/levels/`.
- `assets/levels/level_1.json` defines physical state directly in meters, kg, m/s.
- Level mode disables sandbox editing tools.
- Level 1:
  - central Earth-like body is currently typed as `BODY_TYPE_STAR`
  - target Moon-like body is `BODY_TYPE_PLANET`
  - probe starts on the central body
  - success requires a landed probe on a planet body

## HUD/Dialog Contract

- HUD message dialogs should block underlying input until acknowledged.
- Long-lived UI changes should have tests in `tests/test_mode_menu.py`, rendering tests, or focused HUD tests.
- Avoid visible UI text that only explains controls unless it is a modal objective/result message or menu label.

