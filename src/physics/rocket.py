"""Pure rocket thrust calculations for probe control.

This module intentionally has no Pygame dependency. It computes fuel burn and
velocity delta for a single thrust step so UI/input code can call it without
duplicating physics formulas.
"""

from dataclasses import dataclass
from typing import Sequence

import numpy as np


MASS_TOLERANCE = 1.0e-9


@dataclass(frozen=True)
class RocketBurnResult:
    """Result of one rocket burn step.

    Attributes:
        delta_v: Velocity change vector in m/s.
        fuel_used: Fuel mass consumed during this step in kg.
        remaining_fuel_mass: Fuel mass left after the burn in kg.
        new_mass: New total rocket mass in kg.
        burn_time: Actual burn duration in seconds. This can be shorter than
            the requested ``dt`` when fuel runs out mid-step.
    """

    delta_v: np.ndarray
    fuel_used: float
    remaining_fuel_mass: float
    new_mass: float
    burn_time: float


@dataclass(frozen=True)
class ProbeRocketState:
    """Sidecar state for a probe rocket.

    Attributes:
        dry_mass: Probe mass without fuel in kg.
        fuel_mass: Current fuel mass in kg.
        exhaust_velocity: Effective exhaust velocity in m/s.
        mass_flow_rate: Fuel consumption rate in kg/s.
    """

    dry_mass: float
    fuel_mass: float
    exhaust_velocity: float
    mass_flow_rate: float

    @property
    def current_mass(self) -> float:
        """Return total rocket mass in kg."""
        return self.dry_mass + self.fuel_mass


def normalize_direction(direction: Sequence[float] | np.ndarray) -> np.ndarray:
    """Return a unit 2D direction vector.

    Args:
        direction: 2D vector where non-zero length requests thrust direction.

    Returns:
        Unit direction as a ``np.float64`` array. A zero vector remains zero.

    Raises:
        ValueError: If direction is not a finite 2D vector.
    """
    vector = np.asarray(direction, dtype=np.float64)
    if vector.shape != (2,):
        raise ValueError("direction must be a 2D vector")
    if not np.all(np.isfinite(vector)):
        raise ValueError("direction must contain finite values")

    magnitude = float(np.linalg.norm(vector))
    if magnitude == 0.0:
        return np.zeros(2, dtype=np.float64)
    return vector / magnitude


def compute_rocket_burn(
    current_mass: float,
    fuel_mass: float,
    dry_mass: float,
    exhaust_velocity: float,
    mass_flow_rate: float,
    direction: Sequence[float] | np.ndarray,
    dt: float,
) -> RocketBurnResult:
    """Compute velocity delta and fuel state for one probe rocket burn.

    The first version uses the small-step momentum approximation:
    ``delta_v = direction * exhaust_velocity * fuel_used / current_mass``.
    Fuel shortage shortens the burn time, so the returned ``burn_time`` can be
    less than ``dt``.

    Args:
        current_mass: Current total rocket mass in kg.
        fuel_mass: Current fuel mass in kg.
        dry_mass: Rocket mass without fuel in kg.
        exhaust_velocity: Effective exhaust velocity in m/s.
        mass_flow_rate: Fuel consumption rate in kg/s.
        direction: Desired thrust direction. Diagonal input is normalized.
        dt: Requested burn duration in seconds.

    Returns:
        Rocket burn result containing delta-v, fuel used, remaining fuel, new
        total mass, and actual burn duration.

    Raises:
        ValueError: If masses, engine parameters, direction, or dt are invalid.
    """
    _validate_mass_inputs(current_mass, fuel_mass, dry_mass)
    unit_direction = normalize_direction(direction)
    _validate_non_negative_finite("dt", dt)

    if dt == 0.0 or fuel_mass == 0.0 or np.array_equal(unit_direction, np.zeros(2)):
        return RocketBurnResult(
            delta_v=np.zeros(2, dtype=np.float64),
            fuel_used=0.0,
            remaining_fuel_mass=fuel_mass,
            new_mass=dry_mass + fuel_mass,
            burn_time=0.0,
        )

    _validate_positive_finite("exhaust_velocity", exhaust_velocity)
    _validate_positive_finite("mass_flow_rate", mass_flow_rate)

    requested_fuel = mass_flow_rate * dt
    fuel_used = min(fuel_mass, requested_fuel)
    burn_time = fuel_used / mass_flow_rate
    delta_v_magnitude = exhaust_velocity * fuel_used / current_mass
    remaining_fuel = fuel_mass - fuel_used

    return RocketBurnResult(
        delta_v=unit_direction * delta_v_magnitude,
        fuel_used=fuel_used,
        remaining_fuel_mass=remaining_fuel,
        new_mass=dry_mass + remaining_fuel,
        burn_time=burn_time,
    )


def _validate_mass_inputs(current_mass: float, fuel_mass: float, dry_mass: float) -> None:
    """Validate rocket mass parameters."""
    _validate_positive_finite("current_mass", current_mass)
    _validate_positive_finite("dry_mass", dry_mass)
    _validate_non_negative_finite("fuel_mass", fuel_mass)

    if current_mass + MASS_TOLERANCE < dry_mass:
        raise ValueError("current_mass must be greater than or equal to dry_mass")
    if fuel_mass - MASS_TOLERANCE > current_mass - dry_mass:
        raise ValueError("fuel_mass cannot exceed current_mass - dry_mass")


def _validate_positive_finite(name: str, value: float) -> None:
    """Validate that a scalar is finite and positive."""
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")


def _validate_non_negative_finite(name: str, value: float) -> None:
    """Validate that a scalar is finite and non-negative."""
    if not np.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
