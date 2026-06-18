"""Level 1 scene tests."""

import math

import pytest

from src.config import (
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_STAR,
    DEFAULT_RADIUS_PROBE,
    GRAVITATIONAL_CONSTANT,
    PROBE_ROCKET_TOTAL_MASS_DEFAULT,
    WORLD_SCALE,
)
from src.core.types import BODY_TYPE, IS_STATIC, MASS, RADIUS, VX, VY, X, Y
from src.main import create_level_1_scene, probe_radius_to_tool_pixels


def test_level_1_contains_earth_moon_and_probe() -> None:
    """Level 1 should load a fixed Earth-Moon setup with a default probe."""
    bodies = create_level_1_scene()

    assert bodies.shape == (3, 10)
    assert int(bodies[0, BODY_TYPE]) == BODY_TYPE_STAR
    assert int(bodies[1, BODY_TYPE]) == BODY_TYPE_PLANET
    assert int(bodies[2, BODY_TYPE]) == BODY_TYPE_PROBE
    assert bodies[0, IS_STATIC] == 1.0
    assert bodies[2, MASS] == pytest.approx(PROBE_ROCKET_TOTAL_MASS_DEFAULT)
    assert bodies[2, RADIUS] == pytest.approx(DEFAULT_RADIUS_PROBE * WORLD_SCALE)


def test_level_1_moon_uses_circular_orbit_speed() -> None:
    """The moon should start at circular-orbit speed around static Earth."""
    bodies = create_level_1_scene()
    orbit_radius = float(bodies[1, X] - bodies[0, X])
    expected_speed = math.sqrt(
        GRAVITATIONAL_CONSTANT * float(bodies[0, MASS]) / orbit_radius
    )

    assert bodies[1, Y] == pytest.approx(0.0)
    assert bodies[1, VX] == pytest.approx(0.0)
    assert bodies[1, VY] == pytest.approx(expected_speed)


def test_level_1_probe_starts_on_earth_surface_clear_of_collision() -> None:
    """The default probe should be placed on Earth with a tiny clearance."""
    bodies = create_level_1_scene()
    earth_radius = float(bodies[0, RADIUS])
    probe_radius = float(bodies[2, RADIUS])
    probe_distance = math.hypot(float(bodies[2, X]), float(bodies[2, Y]))

    assert probe_distance == pytest.approx(earth_radius + probe_radius + 1.0)


def test_probe_radius_tool_conversion_preserves_small_probe_radius() -> None:
    """Probe placement should not clamp sub-pixel radii to one world-scale pixel."""
    radius_meters = 100.0
    radius_pixels = probe_radius_to_tool_pixels(radius_meters)

    assert radius_pixels * WORLD_SCALE == pytest.approx(radius_meters)
