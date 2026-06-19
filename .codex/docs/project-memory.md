# MiniSFS Project Memory

This file stores durable product context and user preferences that should survive chat compaction. Keep it high signal. Do not paste temporary logs, full stack traces, or one-off command output here.

## Product Direction

- MiniSFS is a 2D space flight / orbital mechanics sandbox with level mode.
- Current design direction favors a clean monochrome pixel UI: black background, white geometric bodies, pixel borders, and Ark Pixel fonts from `src/ttf/`.
- The first screen is a mode menu. Sandbox mode enters the normal editable simulation. Level mode opens a 2 x 4 level grid; Levels 1 and 2 are implemented for now.
- Level 1 is an Earth-Moon-like transfer mission: the central Earth-like body is represented as a static `BODY_TYPE_STAR`; the Moon-like target is `BODY_TYPE_PLANET`; the default probe starts on the central body and clears the level when it lands on the planet.
- Level 2 is a simplified Sun-Earth-Mars transfer mission using circular orbit approximations and a Hohmann-like initial probe speed. The probe starts near Earth but clear of Earth collision overlap.

## User Preferences

- The user expects the assistant to act as Chief Agent for non-trivial work: understand the request, document task packets, delegate implementation/testing to subagents where useful, and merge/verify results.
- Small, narrow fixes may be handled directly by Chief Agent, but this should be treated as an exception and named as such.
- Git hygiene is important: commit tested, rollback-friendly increments; do not leave unrelated changes mixed in; use worktrees under `.codex/worktrees/`.
- The user prefers preserving physical meaning of parameters. Example: probe radius entered as meters/kilometers must remain physical radius in `BodyState`, while any visual compensation must stay render-only.
- The user is sensitive to UI overlap, text overflow, and controls changing in surprising ways.
- The user intends to compact conversations. Durable discoveries must be written under `.codex/` before compacting.

## Current Product Facts

- Probe defaults:
  - total mass `2.8e6 kg`
  - fuel mass `2.1e6 kg`
  - exhaust velocity `2.5e3 m/s`
  - mass flow `1.4e4 kg/s`
  - radius `100 m`
  - sandbox landing speed limit `1.0e30 m/s`
- Level 1 probe tuning:
  - exhaust velocity is default `* 50`
  - mass flow is default `// 50`
- Fixed levels can override probe landing speed limits. Level 1 uses `1000 m/s`;
  Level 2 uses `10000 m/s`.
- Level 2 probe tuning:
  - total mass `500000 kg`
  - fuel mass `400000 kg`
  - dry mass `100000 kg`
  - exhaust velocity `100000 m/s`
  - mass flow `10 kg/s`
  - landing speed limit `10000 m/s`
- Default star/body parameters have been moved toward solar/Earth-like values. `WORLD_SCALE = 8.0e5` meters per pixel.
- Probe visual size has render-only compensation. Real body radius must not be clamped to one screen pixel during placement.
- Right-clicking a probe edits its current rocket/body parameters. The previous right-click probe aiming lines are no longer the right-click behavior.
- Toolbar includes non-editing helpers for length measurement, angle measurement, grid toggle, and labels toggle.
