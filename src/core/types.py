"""MiniSFS core data type definitions.

Defines the shared body state array (BodyState) format used by all modules.
The array is an ``np.ndarray`` of shape ``(N, NUM_FIELDS)`` and dtype ``np.float64``.

Column indices are defined by the ``BodyField`` named tuple and accessed
by name rather than hardcoded numbers.
"""

from typing import NamedTuple, Tuple

import numpy as np

# ============================================================================
# BodyState array field index definitions
# ============================================================================


class BodyField(NamedTuple):
    """Mapping of column names to indices in the BodyState NumPy array.

    Usage::

        bodies[0, BodyField.X]        # x coordinate of first body
        bodies[:, BodyField.VX:BodyField.VY+1]  # velocity vectors of all bodies
    """

    # --- Position ---
    X: int = 0      # x coordinate (m)
    Y: int = 1      # y coordinate (m)

    # --- Velocity ---
    VX: int = 2     # x velocity (m/s)
    VY: int = 3     # y velocity (m/s)

    # --- Physical Properties ---
    MASS: int = 4       # mass (kg)
    CHARGE: int = 5     # charge (C)
    RADIUS: int = 6     # radius (m)

    # --- Metadata ---
    BODY_TYPE: int = 7   # body type (0=star, 1=planet, 2=probe, 3=charged)
    IS_STATIC: int = 8   # static flag (0=dynamic, 1=static; static bodies skip physics)
    IS_ACTIVE: int = 9   # active flag (0=inactive, 1=alive)


# Total number of fields in the body state array
NUM_FIELDS: int = 10

# Singleton for fast access (module-level constants avoid re-instantiation)
_FIELD = BodyField()

# Convenience imports
X: int = _FIELD.X
Y: int = _FIELD.Y
VX: int = _FIELD.VX
VY: int = _FIELD.VY
MASS: int = _FIELD.MASS
CHARGE: int = _FIELD.CHARGE
RADIUS: int = _FIELD.RADIUS
BODY_TYPE: int = _FIELD.BODY_TYPE
IS_STATIC: int = _FIELD.IS_STATIC
IS_ACTIVE: int = _FIELD.IS_ACTIVE


# ============================================================================
# Body type enums (must stay in sync with config.py)
# ============================================================================

# int constants are used instead of Enum for NumPy array compatibility
BODY_TYPE_STAR: int = 0      # star — massive, luminous
BODY_TYPE_PLANET: int = 1    # planet — ordinary body (no charge)
BODY_TYPE_PROBE: int = 2     # probe — player-controlled
BODY_TYPE_CHARGED: int = 3   # charged particle — affected by Coulomb force


# ============================================================================
# Type aliases
# ============================================================================

# World coordinate (x, y) in meters
WorldPoint = Tuple[float, float]

# Screen coordinate (x, y) in pixels
ScreenPoint = Tuple[int, int]

# Velocity vector (vx, vy) in m/s
Velocity = Tuple[float, float]

# Force vector (fx, fy) in Newtons
Force = Tuple[float, float]


# ============================================================================
# Factory functions
# ============================================================================


def create_body_state_array(n: int) -> np.ndarray:
    """Create a body state array with N rows and NUM_FIELDS columns, zero-initialized.

    Args:
        n: Number of bodies.

    Returns:
        float64 array of shape (n, NUM_FIELDS) with all bodies active and dynamic.
    """
    bodies = np.zeros((n, NUM_FIELDS), dtype=np.float64)
    bodies[:, IS_ACTIVE] = 1.0   # default: alive
    bodies[:, IS_STATIC] = 0.0   # default: dynamic
    return bodies


def make_body(
    x: float = 0.0,
    y: float = 0.0,
    vx: float = 0.0,
    vy: float = 0.0,
    mass: float = 1.0e28,
    charge: float = 0.0,
    radius: float = 8.0,
    body_type: int = BODY_TYPE_PLANET,
    is_static: bool = False,
    is_active: bool = True,
) -> np.ndarray:
    """Create a single-body state array of shape (1, NUM_FIELDS).

    Args:
        x, y: Initial position (m).
        vx, vy: Initial velocity (m/s).
        mass: Mass (kg).
        charge: Charge (C).
        radius: Radius (m).
        body_type: Body type index.
        is_static: Whether the body is static.
        is_active: Whether the body is alive.

    Returns:
        float64 array of shape (1, NUM_FIELDS).
    """
    body = np.zeros((1, NUM_FIELDS), dtype=np.float64)
    body[0, X] = x
    body[0, Y] = y
    body[0, VX] = vx
    body[0, VY] = vy
    body[0, MASS] = mass
    body[0, CHARGE] = charge
    body[0, RADIUS] = radius
    body[0, BODY_TYPE] = float(body_type)
    body[0, IS_STATIC] = 1.0 if is_static else 0.0
    body[0, IS_ACTIVE] = 1.0 if is_active else 0.0
    return body
