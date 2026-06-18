"""Rocket thrust calculation tests."""

import numpy as np
import pytest

from src.physics.rocket import (
    ProbeRocketState,
    compute_rocket_burn,
    normalize_direction,
)


def test_compute_rocket_burn_consumes_fuel_and_returns_delta_v() -> None:
    """A burn step should consume fuel and accelerate along the thrust direction."""
    result = compute_rocket_burn(
        current_mass=100.0,
        fuel_mass=40.0,
        dry_mass=60.0,
        exhaust_velocity=3000.0,
        mass_flow_rate=2.0,
        direction=[1.0, 0.0],
        dt=5.0,
    )

    assert result.fuel_used == pytest.approx(10.0)
    assert result.remaining_fuel_mass == pytest.approx(30.0)
    assert result.new_mass == pytest.approx(90.0)
    assert result.burn_time == pytest.approx(5.0)
    np.testing.assert_allclose(result.delta_v, np.array([300.0, 0.0]))


def test_no_fuel_returns_zero_delta_v() -> None:
    """A dry rocket should not accelerate or consume fuel."""
    result = compute_rocket_burn(
        current_mass=60.0,
        fuel_mass=0.0,
        dry_mass=60.0,
        exhaust_velocity=3000.0,
        mass_flow_rate=2.0,
        direction=[0.0, 1.0],
        dt=5.0,
    )

    assert result.fuel_used == 0.0
    assert result.remaining_fuel_mass == 0.0
    assert result.new_mass == pytest.approx(60.0)
    assert result.burn_time == 0.0
    np.testing.assert_allclose(result.delta_v, np.zeros(2))


@pytest.mark.parametrize(
    ("current_mass", "fuel_mass", "dry_mass"),
    [
        (0.0, 1.0, 1.0),
        (10.0, -1.0, 9.0),
        (10.0, 1.0, 0.0),
        (9.0, 1.0, 10.0),
        (10.0, 5.0, 8.0),
    ],
)
def test_invalid_masses_raise_value_error(
    current_mass: float,
    fuel_mass: float,
    dry_mass: float,
) -> None:
    """Masses must be positive, finite, and internally consistent."""
    with pytest.raises(ValueError):
        compute_rocket_burn(
            current_mass=current_mass,
            fuel_mass=fuel_mass,
            dry_mass=dry_mass,
            exhaust_velocity=3000.0,
            mass_flow_rate=2.0,
            direction=[1.0, 0.0],
            dt=1.0,
        )


def test_diagonal_direction_is_normalized() -> None:
    """Diagonal thrust input should keep total delta-v magnitude unchanged."""
    result = compute_rocket_burn(
        current_mass=100.0,
        fuel_mass=40.0,
        dry_mass=60.0,
        exhaust_velocity=3000.0,
        mass_flow_rate=2.0,
        direction=[1.0, 1.0],
        dt=5.0,
    )

    expected_component = 300.0 / np.sqrt(2.0)
    np.testing.assert_allclose(
        result.delta_v,
        np.array([expected_component, expected_component]),
    )


def test_short_burn_when_fuel_is_insufficient() -> None:
    """Fuel shortage should shorten burn duration and clamp fuel consumption."""
    result = compute_rocket_burn(
        current_mass=65.0,
        fuel_mass=5.0,
        dry_mass=60.0,
        exhaust_velocity=3000.0,
        mass_flow_rate=2.0,
        direction=[0.0, -1.0],
        dt=10.0,
    )

    assert result.fuel_used == pytest.approx(5.0)
    assert result.remaining_fuel_mass == pytest.approx(0.0)
    assert result.new_mass == pytest.approx(60.0)
    assert result.burn_time == pytest.approx(2.5)
    np.testing.assert_allclose(result.delta_v, np.array([0.0, -3000.0 * 5.0 / 65.0]))


def test_zero_direction_returns_zero_delta_v_without_fuel_use() -> None:
    """No requested direction should leave velocity and fuel unchanged."""
    result = compute_rocket_burn(
        current_mass=100.0,
        fuel_mass=40.0,
        dry_mass=60.0,
        exhaust_velocity=3000.0,
        mass_flow_rate=2.0,
        direction=[0.0, 0.0],
        dt=5.0,
    )

    assert result.fuel_used == 0.0
    assert result.remaining_fuel_mass == pytest.approx(40.0)
    assert result.new_mass == pytest.approx(100.0)
    np.testing.assert_allclose(result.delta_v, np.zeros(2))


def test_normalize_direction_rejects_non_2d_vectors() -> None:
    """Direction input must be exactly two-dimensional."""
    with pytest.raises(ValueError):
        normalize_direction([1.0, 0.0, 0.0])


def test_probe_rocket_state_current_mass() -> None:
    """ProbeRocketState should expose dry mass plus fuel as current mass."""
    state = ProbeRocketState(
        dry_mass=60.0,
        fuel_mass=40.0,
        exhaust_velocity=3000.0,
        mass_flow_rate=2.0,
    )

    assert state.current_mass == pytest.approx(100.0)
