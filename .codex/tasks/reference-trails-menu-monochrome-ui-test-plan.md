# Reference Trails/Menu/Monochrome UI Test Plan

## Scope

This plan covers the current bug/requirement round:

- Paused reference-frame centering.
- Clearing trails when entering, switching, or leaving a reference frame.
- Relative trail display inside a reference frame.
- Mode entry state for menu, level mode, and sandbox mode.
- Monochrome geometric rendering, font loading from `src/ttf/`, and HUD drawing.

The current tester worktree is based on committed `HEAD` and intentionally does not include the
main worktree's uncommitted rendering/UI changes. To avoid creating tests that must fail before
those changes are merged, only stable camera behavior is automated now.

## Automated Tests Added Now

- `tests/test_reference_frame_camera.py`
  - Verifies `Camera.update_follow(..., dt=0.0)` centers on the current target position without
    velocity feed-forward. This is the invariant needed when the simulation is paused or grabbing.
  - Verifies positive `dt` still applies velocity feed-forward for active simulation follow.

## Tests To Add After API Stabilizes

### Reference Frame Pause

- Add a pure helper in `src/main.py` or a small gameplay controller function that computes
  `follow_dt`.
- Test cases:
  - `is_paused=True` returns `0.0`.
  - `is_grabbing=True` returns `0.0`.
  - active simulation returns `TIME_STEP * time_speed` or the actual effective simulation step.
- Add an integration-style test that enters a reference frame, pauses, advances one rendered frame,
  and asserts the reference body remains at the screen center within 1 pixel.

### Reference Frame Trail Clearing

- Expose reference-frame transition functions or move them behind a controller class.
- Test cases:
  - Entering a reference frame calls `TrailBuffer.clear_all()`.
  - Switching from body A to body B calls `TrailBuffer.clear_all()`.
  - Exiting via `Esc` calls `TrailBuffer.clear_all()`.
  - Deleting the reference body clears the frame state and all trails.

### Relative Trail Display

- Export the relative-trail transform helper as a stable function, for example:
  `transform_reference_trails(trails, bodies, reference_body_id)`.
- Test cases:
  - Body and reference trails with equal history length are transformed by subtracting the matching
    reference history point and adding the reference body's current position.
  - Unequal trail lengths use the aligned tail only.
  - Missing, inactive, or out-of-range reference body returns the original trails unchanged.
  - Switching reference frames starts from empty trails, so no stale world-space trail remains.

### Mode Entry

- Move initial UI state creation into a testable function, for example `create_initial_game_state()`.
- Test cases:
  - Startup state is `GAME_STATE_MENU`, not `GAME_STATE_PLAYING`.
  - Clicking `Sandbox Mode` builds the existing default sandbox scene and transitions to
    `GAME_STATE_PLAYING`.
  - Clicking `Level Mode` stays in menu or opens a disabled/coming-soon state without creating a
    playable level.
  - `Esc` in menu exits; `Esc` in game preserves existing reference-frame/cancel behavior.

### Font Loading

- Add a font helper, for example `src/rendering/fonts.py`.
- Test cases in pygame dummy video mode:
  - Latin UI font loads from `src/ttf/ark-pixel-10px-monospaced-latin.ttf`.
  - Chinese fallback loads from `src/ttf/ark-pixel-10px-monospaced-zh_cn.ttf` when requested.
  - Missing font path falls back to `pygame.font.Font(None, size)` without raising.
  - `Renderer`, `HUDManager`, `Button`, and input dialogs use the helper instead of direct
    `pygame.font.Font(None, ...)` calls.

### Monochrome Geometry And HUD

- Prefer rendering tests in `SDL_VIDEODRIVER=dummy` with small surfaces.
- Test cases:
  - `Renderer.render_background()` does not draw starfield pixels when monochrome mode is active.
  - Star draws as a white regular 17-gon, planet as a white circle, probe as a white triangle.
  - Charged particles draw a monochrome circle with `+` or `-` text.
  - HUD, buttons, dialogs, time controls, and shortcut overlay draw with black/white/gray palette
    only; no colored gradients, glow, or tinted panels.
  - HUD draw methods complete without exceptions at 800x600 and 1280x720 in dummy mode.

## Manual Visual Checks

- Start the game and confirm the first screen is the two-option mode menu.
- Enter sandbox mode and confirm the old default sandbox scene is preserved.
- Double-click a moving body, pause, and verify the selected body stays centered.
- Toggle reference frames between two bodies and confirm all old trails disappear.
- Confirm the background is solid black and UI uses only pixel borders and monochrome geometry.

## Current Baseline

- Main dirty worktree command: `pytest tests/ -q`
- Result on 2026-06-18: `118 passed, 1 warning in 8.17s`
- Warning: pygame imports deprecated `pkg_resources` from the Python environment.
