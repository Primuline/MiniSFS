"""Level 1 scene tests."""

import math

import numpy as np
import pytest

from src.config import (
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_STAR,
    DEFAULT_RADIUS_PROBE,
    GRAVITATIONAL_CONSTANT,
    PROBE_ROCKET_EXHAUST_VELOCITY_DEFAULT,
    PROBE_ROCKET_MASS_FLOW_RATE_DEFAULT,
    PROBE_ROCKET_TOTAL_MASS_DEFAULT,
    WORLD_SCALE,
)
from src.core.types import BODY_TYPE, IS_STATIC, MASS, RADIUS, VX, VY, X, Y, make_body
from src.main import (
    create_level_1_scene,
    create_level_2_scene,
    make_level_1_probe_rocket_state,
    make_level_probe_rocket_state,
    is_level_1_success,
    is_level_success,
    probe_radius_to_tool_pixels,
)
from src.physics.collision import handle_collisions


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


def test_level_1_probe_rocket_is_tuned_for_transfer() -> None:
    """Level 1 should use the requested boosted probe engine settings."""
    state = make_level_1_probe_rocket_state()

    assert state.exhaust_velocity == pytest.approx(
        PROBE_ROCKET_EXHAUST_VELOCITY_DEFAULT * 50.0
    )
    assert state.mass_flow_rate == pytest.approx(
        PROBE_ROCKET_MASS_FLOW_RATE_DEFAULT // 50.0
    )
    assert state.landing_speed_limit == pytest.approx(1000.0)


def test_level_2_contains_sun_earth_mars_and_probe() -> None:
    """Level 2 should load a simplified Earth-Mars transfer setup."""
    bodies = create_level_2_scene()

    assert bodies.shape == (4, 10)
    assert int(bodies[0, BODY_TYPE]) == BODY_TYPE_STAR
    assert int(bodies[1, BODY_TYPE]) == BODY_TYPE_PLANET
    assert int(bodies[2, BODY_TYPE]) == BODY_TYPE_PLANET
    assert int(bodies[3, BODY_TYPE]) == BODY_TYPE_PROBE
    assert bodies[0, IS_STATIC] == 1.0
    assert bodies[3, MASS] == pytest.approx(2500.0)
    assert bodies[3, RADIUS] == pytest.approx(DEFAULT_RADIUS_PROBE * WORLD_SCALE)


def test_level_2_uses_earth_mars_transfer_like_initial_speed() -> None:
    """Level 2 probe should start near Earth with a Hohmann-like injection speed."""
    bodies = create_level_2_scene()
    sun_mass = float(bodies[0, MASS])
    earth_radius = math.hypot(float(bodies[1, X]), float(bodies[1, Y]))
    mars_radius = math.hypot(float(bodies[2, X]), float(bodies[2, Y]))
    transfer_a = 0.5 * (earth_radius + mars_radius)
    expected_probe_speed = math.sqrt(
        GRAVITATIONAL_CONSTANT * sun_mass * (2.0 / earth_radius - 1.0 / transfer_a)
    )

    assert bodies[3, VX] == pytest.approx(0.0)
    assert bodies[3, VY] == pytest.approx(expected_probe_speed, rel=2e-3)
    assert mars_radius > earth_radius


def test_level_2_probe_starts_clear_of_failure_inputs() -> None:
    """Level 2 should not start overlapped, disappeared, or already successful."""
    bodies = create_level_2_scene()
    probe_id = 3
    earth_id = 1
    earth_probe_distance = math.hypot(
        float(bodies[probe_id, X] - bodies[earth_id, X]),
        float(bodies[probe_id, Y] - bodies[earth_id, Y]),
    )
    contact_distance = float(bodies[earth_id, RADIUS] + bodies[probe_id, RADIUS])

    assert earth_probe_distance > contact_distance
    assert is_level_success(bodies) is False

    resolved, events = handle_collisions(
        bodies.copy(),
        probe_landing_speed_limits={probe_id: 1000.0},
    )

    assert events == []
    assert int(resolved[probe_id, BODY_TYPE]) == BODY_TYPE_PROBE


def test_level_probe_rocket_parameters_are_level_specific() -> None:
    """Fixed levels should use their requested engine and landing settings."""
    level_1 = make_level_probe_rocket_state(1)
    level_2 = make_level_probe_rocket_state(2)

    assert level_1.landing_speed_limit == pytest.approx(1000.0)
    assert level_2.total_mass() == pytest.approx(2500.0)
    assert level_2.dry_mass == pytest.approx(1500.0)
    assert level_2.fuel_mass == pytest.approx(1000.0)
    assert level_2.initial_fuel_mass == pytest.approx(1000.0)
    assert level_2.exhaust_velocity == pytest.approx(300000.0)
    assert level_2.mass_flow_rate == pytest.approx(1.0e-6)
    assert level_2.landing_speed_limit == pytest.approx(1000.0)


def test_level_1_success_requires_probe_landed_on_planet() -> None:
    """Landing on the planet body should clear Level 1."""
    planet = make_body(
        x=0.0,
        y=0.0,
        mass=1.0e24,
        radius=10.0,
        body_type=BODY_TYPE_PLANET,
    )
    probe = make_body(
        x=15.0,
        y=0.0,
        vx=0.0,
        vy=0.0,
        mass=1.0,
        radius=5.0,
        body_type=BODY_TYPE_PROBE,
    )

    assert is_level_1_success(np.vstack([planet, probe])) is True
