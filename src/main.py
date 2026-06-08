"""MiniSFS main entry point: visual demo.

Initializes all modules and runs the main loop:
    Input -> Physics Update -> Collision Detection -> Trail Recording -> Rendering

Uses fixed time-step physics for stability; rendering frame rate is independent.
Default scene: star + orbiting planet + probe launcher.
"""

import math
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
import pygame

from src.config import (
    BODY_TYPE_CHARGED,
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_STAR,
    CAMERA_ZOOM_MAX,
    CAMERA_ZOOM_MIN,
    CUSTOM_CHARGE_DEFAULT,
    CUSTOM_MASS_DEFAULT,
    DEFAULT_CHARGE_CHARGED,
    DEFAULT_MASS_CHARGED,
    DEFAULT_MASS_PLANET,
    DEFAULT_MASS_PROBE,
    DEFAULT_MASS_STAR,
    DEFAULT_RADIUS_CHARGED,
    DEFAULT_RADIUS_PLANET,
    DEFAULT_RADIUS_PROBE,
    DEFAULT_RADIUS_STAR,
    GRAVITATIONAL_CONSTANT,
    PLACEMENT_SPEED_PER_PX,
    GAME_STATE_PAUSED,
    GAME_STATE_PLAYING,
    SOFTENING,
    SUBSTEPS,
    TARGET_FPS,
    TIME_STEP,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    WORLD_SCALE,
)
from src.core.types import (
    BODY_TYPE,
    CHARGE,
    IS_ACTIVE,
    IS_STATIC,
    MASS,
    RADIUS,
    VX,
    VY,
    X,
    Y,
    make_body,
)
from src.core.utils.tools import normalize_angle_delta
from src.input.handler import InputHandler
from src.physics.engine import PhysicsEngine
from src.physics.forces import find_nearest_star
from src.quadtree.trail import TrailBuffer
from src.rendering.camera import Camera
from src.rendering.effects import ParticleSystem
from src.rendering.hud import HUDManager
from src.rendering.renderer import Renderer

# ============================================================================
# Default scene creation
# ============================================================================


def create_default_scene() -> np.ndarray:
    """Create the default demo scene.

    Contains:
        - 1 massive static star (center)
        - 1 planet in circular orbit at 100 million km

    All radii are specified directly in world units (meters).

    Returns:
        Body state array of shape (N, NUM_FIELDS)
    """
    bodies_list = []

    # 1. Central star (static)
    star = make_body(
        x=0.0, y=0.0,
        vx=0.0, vy=0.0,
        mass=DEFAULT_MASS_STAR,  # 2.0e30 kg
        radius=7.0e8,  # 7e5 km
        body_type=BODY_TYPE_STAR,
        is_static=True,
    )
    bodies_list.append(star)

    # 2. Planet (orbiting star, 100 million km orbit)
    orbit_radius = 1.0e11  # 1e8 km
    orbital_speed = math.sqrt(
        DEFAULT_MASS_STAR * 6.67430e-11 / orbit_radius
    )

    planet = make_body(
        x=orbit_radius, y=0.0,
        vx=0.0, vy=orbital_speed,
        mass=DEFAULT_MASS_PLANET,  # 6.0e26 kg
        radius=6.4e6,  # 6.4e3 km
        body_type=BODY_TYPE_PLANET,
    )
    bodies_list.append(planet)

    return np.vstack(bodies_list)


def create_collision_scene() -> np.ndarray:
    """Create an optional collision demo scene (2 groups of colliding bodies).

    Returns:
        Body state array of shape (N, NUM_FIELDS)
    """
    scale = WORLD_SCALE

    bodies_list = []

    # Left star
    star1 = make_body(
        x=-100.0 * scale, y=0.0,
        vx=2e3, vy=0.0,
        mass=1.0e29,
        radius=scale * 12.0,
        body_type=BODY_TYPE_STAR,
    )
    bodies_list.append(star1)

    # Right star
    star2 = make_body(
        x=100.0 * scale, y=0.0,
        vx=-2e3, vy=0.0,
        mass=1.0e29,
        radius=scale * 12.0,
        body_type=BODY_TYPE_STAR,
    )
    bodies_list.append(star2)

    return np.vstack(bodies_list)


# ============================================================================
# Utility functions
# ============================================================================


def add_body_to_array(
    bodies: np.ndarray,
    body_data: np.ndarray,
) -> np.ndarray:
    """Add a new body to the body array.

    Args:
        bodies: Existing body array
        body_data: New body data of shape (1, NUM_FIELDS)

    Returns:
        Merged body array
    """
    return np.vstack([bodies, body_data])


def remove_body_from_array(
    bodies: np.ndarray, body_id: int
) -> np.ndarray:
    """Remove a specific body from the body array.

    Args:
        bodies: Existing body array
        body_id: Row index of the body to remove

    Returns:
        Body array after removal
    """
    if body_id < 0 or body_id >= bodies.shape[0]:
        return bodies

    # Mark as inactive (keep array indices stable)
    bodies[body_id, IS_ACTIVE] = 0.0
    # Re-filter active bodies
    active = bodies[bodies[:, IS_ACTIVE] == 1.0]
    return active


# ============================================================================
# Main function
# ============================================================================


def main() -> None:
    """MiniSFS main entry point.

    Initializes all modules and runs the main loop."""
    pygame.init()
    pygame.display.set_caption("MiniSFS")

    # Create module instances
    renderer = Renderer(WINDOW_WIDTH, WINDOW_HEIGHT)
    camera = Camera(WINDOW_WIDTH, WINDOW_HEIGHT, WORLD_SCALE)
    camera.zoom_at(0.008, WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
    physics_engine = PhysicsEngine(
        substeps=SUBSTEPS,
        use_quadtree=False,
    )
    trail_buffer = TrailBuffer()
    input_handler = InputHandler()
    hud = HUDManager()
    particle_system = ParticleSystem()

    # Scene
    bodies = create_default_scene()

    # Game state
    game_state: str = GAME_STATE_PLAYING
    clock = pygame.time.Clock()
    running = True

    # Physics timestep
    physics_dt = TIME_STEP  # Fixed 1/60 second
    accumulator = 0.0
    # Base time speed
    BASE_TIME_SPEED = 3125.0
    time_speed = BASE_TIME_SPEED
    time_multiplier = 1.0  # Ratio relative to base speed (1x, 2x, 4x, 8x)
    is_paused = False

    # Tool state
    active_tool: Optional[str] = None

    # Aiming state
    is_aiming = False
    aim_start_screen: Tuple[int, int] = (0, 0)
    aim_start_world: Tuple[float, float] = (0.0, 0.0)
    aim_current_world: Tuple[float, float] = (0.0, 0.0)

    # UX display state
    show_grid = False
    show_labels = False
    show_shortcuts = False

    # Grab/drag state
    is_grabbing = False
    grabbed_body_id: Optional[int] = None
    _grab_actually_dragged = False  # Whether actually dragged (distinguishes click-select vs grab)

    # Currently selected body
    selected_body_id: Optional[int] = None

    # Reference frame body ID (double-click to enter reference frame)
    reference_body_id: Optional[int] = None
    _saved_zoom_before_frame: float = 1.0

    # Predicted trajectory cache
    predicted_trajectory: Optional[np.ndarray] = None
    _prediction_frame_counter: int = 0  # Only recalculate predicted trajectory every N frames
    _last_predicted_body_id: Optional[int] = None  # Track last selected probe ID

    # Custom particle placement flow state
    # 0=inactive, 1=dialog config, 2=position selection, 3=speed setting
    custom_placement_stage: int = 0
    custom_preview_pos: Optional[Tuple[float, float]] = None  # Preview circle world coordinates
    custom_arrow_start: Optional[Tuple[float, float]] = None   # Arrow origin (= preview circle position)

    # Simple placement flow state (shared by Star/Planet/Probe)
    # 0=inactive, 1=preview position, 2=speed setting
    simple_placement_stage: int = 0
    simple_placement_tool: Optional[str] = None
    simple_preview_pos: Optional[Tuple[float, float]] = None
    simple_arrow_start: Optional[Tuple[float, float]] = None

    # Trajectory preview during placement speed setting
    placement_trajectory: Optional[Dict[str, object]] = None

    # ==================================================================
    # Helper functions
    # ==================================================================

    def _cancel_custom_placement() -> None:
        """Cancel custom particle placement flow, restore time and tool state."""
        nonlocal custom_placement_stage, custom_preview_pos, custom_arrow_start
        nonlocal active_tool, is_paused
        custom_placement_stage = 0
        custom_preview_pos = None
        custom_arrow_start = None
        hud.custom_dialog_visible = False
        hud._input_dialog.visible = False
        hud._input_dialog.active_field_index = -1
        # Reset input field contents
        for field in hud._input_dialog.fields:
            field["text"] = ""
        if active_tool == "TOOL_CUSTOM":
            active_tool = None
            hud.set_tool_active(None)
        is_paused = False
        hud.set_play_pause_state(False)

    def _cancel_simple_placement() -> None:
        """Cancel simple placement flow (Star/Planet/Probe/Custom), restore time and tool state."""
        nonlocal simple_placement_stage, simple_placement_tool
        nonlocal simple_preview_pos, simple_arrow_start
        nonlocal active_tool, is_paused
        simple_placement_stage = 0
        simple_placement_tool = None
        simple_preview_pos = None
        simple_arrow_start = None
        if active_tool in ("TOOL_STAR", "TOOL_PLANET", "TOOL_PROBE"):
            active_tool = None
            hud.set_tool_active(None)
        is_paused = False
        hud.set_play_pause_state(False)

    # --- Trajectory preview helper functions ---

    def _get_gravity_source(
        bodies_arr: np.ndarray,
        ref_body_id: Optional[int],
    ) -> Optional[Tuple[np.ndarray, float, float]]:
        """Get gravity source body information.

        Args:
            bodies_arr: Body state array
            ref_body_id: Reference frame body ID (may be None)

        Returns:
            (star_pos, star_mass, star_radius) or None (when no gravity source)
        """
        if ref_body_id is not None and ref_body_id < bodies_arr.shape[0]:
            if int(bodies_arr[ref_body_id, IS_ACTIVE]) == 1:
                star_pos = bodies_arr[ref_body_id, [X, Y]].copy()
                star_mass = float(bodies_arr[ref_body_id, MASS])
                star_radius = float(bodies_arr[ref_body_id, RADIUS])
                return (star_pos, star_mass, star_radius)

        # Find nearest star when no reference frame
        nearest = find_nearest_star(
            np.array([0.0, 0.0], dtype=np.float64), bodies_arr
        )
        if nearest is not None:
            _, star_pos, star_mass, star_radius = nearest
            return (star_pos, star_mass, star_radius)

        return None

    def _compute_placement_trajectory(
        pos: np.ndarray,
        vel: np.ndarray,
        star_info: Optional[Tuple[np.ndarray, float, float]],
        body_radius_world: float,
    ) -> Optional[Dict[str, object]]:
        """Compute placement preview trajectory (two-body Kepler approximation, RK4).

        Only considers the reference star's gravity (two-body approximation) to avoid full N-body calculation.
        Predicts approximately 10 seconds.
        Termination conditions (by priority):
          1. Collision with reference star
          2. Distance from reference star > initial distance x 3 (escape)
          3. Angle change around reference star >= 2pi

        Args:
            pos: shape (2,) preview position world coordinates
            vel: shape (2,) velocity vector
            star_info: unused (kept for parameter compatibility)
            body_radius_world: placement body radius (meters)

        Returns:
            Dictionary containing trajectory/collided/escaped/orbited, or None
        """
        speed = float(np.linalg.norm(vel))
        if speed < 1.0:
            return None

        # Find reference star (nearest star or reference frame body)
        ref_star = _get_gravity_source(bodies, reference_body_id)
        if ref_star is None:
            pts = 200
            total_dist = speed * 1e7
            pts_list = []
            for i in range(pts):
                t = i / (pts - 1)
                pts_list.append(pos + vel * t * total_dist / speed)
            return {
                "trajectory": np.array(pts_list, dtype=np.float64),
                "collided": False,
                "escaped": False,
                "orbited": False,
            }

        star_pos, star_mass, star_radius = ref_star
        G = GRAVITATIONAL_CONSTANT

        initial_delta = pos - star_pos
        initial_dist = float(np.linalg.norm(initial_delta))
        escape_dist_threshold = initial_dist * 3.0
        collision_r = star_radius + body_radius_world
        initial_angle = math.atan2(initial_delta[1], initial_delta[0])

        # Fixed step size (not scaled with speed multiplier, because this is a visual preview)
        pred_dt = min(physics_dt * 3125.0, 20000.0)
        max_steps = 3000

        # Only save probe position and velocity (two-body approximation, no full body array needed)
        p = pos.astype(np.float64).copy()
        v = vel.astype(np.float64).copy()

        trajectory = [p.copy()]
        collided = False
        escaped = False
        orbited = False
        total_angle = 0.0
        prev_angle = initial_angle
        def _two_body_acc(pp: np.ndarray) -> np.ndarray:
            """Gravitational acceleration of the reference star on the probe."""
            delta = star_pos - pp
            r2 = float(delta[0] * delta[0] + delta[1] * delta[1])
            if r2 < 1.0:
                return np.array([0.0, 0.0], dtype=np.float64)
            r = math.sqrt(r2)
            a_mag = G * star_mass / r2
            return delta * (a_mag / r)

        def _rk4_step(pp: np.ndarray, vv: np.ndarray, dt: float) -> tuple:
            """Inline RK4 step (two-body gravity only)."""
            # k1
            k1p = vv
            k1v = _two_body_acc(pp)
            # k2
            k2p = vv + k1v * dt * 0.5
            k2v = _two_body_acc(pp + k1p * dt * 0.5)
            # k3
            k3p = vv + k2v * dt * 0.5
            k3v = _two_body_acc(pp + k2p * dt * 0.5)
            # k4
            k4p = vv + k3v * dt
            k4v = _two_body_acc(pp + k3p * dt)

            p_new = pp + (k1p + k2p * 2.0 + k3p * 2.0 + k4p) * (dt / 6.0)
            v_new = vv + (k1v + k2v * 2.0 + k3v * 2.0 + k4v) * (dt / 6.0)
            return p_new, v_new

        for _ in range(max_steps):
            p, v = _rk4_step(p, v, pred_dt)
            trajectory.append(p.copy())

            # 1. Collision detection (reference star only)
            delta = p - star_pos
            d = math.sqrt(float(delta[0] * delta[0] + delta[1] * delta[1]))
            if d < collision_r:
                collided = True
                if len(trajectory) >= 2:
                    last = trajectory[-2]
                    d_last = float(np.linalg.norm(last - star_pos))
                    if d_last > 0:
                        t_hit = (d_last - collision_r) / d_last
                        t_hit = max(0.0, min(t_hit, 1.0))
                        trajectory[-1] = last + (p - last) * t_hit
                break

            # 2. Escape detection
            if d > escape_dist_threshold:
                escaped = True
                break

            # 3. Angle change detection
            current_angle = math.atan2(delta[1], delta[0])
            da = normalize_angle_delta(current_angle - prev_angle)
            total_angle += abs(da)
            prev_angle = current_angle
            if total_angle >= 2.0 * math.pi:
                orbited = True
                break

        return {
            "trajectory": np.array(trajectory, dtype=np.float64),
            "collided": collided,
            "escaped": escaped,
            "orbited": orbited,
        }

    # ==================================================================
    # Main loop
    # ==================================================================

    while running:
        frame_dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.05)  # Max 50ms

        # ================================================================
        # 1. Input handling
        # ================================================================

        commands: List[str] = []

        for event in pygame.event.get():
            # Dialog stage: only dialog can receive events, skip InputHandler
            if custom_placement_stage == 1:
                hud_cmd = hud.handle_event(event)
                if hud_cmd is not None:
                    commands.append(hud_cmd)
                continue

            # HUD processes events first
            hud_cmd = hud.handle_event(event)
            if hud_cmd is not None:
                commands.append(hud_cmd)
                # Toolbar clicks are not passed to InputHandler
                if hud_cmd.startswith("TOOL_"):
                    continue
                # Time control events also skip InputHandler
                if hud_cmd in ("PLAY_PAUSE", "FAST_2X", "FAST_4X", "REWIND"):
                    continue
                # Custom particle dialog commands skip InputHandler
                if hud_cmd.startswith("CUSTOM_DIALOG_"):
                    continue
                # Edit dialog commands skip InputHandler
                if hud_cmd.startswith("EDIT_DIALOG_"):
                    continue

            # When edit dialog is visible, don't pass events to InputHandler
            if hud._edit_dialog.visible:
                continue

            # InputHandler processes (pass bodies and camera for grab detection)
            inp_cmd = input_handler.handle_event(event, bodies, camera)
            if inp_cmd is not None:
                commands.append(inp_cmd)

        # Continuously held arrow keys
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            commands.append("PAN_LEFT")
        if keys[pygame.K_RIGHT]:
            commands.append("PAN_RIGHT")
        if keys[pygame.K_UP]:
            commands.append("PAN_UP")
        if keys[pygame.K_DOWN]:
            commands.append("PAN_DOWN")

        # ================================================================
        # 2. Command processing
        # ================================================================

        for cmd in commands:
            if cmd == "QUIT":
                running = False

            # --- Camera control ---
            elif cmd.startswith("PAN:"):
                parts = cmd.split(":")
                if len(parts) >= 2:
                    coords = parts[1].split(",")
                    if len(coords) == 2:
                        dx = float(coords[0])
                        dy = float(coords[1])
                        # Dead zone threshold: jitter < 3px ignored
                        if abs(dx) + abs(dy) > 3:
                            camera.pan(-dx, -dy)

            elif cmd == "PAN_LEFT":
                camera.pan(-500.0 * frame_dt, 0)
            elif cmd == "PAN_RIGHT":
                camera.pan(500.0 * frame_dt, 0)
            elif cmd == "PAN_UP":
                camera.pan(0, -500.0 * frame_dt)
            elif cmd == "PAN_DOWN":
                camera.pan(0, 500.0 * frame_dt)

            elif cmd.startswith("ZOOM_IN"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])
                if reference_body_id is not None:
                    sx, sy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
                camera.zoom_at(1.1, sx, sy)

            elif cmd.startswith("ZOOM_OUT"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])
                if reference_body_id is not None:
                    sx, sy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
                camera.zoom_at(1.0 / 1.1, sx, sy)

            # --- Time controls ---
            elif cmd == "TOGGLE_PAUSE":
                is_paused = not is_paused
                hud.set_play_pause_state(is_paused)

            elif cmd == "PLAY_PAUSE":
                is_paused = not is_paused
                hud.set_play_pause_state(is_paused)

            elif cmd == "FAST_2X":
                time_multiplier = 2.0 if time_multiplier != 2.0 else 1.0
                time_speed = BASE_TIME_SPEED * time_multiplier
                hud.set_time_speed(time_multiplier)

            elif cmd == "FAST_4X":
                time_multiplier = 4.0 if time_multiplier != 4.0 else 1.0
                time_speed = BASE_TIME_SPEED * time_multiplier
                hud.set_time_speed(time_multiplier)

            elif cmd == "FAST_8X":
                time_multiplier = 8.0 if time_multiplier != 8.0 else 1.0
                time_speed = BASE_TIME_SPEED * time_multiplier
                hud.set_time_speed(time_multiplier)

            elif cmd == "TIME_1X":
                time_multiplier = 1.0
                time_speed = BASE_TIME_SPEED
                hud.set_time_speed(1.0)

            elif cmd == "REWIND":
                # REWIND resets to 1x
                time_multiplier = 1.0
                time_speed = BASE_TIME_SPEED
                hud.set_time_speed(1.0)

            elif cmd == "TOGGLE_GRID":
                show_grid = not show_grid
                renderer.show_grid = show_grid

            elif cmd == "TOGGLE_LABELS":
                show_labels = not show_labels
                renderer.show_labels = show_labels

            elif cmd == "TOGGLE_SHORTCUTS":
                show_shortcuts = not show_shortcuts
                renderer.show_shortcuts = show_shortcuts

            # --- Tool selection ---
            elif cmd.startswith("TOOL_"):
                if active_tool == cmd:
                    # Deselect tool
                    if simple_placement_stage > 0:
                        _cancel_simple_placement()
                    elif custom_placement_stage > 0:
                        _cancel_custom_placement()
                    active_tool = None
                else:
                    # If a previous tool was in placement mode, cancel it first
                    if simple_placement_stage > 0:
                        _cancel_simple_placement()
                    if custom_placement_stage > 0:
                        _cancel_custom_placement()
                    active_tool = cmd
                    if cmd == "TOOL_CUSTOM":
                        # Custom particle tool: freeze time + open scientific notation input dialog
                        is_paused = True
                        hud.set_play_pause_state(True)
                        custom_placement_stage = 1
                        hud.show_custom_dialog()
                    elif cmd in ("TOOL_STAR", "TOOL_PLANET", "TOOL_PROBE"):
                        # Simple placement tool: freeze time + enter preview position stage
                        is_paused = True
                        hud.set_play_pause_state(True)
                        simple_placement_stage = 1
                        simple_placement_tool = cmd
                hud.set_tool_active(active_tool)

            # --- Custom particle dialog commands ---
            elif cmd.startswith("CUSTOM_DIALOG_"):
                if cmd == "CUSTOM_DIALOG_OK":
                    # Close dialog, enter placement preview stage
                    # Values have been stored in hud.custom_mass/charge/speed by HUD.handle_event
                    hud.custom_dialog_visible = False
                    hud._input_dialog.visible = False
                    hud._input_dialog.active_field_index = -1
                    for field in hud._input_dialog.fields:
                        field["text"] = ""
                    custom_placement_stage = 2
                elif cmd == "CUSTOM_DIALOG_CANCEL":
                    # Cancel the entire operation
                    _cancel_custom_placement()

            # --- Edit body dialog commands ---
            elif cmd.startswith("EDIT_DIALOG_"):
                if cmd == "EDIT_DIALOG_OK":
                    if selected_body_id is not None and selected_body_id < bodies.shape[0]:
                        idx = selected_body_id
                        new_mass = hud.edit_mass
                        new_charge = hud.edit_charge
                        new_radius = hud.edit_radius
                        # Update mass, charge, radius
                        bodies[idx, MASS] = new_mass
                        bodies[idx, CHARGE] = new_charge
                        bodies[idx, RADIUS] = new_radius
                        # Refresh info panel
                        hud.set_selected_body(bodies[idx], idx)
                    hud.hide_edit_dialog()
                    is_paused = False
                    hud.set_play_pause_state(False)
                elif cmd == "EDIT_DIALOG_CANCEL":
                    hud.hide_edit_dialog()
                    is_paused = False
                    hud.set_play_pause_state(False)

            # --- Mouse click ---
            elif cmd.startswith("CLICK:"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])

                # Simple placement flow click handling (Star/Planet/Probe)
                if simple_placement_stage > 0:
                    world_x, world_y = camera.screen_to_world(sx, sy)

                    if simple_placement_stage == 1:
                        if simple_placement_tool == "TOOL_STAR":
                            # Star: place directly, skip speed setting step
                            mass, radius_pixels, charge, body_type = (
                                hud.get_default_body_params(simple_placement_tool)
                            )
                            new_body = make_body(
                                x=world_x, y=world_y,
                                vx=0.0, vy=0.0,
                                mass=mass,
                                radius=radius_pixels * WORLD_SCALE,
                                charge=charge,
                                body_type=int(body_type),
                                is_static=True,
                            )
                            bodies = add_body_to_array(bodies, new_body)
                            # Reference frame velocity superposition
                            if reference_body_id is not None and reference_body_id < bodies.shape[0]:
                                if int(bodies[reference_body_id, IS_ACTIVE]) == 1:
                                    bodies[-1, VX] += bodies[reference_body_id, VX]
                                    bodies[-1, VY] += bodies[reference_body_id, VY]
                            _cancel_simple_placement()
                        else:
                            # Planet/Probe: fix preview position, enter speed setting stage
                            simple_preview_pos = (world_x, world_y)
                            simple_arrow_start = (world_x, world_y)
                            simple_placement_stage = 2
                    elif simple_placement_stage == 2:
                        # Stage 2: place body
                        if simple_preview_pos is not None:
                            px, py = simple_preview_pos
                            mass, radius_pixels, charge, body_type = (
                                hud.get_default_body_params(simple_placement_tool)
                            )
                            new_body = make_body(
                                x=px, y=py,
                                vx=0.0, vy=0.0,
                                mass=mass,
                                radius=radius_pixels * WORLD_SCALE,
                                charge=charge,
                                body_type=int(body_type),
                            )
                            bodies = add_body_to_array(bodies, new_body)

                            # Calculate velocity (arrow length x PLACEMENT_SPEED_PER_PX, no upper length limit)
                            sx0, sy0 = camera.world_to_screen(px, py)
                            dx_screen = float(sx) - sx0
                            dy_screen = float(sy) - sy0
                            arrow_dist = math.sqrt(dx_screen ** 2 + dy_screen ** 2)
                            if arrow_dist > 10:
                                actual_speed = arrow_dist * PLACEMENT_SPEED_PER_PX
                                ux = dx_screen / arrow_dist
                                uy = dy_screen / arrow_dist
                                bodies[-1, VX] = ux * actual_speed
                                bodies[-1, VY] = uy * actual_speed
                            # Reference frame velocity superposition
                            if reference_body_id is not None and reference_body_id < bodies.shape[0]:
                                if int(bodies[reference_body_id, IS_ACTIVE]) == 1:
                                    bodies[-1, VX] += bodies[reference_body_id, VX]
                                    bodies[-1, VY] += bodies[reference_body_id, VY]

                            # If a probe was placed, select it
                            if int(body_type) == BODY_TYPE_PROBE:
                                selected_body_id = bodies.shape[0] - 1
                                renderer.selected_body_id = selected_body_id
                                hud.set_selected_body(bodies[selected_body_id], selected_body_id)

                        # Clean up placement state
                        _cancel_simple_placement()
                    continue

                # Custom particle placement flow click handling
                if custom_placement_stage >= 2:
                    world_x, world_y = camera.screen_to_world(sx, sy)

                    if custom_placement_stage == 2:
                        # Stage 2: fix preview position, enter speed setting stage
                        custom_preview_pos = (world_x, world_y)
                        custom_arrow_start = (world_x, world_y)
                        custom_placement_stage = 3
                    elif custom_placement_stage == 3:
                        # Stage 3: place body
                        if custom_preview_pos is not None and custom_arrow_start is not None:
                            px, py = custom_preview_pos
                            new_body = make_body(
                                x=px, y=py,
                                vx=0.0, vy=0.0,
                                mass=hud.custom_mass,
                                radius=hud.custom_radius,
                                charge=hud.custom_charge,
                                body_type=BODY_TYPE_PLANET,
                            )
                            bodies = add_body_to_array(bodies, new_body)

                            # Calculate velocity
                            sx0, sy0 = camera.world_to_screen(px, py)
                            dx_screen = float(sx) - sx0
                            dy_screen = float(sy) - sy0
                            arrow_dist = math.sqrt(dx_screen ** 2 + dy_screen ** 2)
                            if arrow_dist > 10:
                                actual_speed = arrow_dist * PLACEMENT_SPEED_PER_PX
                                ux = dx_screen / arrow_dist
                                uy = dy_screen / arrow_dist
                                bodies[-1, VX] = ux * actual_speed
                                bodies[-1, VY] = uy * actual_speed
                            # Reference frame velocity superposition
                            if reference_body_id is not None and reference_body_id < bodies.shape[0]:
                                if int(bodies[reference_body_id, IS_ACTIVE]) == 1:
                                    bodies[-1, VX] += bodies[reference_body_id, VX]
                                    bodies[-1, VY] += bodies[reference_body_id, VY]

                        # Clean up placement state
                        _cancel_custom_placement()
                    continue

                # Dialog stage (stage 1) ignores all clicks
                if custom_placement_stage == 1:
                    continue

                # Check if in UI area
                if sx < 50 or sy > WINDOW_HEIGHT - 50:  # Toolbar or control bar area
                    continue

                if active_tool:
                    # Use tool to place body
                    world_x, world_y = camera.screen_to_world(sx, sy)
                    mass, radius, charge, body_type = hud.get_default_body_params(active_tool)

                    new_body = make_body(
                        x=world_x, y=world_y,
                        vx=0.0, vy=0.0,
                        mass=mass,
                        radius=radius * WORLD_SCALE,  # Convert pixel radius to world units
                        charge=charge,
                        body_type=int(body_type),
                    )
                    bodies = add_body_to_array(bodies, new_body)

                    # Reference frame velocity stacking
                    if reference_body_id is not None and reference_body_id < bodies.shape[0]:
                        if int(bodies[reference_body_id, IS_ACTIVE]) == 1:
                            bodies[-1, VX] += bodies[reference_body_id, VX]
                            bodies[-1, VY] += bodies[reference_body_id, VY]

                    # If a probe was placed, select it and allow aiming
                    if int(body_type) == BODY_TYPE_PROBE:
                        selected_body_id = bodies.shape[0] - 1
                        renderer.selected_body_id = selected_body_id
                        hud.set_selected_body(bodies[selected_body_id], selected_body_id)

                    # Keep tool active after placement (can place continuously)
                else:
                    # Select body
                    found_id = input_handler.find_body_at_screen_pos(sx, sy, bodies, camera)
                    if found_id is not None:
                        selected_body_id = found_id
                        renderer.selected_body_id = found_id
                        hud.set_selected_body(bodies[found_id], found_id)
                    else:
                        # Deselect
                        selected_body_id = None
                        renderer.selected_body_id = None
                        hud.set_selected_body(None, -1)

            # --- Left-click grab/drag ---
            elif cmd.startswith("GRAB_START:"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                body_id = int(sx_str[0])
                sx, sy = int(sx_str[1]), int(sx_str[2])

                # Simple placement flow click handling (same logic as CLICK)
                if simple_placement_stage > 0:
                    input_handler.reset_grab()
                    world_x, world_y = camera.screen_to_world(sx, sy)

                    if simple_placement_stage == 1:
                        if simple_placement_tool == "TOOL_STAR":
                            # Star: place directly, skip speed setting step
                            mass, radius_pixels, charge, body_type = (
                                hud.get_default_body_params(simple_placement_tool)
                            )
                            new_body = make_body(
                                x=world_x, y=world_y,
                                vx=0.0, vy=0.0,
                                mass=mass,
                                radius=radius_pixels * WORLD_SCALE,
                                charge=charge,
                                body_type=int(body_type),
                                is_static=True,
                            )
                            bodies = add_body_to_array(bodies, new_body)
                            # Reference frame velocity superposition
                            if reference_body_id is not None and reference_body_id < bodies.shape[0]:
                                if int(bodies[reference_body_id, IS_ACTIVE]) == 1:
                                    bodies[-1, VX] += bodies[reference_body_id, VX]
                                    bodies[-1, VY] += bodies[reference_body_id, VY]
                            _cancel_simple_placement()
                        else:
                            simple_preview_pos = (world_x, world_y)
                            simple_arrow_start = (world_x, world_y)
                            simple_placement_stage = 2
                    elif simple_placement_stage == 2:
                        if simple_preview_pos is not None:
                            px, py = simple_preview_pos
                            mass, radius_pixels, charge, body_type = (
                                hud.get_default_body_params(simple_placement_tool)
                            )
                            new_body = make_body(
                                x=px, y=py,
                                vx=0.0, vy=0.0,
                                mass=mass,
                                radius=radius_pixels * WORLD_SCALE,
                                charge=charge,
                                body_type=int(body_type),
                            )
                            bodies = add_body_to_array(bodies, new_body)

                            sx0, sy0 = camera.world_to_screen(px, py)
                            dx_screen = float(sx) - sx0
                            dy_screen = float(sy) - sy0
                            arrow_dist = math.sqrt(dx_screen ** 2 + dy_screen ** 2)
                            if arrow_dist > 10:
                                actual_speed = arrow_dist * PLACEMENT_SPEED_PER_PX
                                ux = dx_screen / arrow_dist
                                uy = dy_screen / arrow_dist
                                bodies[-1, VX] = ux * actual_speed
                                bodies[-1, VY] = uy * actual_speed

                            if int(body_type) == BODY_TYPE_PROBE:
                                selected_body_id = bodies.shape[0] - 1
                                renderer.selected_body_id = selected_body_id
                                hud.set_selected_body(bodies[selected_body_id], selected_body_id)

                        _cancel_simple_placement()
                    continue

                # Custom particle placement flow click handling (same stage logic as CLICK)
                if custom_placement_stage >= 2:
                    input_handler.reset_grab()
                    world_x, world_y = camera.screen_to_world(sx, sy)

                    if custom_placement_stage == 2:
                        custom_preview_pos = (world_x, world_y)
                        custom_arrow_start = (world_x, world_y)
                        custom_placement_stage = 3
                    elif custom_placement_stage == 3:
                        if custom_preview_pos is not None and custom_arrow_start is not None:
                            px, py = custom_preview_pos
                            new_body = make_body(
                                x=px, y=py,
                                vx=0.0, vy=0.0,
                                mass=hud.custom_mass,
                                radius=hud.custom_radius,
                                charge=hud.custom_charge,
                                body_type=BODY_TYPE_PLANET,
                            )
                            bodies = add_body_to_array(bodies, new_body)

                            sx0, sy0 = camera.world_to_screen(px, py)
                            dx_screen = float(sx) - sx0
                            dy_screen = float(sy) - sy0
                            arrow_dist = math.sqrt(dx_screen ** 2 + dy_screen ** 2)
                            if arrow_dist > 10:
                                actual_speed = arrow_dist * PLACEMENT_SPEED_PER_PX
                                ux = dx_screen / arrow_dist
                                uy = dy_screen / arrow_dist
                                bodies[-1, VX] = ux * actual_speed
                                bodies[-1, VY] = uy * actual_speed

                        _cancel_custom_placement()
                    continue

                # Dialog stage (stage 1) ignores all clicks
                if custom_placement_stage == 1:
                    input_handler.reset_grab()
                    continue

                if active_tool:
                    # Don't enter grab mode when tool is active, reset handler state
                    input_handler.reset_grab()
                    # Treat as tool placement (same logic as CLICK)
                    if sx < 50 or sy > WINDOW_HEIGHT - 50:
                        continue
                    world_x, world_y = camera.screen_to_world(sx, sy)
                    mass, radius, charge, body_type = hud.get_default_body_params(active_tool)
                    new_body = make_body(
                        x=world_x, y=world_y,
                        vx=0.0, vy=0.0,
                        mass=mass,
                        radius=radius * WORLD_SCALE,
                        charge=charge,
                        body_type=int(body_type),
                    )
                    bodies = add_body_to_array(bodies, new_body)
                    # Reference frame velocity stacking
                    if reference_body_id is not None and reference_body_id < bodies.shape[0]:
                        if int(bodies[reference_body_id, IS_ACTIVE]) == 1:
                            bodies[-1, VX] += bodies[reference_body_id, VX]
                            bodies[-1, VY] += bodies[reference_body_id, VY]
                    if int(body_type) == BODY_TYPE_PROBE:
                        selected_body_id = bodies.shape[0] - 1
                        renderer.selected_body_id = selected_body_id
                        hud.set_selected_body(bodies[selected_body_id], selected_body_id)
                else:
                    if is_paused:
                        # Don't grab bodies while paused, only select
                        input_handler.reset_grab()
                        selected_body_id = body_id
                        renderer.selected_body_id = body_id
                        hud.set_selected_body(bodies[body_id], body_id)
                        continue
                    # Enter grab mode
                    is_grabbing = True
                    grabbed_body_id = body_id
                    is_paused = True
                    hud.set_play_pause_state(True)
                    # Select the grabbed body
                    selected_body_id = body_id
                    renderer.selected_body_id = body_id
                    hud.set_selected_body(bodies[body_id], body_id)

            elif cmd.startswith("GRAB_DRAG:"):
                parts = cmd.split(":")
                coords = parts[1].split(",")
                sx, sy = int(coords[1]), int(coords[2])
                if grabbed_body_id is not None and grabbed_body_id < bodies.shape[0]:
                    wx, wy = camera.screen_to_world(sx, sy)
                    bodies[grabbed_body_id, X] = wx
                    bodies[grabbed_body_id, Y] = wy
                _grab_actually_dragged = True

            elif cmd == "GRAB_END":
                if grabbed_body_id is not None:
                    trail_buffer.clear(grabbed_body_id)
                    if _grab_actually_dragged:
                        # Only zero velocity if actually dragged; click-select does not zero
                        bodies[grabbed_body_id, VX] = 0.0
                        bodies[grabbed_body_id, VY] = 0.0
                is_grabbing = False
                grabbed_body_id = None
                _grab_actually_dragged = False
                is_paused = False
                hud.set_play_pause_state(False)

            # --- Right-click ---
            elif cmd.startswith("RIGHT_CLICK:"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])

                # Right-click handling for simple placement flow
                if simple_placement_stage > 0:
                    if simple_placement_stage == 2:
                        # Stage 2: return to stage 1 (re-select position)
                        simple_placement_stage = 1
                        simple_preview_pos = None
                        simple_arrow_start = None
                    else:
                        # Stage 1: cancel entire operation
                        _cancel_simple_placement()
                    continue

                # Right-click handling for custom particle placement flow
                if custom_placement_stage > 0:
                    if custom_placement_stage == 3:
                        # Stage 3: return to stage 2 (re-select position)
                        custom_placement_stage = 2
                        custom_preview_pos = None
                        custom_arrow_start = None
                    else:
                        # Stage 1 or 2: cancel entire operation
                        _cancel_custom_placement()
                    continue

                # If a tool is active, cancel it
                if active_tool:
                    active_tool = None
                    hud.set_tool_active(None)
                    continue

                # Check if clicking on an existing probe
                found_id = input_handler.find_body_at_screen_pos(sx, sy, bodies, camera)
                if found_id is not None and int(bodies[found_id, BODY_TYPE]) == BODY_TYPE_PROBE:
                    # Start aiming
                    is_aiming = True
                    input_handler.start_aiming()
                    aim_start_screen = (sx, sy)
                    world_x, world_y = camera.screen_to_world(sx, sy)
                    aim_start_world = (world_x, world_y)
                    selected_body_id = found_id
                    renderer.selected_body_id = found_id
                    hud.set_selected_body(bodies[found_id], found_id)
                elif found_id is not None:
                    # Right-click on another body -> edit that body
                    selected_body_id = found_id
                    renderer.selected_body_id = found_id
                    hud.set_selected_body(bodies[found_id], found_id)
                    body_mass = float(bodies[found_id, MASS])
                    body_charge = float(bodies[found_id, CHARGE])
                    body_radius = float(bodies[found_id, RADIUS])
                    is_paused = True
                    hud.set_play_pause_state(True)
                    hud.show_edit_dialog(body_mass, body_charge, body_radius)
                else:
                    # Right-click on empty space -> deselect
                    selected_body_id = None
                    renderer.selected_body_id = None
                    hud.set_selected_body(None, -1)
                    active_tool = None
                    hud.set_tool_active(None)

            # --- Double-click: follow body ---
            elif cmd.startswith("DOUBLE_CLICK:"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])
                found_id = input_handler.find_body_at_screen_pos(sx, sy, bodies, camera)
                if found_id is not None:
                    _saved_zoom_before_frame = camera.zoom
                    reference_body_id = found_id
                    hud.set_reference_frame(found_id, int(bodies[found_id, BODY_TYPE]))
                    # Auto zoom to make target body about 50px size, and center on screen
                    target_screen_radius = 50.0
                    body_world_radius = float(bodies[found_id, RADIUS])
                    if body_world_radius > 0:
                        desired_zoom = target_screen_radius * WORLD_SCALE / body_world_radius
                        desired_zoom = max(CAMERA_ZOOM_MIN, min(CAMERA_ZOOM_MAX, desired_zoom))
                        camera.zoom = desired_zoom
                    wx = float(bodies[found_id, X])
                    wy = float(bodies[found_id, Y])
                    camera.follow(wx, wy)

            # --- Launch probe ---
            elif cmd.startswith("LAUNCH_PROBE:"):
                parts = cmd.split(":")
                if len(parts) >= 2:
                    coords = parts[1].split(",")
                    if len(coords) == 4:
                        start_x = float(coords[0])
                        start_y = float(coords[1])
                        dx = float(coords[2])
                        dy = float(coords[3])

                    # Convert to world coordinate velocity
                    # Opposite of drag direction is launch direction, force proportional to drag distance
                    world_dx = dx * WORLD_SCALE / camera.zoom
                    world_dy = dy * WORLD_SCALE / camera.zoom
                    launch_speed = min(
                        math.sqrt(world_dx**2 + world_dy**2),
                        1.0e6,  # Maximum speed limit
                    )

                    if launch_speed > 100.0 and selected_body_id is not None:
                        idx = selected_body_id
                        if idx < bodies.shape[0]:
                            # Direction: opposite of mouse drag direction
                            angle = math.atan2(-world_dy, -world_dx)
                            bodies[idx, VX] = math.cos(angle) * launch_speed
                            bodies[idx, VY] = math.sin(angle) * launch_speed

                            # Exhaust particles
                            sx_world = float(bodies[idx, X])
                            sy_world = float(bodies[idx, Y])
                            psx, psy = camera.world_to_screen(sx_world, sy_world)
                            particle_system.emit_probe_exhaust(psx, psy, angle)

                    is_aiming = False

            elif cmd == "DELETE_SELECTED":
                if selected_body_id is not None:
                    trail_buffer.clear(selected_body_id)
                    bodies = remove_body_from_array(bodies, selected_body_id)
                    selected_body_id = None
                    renderer.selected_body_id = None
                    hud.set_selected_body(None, -1)

            elif cmd == "MENU":
                if show_shortcuts:
                    show_shortcuts = False
                    renderer.show_shortcuts = False
                    continue
                if simple_placement_stage > 0:
                    _cancel_simple_placement()
                elif custom_placement_stage > 0:
                    _cancel_custom_placement()
                elif reference_body_id is not None:
                    # Save current reference frame body position, keep center at current location
                    if reference_body_id < bodies.shape[0]:
                        last_x = float(bodies[reference_body_id, X])
                        last_y = float(bodies[reference_body_id, Y])
                        camera.follow(last_x, last_y)
                    zoom_to_restore = _saved_zoom_before_frame
                    if abs(camera.zoom - zoom_to_restore) > 0.01:
                        camera.zoom_at(zoom_to_restore / camera.zoom, WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
                    reference_body_id = None
                    hud.clear_reference_frame()
                    continue
                else:
                    running = False

        # ================================================================
        # 3. Physics update (fixed time step)
        # ================================================================

        if not is_paused and not is_grabbing:
            if time_speed > 100:
                # High speed: scale dt directly (avoid millions of tiny steps)
                # Physics engine uses SUBSTEPS=4, RK4 guarantees stability
                big_dt = physics_dt * time_speed
                bodies = physics_engine.update(bodies, big_dt)
            else:
                accumulator += frame_dt * time_speed
                max_accumulate = physics_dt * 10
                if accumulator > max_accumulate:
                    accumulator = max_accumulate
                while accumulator >= physics_dt:
                    bodies = physics_engine.update(bodies, physics_dt)
                    accumulator -= physics_dt
        else:
            # Reset accumulator when paused
            accumulator = 0.0

        # ================================================================
        # 4. Trail recording
        # ================================================================

        # When paused, no new trail frames and no fade progression
        if not is_paused:
            if is_grabbing and grabbed_body_id is not None:
                trail_buffer.push_all(bodies, exclude={grabbed_body_id})
            else:
                trail_buffer.push_all(bodies)

        # ================================================================
        # 5. Post-trail data update
        # ================================================================

        # Get trail data
        trails = trail_buffer.get_all_trails()
        fade_factors = trail_buffer.get_fade_factors()

        # Follow selected body
        if selected_body_id is not None and not is_aiming:
            if selected_body_id < bodies.shape[0] and bodies[selected_body_id, IS_ACTIVE] == 1.0:
                # Only follow when F is pressed, otherwise no auto-follow
                # Or auto-follow after double click (handled in DOUBLE_CLICK)
                pass
            else:
                # Selected body has disappeared
                selected_body_id = None
                renderer.selected_body_id = None
                hud.set_selected_body(None, -1)

        # Predicted trajectory (recalculate every 3 frames for selected probe; skip while grabbing)
        _prediction_frame_counter += 1
        should_recalc = (
            selected_body_id is not None
            and selected_body_id < bodies.shape[0]
            and int(bodies[selected_body_id, BODY_TYPE]) == BODY_TYPE_PROBE
            and not is_grabbing
        )
        # Recalculate immediately when selection changes
        if should_recalc and selected_body_id != _last_predicted_body_id:
            _prediction_frame_counter = 0
            _last_predicted_body_id = selected_body_id
        if not should_recalc:
            _last_predicted_body_id = None

        if should_recalc and _prediction_frame_counter % 6 == 1:
            probe_data = bodies[selected_body_id:selected_body_id + 1].copy()
            other_bodies = np.delete(bodies, selected_body_id, axis=0)
            if other_bodies.shape[0] > 0:
                # Use same dt as simulation, predict ~1 second visual time
                if time_speed > 100:
                    pred_dt = physics_dt * time_speed  # Same dt as simulation
                    # Visual steps for 1 second = 60fps / multiplier
                    pred_steps = int(TARGET_FPS / max(1, time_multiplier))
                    pred_steps = max(3, min(pred_steps, 60))
                else:
                    pred_dt = physics_dt
                    pred_steps = 60
                pred = physics_engine.predict_trajectory(
                    probe_data, other_bodies, steps=pred_steps, dt=pred_dt
                )
                if pred.shape[0] > 0:
                    predicted_trajectory = pred
                else:
                    predicted_trajectory = None
            else:
                predicted_trajectory = None
        elif not should_recalc:
            predicted_trajectory = None

        # Update particle system
        particle_system.update(frame_dt)

        # Reference frame body disappearance check
        if reference_body_id is not None:
            if reference_body_id >= bodies.shape[0] or bodies[reference_body_id, IS_ACTIVE] == 0.0:
                # Save last known position and follow, so center stops at vanishing point
                if reference_body_id < bodies.shape[0]:
                    last_x = float(bodies[reference_body_id, X])
                    last_y = float(bodies[reference_body_id, Y])
                    camera.follow(last_x, last_y)
                # Restore zoom on exit
                zoom_to_restore = _saved_zoom_before_frame
                if abs(camera.zoom - zoom_to_restore) > 0.01:
                    camera.zoom_at(zoom_to_restore / camera.zoom, WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
                reference_body_id = None
                hud.clear_reference_frame()
            else:
                # Follow reference body each frame (velocity feedforward + smooth lerp)
                effective_dt = TIME_STEP * time_speed
                ref_vx = float(bodies[reference_body_id, VX])
                ref_vy = float(bodies[reference_body_id, VY])
                ref_wx = float(bodies[reference_body_id, X])
                ref_wy = float(bodies[reference_body_id, Y])
                camera.update_follow(ref_wx, ref_wy, ref_vx, ref_vy, effective_dt)

        # ================================================================
        # 6. Rendering
        # ================================================================

        # Update aim line
        if is_aiming and selected_body_id is not None:
            world_x, world_y = camera.screen_to_world(
                input_handler.mouse_screen_x,
                input_handler.mouse_screen_y,
            )
            aim_current_world = (world_x, world_y)

        # Compute placement trajectory preview
        placement_trajectory = None
        if custom_placement_stage == 3 and custom_arrow_start is not None:
            px, py = custom_preview_pos
            # Compute velocity vector (same logic as placement)
            spx, spy = camera.world_to_screen(px, py)
            mx, my = input_handler.mouse_screen_x, input_handler.mouse_screen_y
            dx_screen = float(mx) - spx
            dy_screen = float(my) - spy
            arrow_dist = math.sqrt(dx_screen ** 2 + dy_screen ** 2)
            if arrow_dist > 10:
                actual_speed = arrow_dist * PLACEMENT_SPEED_PER_PX
                ux = dx_screen / arrow_dist
                uy = dy_screen / arrow_dist
                vel = np.array([ux * actual_speed, uy * actual_speed], dtype=np.float64)
                # Compute trajectory (using physics engine RK4 + full gravity)
                placement_trajectory = _compute_placement_trajectory(
                    np.array([px, py], dtype=np.float64), vel,
                    None, hud.custom_radius,
                )
        elif simple_placement_stage == 2 and simple_arrow_start is not None:
            px, py = simple_preview_pos
            _, radius_pixels, _, body_type = hud.get_default_body_params(simple_placement_tool)
            # Compute velocity vector (same logic as placement)
            spx, spy = camera.world_to_screen(px, py)
            mx, my = input_handler.mouse_screen_x, input_handler.mouse_screen_y
            dx_screen = float(mx) - spx
            dy_screen = float(my) - spy
            arrow_dist = math.sqrt(dx_screen ** 2 + dy_screen ** 2)
            if arrow_dist > 10:
                actual_speed = arrow_dist * PLACEMENT_SPEED_PER_PX
                ux = dx_screen / arrow_dist
                uy = dy_screen / arrow_dist
                vel = np.array([ux * actual_speed, uy * actual_speed], dtype=np.float64)
                # Compute trajectory (using physics engine RK4 + full gravity)
                body_radius = radius_pixels * WORLD_SCALE
                placement_trajectory = _compute_placement_trajectory(
                    np.array([px, py], dtype=np.float64), vel,
                    None, body_radius,
                )

        # Render
        renderer.render(bodies, trails, camera, fade_factors)

        # Custom particle placement preview
        if custom_placement_stage == 2:
            # Stage 2: preview circle follows mouse
            mouse_wx, mouse_wy = input_handler.get_mouse_world_pos(camera)
            radius_world = hud.custom_radius
            renderer.draw_placement_preview(
                mouse_wx, mouse_wy, radius_world, camera, renderer.screen
            )
        elif custom_placement_stage == 3 and custom_preview_pos is not None:
            # Stage 3: fixed preview circle + velocity direction arrow
            px, py = custom_preview_pos
            radius_world = hud.custom_radius
            renderer.draw_placement_preview(
                px, py, radius_world, camera, renderer.screen
            )
            # Only draw velocity arrow when length > 3px
            spx, spy = camera.world_to_screen(px, py)
            mx, my = input_handler.mouse_screen_x, input_handler.mouse_screen_y
            arrow_screen_dist = math.sqrt((mx - spx) ** 2 + (my - spy) ** 2)
            if arrow_screen_dist > 10:
                renderer.draw_velocity_arrow(
                    (px, py),
                    (input_handler.mouse_screen_x, input_handler.mouse_screen_y),
                    float("inf"),  # No length limit
                    camera,
                    renderer.screen,
                )

        # Simple placement preview (Star / Planet / Probe)
        if simple_placement_stage == 1 and simple_placement_tool is not None:
            # Stage 1: preview circle follows mouse
            mouse_wx, mouse_wy = input_handler.get_mouse_world_pos(camera)
            _, radius_pixels, _, _ = hud.get_default_body_params(simple_placement_tool)
            radius_world = radius_pixels * WORLD_SCALE
            renderer.draw_placement_preview(
                mouse_wx, mouse_wy, radius_world, camera, renderer.screen
            )
        elif simple_placement_stage == 2 and simple_preview_pos is not None:
            # Stage 2: fixed preview circle + velocity direction arrow (no length limit)
            px, py = simple_preview_pos
            _, radius_pixels, _, _ = hud.get_default_body_params(simple_placement_tool)
            radius_world = radius_pixels * WORLD_SCALE
            renderer.draw_placement_preview(
                px, py, radius_world, camera, renderer.screen
            )
            # Only draw velocity arrow when length > 3px
            spx, spy = camera.world_to_screen(px, py)
            mx, my = input_handler.mouse_screen_x, input_handler.mouse_screen_y
            arrow_screen_dist = math.sqrt((mx - spx) ** 2 + (my - spy) ** 2)
            if arrow_screen_dist > 10:
                renderer.draw_velocity_arrow(
                    (px, py),
                    (input_handler.mouse_screen_x, input_handler.mouse_screen_y),
                    float("inf"),  # No length limit
                    camera,
                    renderer.screen,
                )

        # Draw placement trajectory preview
        if placement_trajectory is not None:
            renderer.render_placement_trajectory(placement_trajectory, camera)

        # Draw aim line
        if is_aiming:
            start_screen = camera.world_to_screen(
                aim_start_world[0], aim_start_world[1]
            )
            end_screen = (
                input_handler.mouse_screen_x,
                input_handler.mouse_screen_y,
            )
            ddx = end_screen[0] - start_screen[0]
            ddy = end_screen[1] - start_screen[1]
            dist = math.sqrt(ddx*ddx + ddy*ddy)
            if dist > 5:
                # Line from probe to mouse (blue aim line)
                pygame.draw.line(
                    renderer.screen,
                    (100, 200, 255, 160),
                    start_screen, end_screen, 2,
                )
                # Launch direction indicator (opposite direction, orange)
                launch_end = (
                    start_screen[0] - int(ddx * 1.5),
                    start_screen[1] - int(ddy * 1.5),
                )
                pygame.draw.line(
                    renderer.screen,
                    (255, 180, 50, 200),
                    start_screen, launch_end, 3,
                )

        # Draw predicted trajectory
        if predicted_trajectory is not None and predicted_trajectory.shape[0] > 1:
            renderer.render_predicted_trajectory(predicted_trajectory, camera)

        # Draw particles
        particle_system.render(renderer.screen)

        # Update status info and draw HUD
        hud.set_status_info(
            num_bodies=bodies.shape[0],
            time_speed=time_multiplier,
            fps=clock.get_fps(),
            mouse_world_pos=(
                input_handler.mouse_world_x,
                input_handler.mouse_world_y,
            ),
        )
        hud.draw(renderer.screen, camera)
        renderer.render_hud(game_state)

        # Update window title
        actual_fps = clock.get_fps()
        paused_indicator = " PAUSED" if is_paused else ""
        grabbing_indicator = " GRABBING" if is_grabbing else ""
        speed_indicator = f" {time_multiplier:.0f}x" if time_multiplier > 1 else ""
        pygame.display.set_caption(
            f"MiniSFS{grabbing_indicator}{paused_indicator}{speed_indicator}"
            f" - Bodies: {bodies.shape[0]}"
            f" - zoom: {camera.zoom:.1f}"
            f" - {actual_fps:.0f} FPS"
        )

        # Refresh display
        pygame.display.flip()

    # ================================================================
    # Exit
    # ================================================================
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
