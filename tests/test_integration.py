"""MiniSFS integration test suite.

Tests the cooperation and data flow between modules, covering cross-module
interactions of the physics engine, camera, input handler, trail buffer,
and other core modules.

All tests involving Pygame windows use the dummy video driver mode.
"""

import math
import os

import numpy as np
import pytest

from src.config import (
    CAMERA_ZOOM_MAX,
    CLICK_SELECTION_RADIUS,
    COULOMB_CONSTANT,
    GRAVITATIONAL_CONSTANT,
    SOFTENING,
    WORLD_SCALE,
)
from src.core.types import (
    BODY_TYPE_PLANET,
    BODY_TYPE_STAR,
    IS_ACTIVE,
    IS_STATIC,
    MASS,
    VX,
    VY,
    X,
    Y,
    make_body,
)
from src.input.handler import InputHandler
from src.main import create_default_scene
from src.physics.engine import PhysicsEngine
from src.quadtree.trail import TrailBuffer
from src.rendering.camera import Camera


# ============================================================================
# fixture: Pygame dummy mode
# ============================================================================


@pytest.fixture(scope="module")
def pygame_dummy() -> None:
    """Initialize Pygame with dummy video driver to avoid opening a real window."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


# ============================================================================
# Helper functions
# ============================================================================


def _create_two_body_circular(
    m_center: float = 1.0e30,
    m_orbiter: float = 5.0e28,
    orbit_radius: float = 1.5e11,
    center_static: bool = True,
) -> np.ndarray:
    """Create a two-body system with 1 central body + 1 orbiting body.

    Args:
        m_center: Mass of the central body (kg)
        m_orbiter: Mass of the orbiting body (kg)
        orbit_radius: Orbital radius (m)
        center_static: Whether the central body is static

    Returns:
        Body state array of shape (2, NUM_FIELDS)
    """
    orbital_speed = math.sqrt(
        GRAVITATIONAL_CONSTANT * m_center / orbit_radius
    )
    b1 = make_body(
        x=0.0, y=0.0,
        vx=0.0, vy=0.0,
        mass=m_center,
        radius=1.0e6,
        body_type=BODY_TYPE_STAR,
        is_static=center_static,
    )
    b2 = make_body(
        x=orbit_radius, y=0.0,
        vx=0.0, vy=orbital_speed,
        mass=m_orbiter,
        radius=1.0e6,
        body_type=BODY_TYPE_PLANET,
    )
    return np.vstack([b1, b2])


# ============================================================================
# Test classes
# ============================================================================


class TestPhysicsIntegration:
    """Physics engine integration tests."""

    def test_physics_bodies_move(self) -> None:
        """Verify that non-static bodies move and static stars do not after physics update."""
        engine = PhysicsEngine(softening=SOFTENING)
        bodies = create_default_scene()
        dt = 1.0 / 60.0

        # Record positions before update
        positions_before = bodies[:, [X, Y]].copy()

        # Execute one physics update
        bodies = engine.update(bodies, dt)

        # Check movement for all bodies
        for i in range(bodies.shape[0]):
            is_static = bool(bodies[i, IS_STATIC])
            is_active = bool(bodies[i, IS_ACTIVE])

            if not is_active:
                continue

            dx = float(bodies[i, X] - positions_before[i, 0])
            dy = float(bodies[i, Y] - positions_before[i, 1])
            moved = math.sqrt(dx**2 + dy**2) > 0.0

            if is_static:
                assert not moved, f"Body {i} (static) should not move"
            else:
                assert moved, f"Body {i} (non-static) should move"

    def test_energy_conservation(self) -> None:
        """Energy fluctuation < 0.1% after 100 steps of two-body circular orbit."""
        engine = PhysicsEngine(g=GRAVITATIONAL_CONSTANT, softening=SOFTENING)
        # Use a static supermassive central body
        m_center = 1.0e30
        m_orbiter = 5.0e28
        orbit_r = 1.5e11

        bodies = _create_two_body_circular(
            m_center=m_center,
            m_orbiter=m_orbiter,
            orbit_radius=orbit_r,
            center_static=True,
        )

        dt = 1.0 / 60.0
        n_steps = 100

        e0 = engine.get_total_energy(bodies)
        energies = [e0]

        for _ in range(n_steps):
            bodies = engine.update(bodies, dt)
            energies.append(engine.get_total_energy(bodies))

        e_max = max(energies)
        e_min = min(energies)
        e_range = (e_max - e_min) / abs(e0) * 100  # percentage

        assert e_range < 0.1, (
            f"Energy fluctuation {e_range:.4f}% exceeds 0.1%"
        )

    def test_gravitational_force_symmetric(self) -> None:
        """Verify gravitational force F12 = -F21."""
        m1 = 1.0e30
        m2 = 5.0e28
        dist = 1.5e11

        b1 = make_body(x=0.0, y=0.0, mass=m1)
        b2 = make_body(x=dist, y=0.0, mass=m2)
        bodies = np.vstack([b1, b2])

        engine = PhysicsEngine(g=GRAVITATIONAL_CONSTANT, softening=SOFTENING)
        forces = engine.compute_forces(bodies)

        # Verify equal magnitudes
        f1_mag = float(np.linalg.norm(forces[0]))
        f2_mag = float(np.linalg.norm(forces[1]))
        assert f1_mag == pytest.approx(f2_mag, rel=1e-10), "Gravitational force magnitudes not equal"

        # Verify opposite directions
        assert forces[0, 0] == pytest.approx(-forces[1, 0], rel=1e-10), "F_x not antisymmetric"
        assert forces[0, 1] == pytest.approx(-forces[1, 1], rel=1e-10), "F_y not antisymmetric"

        # Verify magnitude matches Newton's formula
        expected = GRAVITATIONAL_CONSTANT * m1 * m2 / (dist**2)
        assert f1_mag == pytest.approx(expected, rel=1e-10), "Gravitational force magnitude does not match Newton's formula"

    def test_get_body_count_and_state(self) -> None:
        """Verify get_body_count and get_body_state return correct data."""
        engine = PhysicsEngine()
        bodies = create_default_scene()

        count = engine.get_body_count(bodies)
        assert count == 2, f"Expected 2 active bodies, got {count}"

        # Check body 0 (star)
        state = engine.get_body_state(bodies, 0)
        assert state["is_static"] is True
        assert state["mass"] == pytest.approx(2.0e30, rel=1e-10)
        assert state["x"] == 0.0
        assert state["y"] == 0.0

        # Check body 1 (planet)
        state = engine.get_body_state(bodies, 1)
        assert state["is_static"] is False
        assert state["mass"] == pytest.approx(6.0e26, rel=1e-10)
        assert state["vx"] == 0.0
        assert float(state["vy"]) > 0  # has tangential velocity

    def test_get_total_momentum(self) -> None:
        """Verify momentum query API returns reasonable values."""
        engine = PhysicsEngine()
        bodies = create_default_scene()

        px, py = engine.get_total_momentum(bodies)

        # Default scene total momentum should be near zero (symmetric motion)
        total_mass = float(np.sum(bodies[:, MASS]))
        # px and py should be reasonable finite values
        assert math.isfinite(px)
        assert math.isfinite(py)
        # Total momentum should not be NaN
        assert not math.isnan(px)
        assert not math.isnan(py)

        # Two-body circular orbit momentum should be conserved
        binary = _create_two_body_circular(center_static=False)
        px0, py0 = engine.get_total_momentum(binary)
        engine.update(binary, 1.0)
        px1, py1 = engine.get_total_momentum(binary)
        assert px0 == pytest.approx(px1, abs=1.0)
        assert py0 == pytest.approx(py1, abs=1.0)


class TestCameraIntegration:
    """Camera integration tests."""

    def test_camera_pan_zoom(self) -> None:
        """Verify camera pan and zoom change center and zoom values."""
        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)

        # Initial state
        assert camera.center_x == 0.0
        assert camera.center_y == 0.0
        assert camera.zoom == 1.0

        # Pan 100, 50 pixels
        camera.pan(100.0, 50.0)
        assert camera.center_x != 0.0, "center_x should change after pan"
        assert camera.center_y != 0.0, "center_y should change after pan"

        # Verify direction: positive dx shifts world coordinates right
        assert camera.center_x > 0.0
        assert camera.center_y > 0.0

        # Zoom
        camera.zoom_at(2.0, 640, 360)
        assert camera.zoom != 1.0, "zoom should change after zoom"
        assert camera.zoom > 1.0, "zoom should be > 1 after zooming in"

        # Zoom multiple times to maximum
        camera.zoom_at(10.0, 640, 360)
        assert camera.zoom <= CAMERA_ZOOM_MAX, "zoom should not exceed max"

    def test_camera_get_state(self) -> None:
        """Verify get_state returns the correct camera state dictionary."""
        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)
        camera.pan(200.0, -100.0)
        camera.zoom_at(1.5, 640, 360)

        state = camera.get_state()
        assert "center_x" in state
        assert "center_y" in state
        assert "zoom" in state
        assert state["center_x"] == camera.center_x
        assert state["center_y"] == camera.center_y
        assert state["zoom"] == camera.zoom

    def test_camera_world_screen_transform(self) -> None:
        """Verify consistency of world-to-screen and screen-to-world transforms."""
        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)

        # Screen center should map to world origin (center_x=0, center_y=0, zoom=1)
        wx, wy = camera.screen_to_world(640, 360)
        assert wx == pytest.approx(0.0, abs=1e-6)
        assert wy == pytest.approx(0.0, abs=1e-6)

        # World origin should map to screen center
        sx, sy = camera.world_to_screen(0.0, 0.0)
        assert sx == 640
        assert sy == 360

        # Re-verify after pan
        camera.pan(100.0, 50.0)
        wx2, wy2 = camera.screen_to_world(640, 360)
        assert wx2 != 0.0

        # round-trip verification
        sx2, sy2 = camera.world_to_screen(wx2, wy2)
        assert sx2 == 640
        assert sy2 == 360


class TestInputIntegration:
    """Input handler integration tests."""

    def test_mouse_click_selects_body(self, pygame_dummy) -> None:
        """Simulate mouse click at body position should return the body ID."""
        import pygame

        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)
        handler = InputHandler()
        bodies = create_default_scene()

        # Get screen position of body 1 (planet)
        planet_id = 1
        world_x = float(bodies[planet_id, X])
        world_y = float(bodies[planet_id, Y])
        screen_x, screen_y = camera.world_to_screen(world_x, world_y)

        # Simulate click
        cmd = handler.inject_mouse_click(screen_x, screen_y, button=1)
        assert cmd.startswith("CLICK:"), f"Expected CLICK command, got: {cmd}"

        # Verify find_body_at_screen_pos finds the body
        found_id = handler.find_body_at_screen_pos(
            screen_x, screen_y, bodies, camera
        )
        assert found_id is not None, "Should find a body"
        assert found_id == planet_id, f"Expected planet ID={planet_id}, got {found_id}"

    def test_mouse_drag_pan_camera(self, pygame_dummy) -> None:
        """Simulate middle-button drag should change camera center."""
        import pygame

        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)
        handler = InputHandler()

        # Record initial center
        initial_center_x = camera.center_x
        initial_center_y = camera.center_y

        # Simulate middle-button drag of 100 pixels
        cmds = handler.inject_mouse_drag(400, 300, 500, 350, button=2)

        # Should produce middle-button pan command "PAN:dx,dy"
        pan_cmd = None
        for cmd in cmds:
            if cmd.startswith("PAN:"):
                pan_cmd = cmd
                break

        assert pan_cmd is not None, f"Expected PAN command, got: {cmds}"

        # Handle pan command
        handler.handle_camera_commands(cmds, camera, 1.0)

        # Verify camera center has changed
        assert camera.center_x != initial_center_x, "center_x should change after drag"
        assert camera.center_y != initial_center_y, "center_y should change after drag"

    def test_keyboard_shortcuts(self, pygame_dummy) -> None:
        """Simulate keyboard shortcuts should return the correct commands."""
        import pygame

        handler = InputHandler()

        # SPACE -> TOGGLE_PAUSE
        cmd = handler.inject_key_press("K_SPACE")
        assert cmd == "TOGGLE_PAUSE", f"K_SPACE should be TOGGLE_PAUSE, got: {cmd}"

        # ESCAPE -> MENU
        cmd = handler.inject_key_press("K_ESCAPE")
        assert cmd == "MENU", f"K_ESCAPE should be MENU, got: {cmd}"

        # G -> TOGGLE_GRID
        cmd = handler.inject_key_press("K_g")
        assert cmd == "TOGGLE_GRID", f"K_g should be TOGGLE_GRID, got: {cmd}"

        # L -> TOGGLE_LABELS
        cmd = handler.inject_key_press("K_l")
        assert cmd == "TOGGLE_LABELS", f"K_l should be TOGGLE_LABELS, got: {cmd}"

        # H -> TOGGLE_SHORTCUTS
        cmd = handler.inject_key_press("K_h")
        assert cmd == "TOGGLE_SHORTCUTS", f"K_h should be TOGGLE_SHORTCUTS, got: {cmd}"

        # 5 -> TIME_1X
        cmd = handler.inject_key_press("K_5")
        assert cmd == "TIME_1X", f"K_5 should be TIME_1X, got: {cmd}"

        # 6 -> FAST_2X
        cmd = handler.inject_key_press("K_6")
        assert cmd == "FAST_2X", f"K_6 should be FAST_2X, got: {cmd}"

        # 7 -> FAST_4X
        cmd = handler.inject_key_press("K_7")
        assert cmd == "FAST_4X", f"K_7 should be FAST_4X, got: {cmd}"

        # 8 -> FAST_8X
        cmd = handler.inject_key_press("K_8")
        assert cmd == "FAST_8X", f"K_8 should be FAST_8X, got: {cmd}"

        # DELETE -> DELETE_SELECTED
        cmd = handler.inject_key_press("K_DELETE")
        assert cmd == "DELETE_SELECTED", f"K_DELETE should be DELETE_SELECTED, got: {cmd}"

        # Old shortcuts R/F/T/0 have been removed -> None
        for removed_key in ("K_r", "K_t", "K_f", "K_0"):
            cmd = handler.inject_key_press(removed_key)
            assert cmd == "", f"{removed_key} should be empty, got: {cmd}"

    def test_get_mouse_pos(self, pygame_dummy) -> None:
        """Verify get_mouse_pos matches the injected mouse position."""
        import pygame

        handler = InputHandler()

        x, y = handler.get_mouse_pos()
        assert x == 0
        assert y == 0

        # Simulate click to update mouse position
        handler.inject_mouse_click(500, 300)
        x, y = handler.get_mouse_pos()
        assert x == 500
        assert y == 300


class TestTrailBufferIntegration:
    """Trail buffer integration tests."""

    def test_trail_buffer_records_positions(self) -> None:
        """Verify TrailBuffer correctly records positions, length and rewind."""
        buffer = TrailBuffer(maxlen=10)

        # Initial state: no trail
        trail = buffer.get_trail(0)
        assert trail == [], "Initial trail should be empty"

        # Simulate 5 frames of data
        for frame in range(5):
            buffer.push_frame(0, float(frame * 10.0), float(frame * 5.0))

        # Verify length
        trail = buffer.get_trail(0)
        assert len(trail) == 5, f"Trail length should be 5, got {len(trail)}"

        # Verify coordinate correctness
        assert trail[3] == (30.0, 15.0), f"Frame 4 coordinates wrong: {trail[3]}"

        # Verify rewind
        # rewind(0, frames=2): go back 2 frames from the latest
        # Latest (index 4) = (40, 20), rewind 2 frames = (20, 10)
        pos = buffer.rewind(0, frames=2)
        assert pos is not None, "rewind should return valid coordinates"
        assert pos[0] == pytest.approx(20.0)
        assert pos[1] == pytest.approx(10.0)

        # Should return None when history is insufficient
        pos = buffer.rewind(0, frames=10)
        assert pos is None, "Should return None when history is insufficient"

        # rewind(0) with latest frame = the last one
        pos = buffer.rewind(0, frames=0)
        assert pos is not None
        assert pos == (40.0, 20.0)

    def test_trail_buffer_clear(self) -> None:
        """Verify clearing trail operation."""
        buffer = TrailBuffer(maxlen=10)
        buffer.push_frame(0, 1.0, 2.0)
        buffer.push_frame(1, 3.0, 4.0)

        assert len(buffer) == 2

        # Clear single
        buffer.clear(0)
        assert buffer.get_trail(0) == []
        assert len(buffer) == 1

        # Clear all
        buffer.clear_all()
        assert len(buffer) == 0

    def test_trail_buffer_maxlen(self) -> None:
        """Verify trail buffer maximum length limit."""
        buffer = TrailBuffer(maxlen=5)
        for frame in range(10):
            buffer.push_frame(0, float(frame), float(frame))

        trail = buffer.get_trail(0)
        assert len(trail) == 5, f"Trail length should be 5 (maxlen), got {len(trail)}"
        # Should retain the last 5 frames: 5, 6, 7, 8, 9
        assert trail[0] == (5.0, 5.0), f"First frame should be (5,5), got {trail[0]}"
        assert trail[-1] == (9.0, 9.0), f"Last frame should be (9,9), got {trail[-1]}"

    def test_trail_push_all(self) -> None:
        """Verify push_all records trails for all active bodies simultaneously."""
        buffer = TrailBuffer(maxlen=10)
        bodies = create_default_scene()

        # push_all once
        buffer.push_all(bodies)

        # Verify each active body has a trail
        for i in range(bodies.shape[0]):
            trail = buffer.get_trail(i)
            assert len(trail) == 1, f"Body {i} should have 1 trail frame"
            assert trail[0][0] == pytest.approx(float(bodies[i, X]))
            assert trail[0][1] == pytest.approx(float(bodies[i, Y]))

        # push_all again
        buffer.push_all(bodies)
        for i in range(bodies.shape[0]):
            trail = buffer.get_trail(i)
            assert len(trail) == 2, f"Body {i} should have 2 trail frames"
