"""MiniSFS shared utility functions.

Reusable helpers extracted from across the project.
All functions are independent of game-specific logic.
"""

import math

import numpy as np

from src.core.types import IS_ACTIVE, IS_STATIC


# ============================================================================
# Angle / Math Utilities
# ============================================================================


def normalize_angle_delta(delta_angle: float) -> float:
    """Normalize an angle difference to the range [-pi, pi].

    Args:
        delta_angle: Raw angle difference in radians.

    Returns:
        Normalized angle difference in [-pi, pi].
    """
    while delta_angle > math.pi:
        delta_angle -= 2.0 * math.pi
    while delta_angle < -math.pi:
        delta_angle += 2.0 * math.pi
    return delta_angle


# ============================================================================
# Body State Queries
# ============================================================================


def is_body_active(bodies: np.ndarray, body_id: int) -> bool:
    """Check whether a body is active.

    Args:
        bodies: Body state array of shape (N, NUM_FIELDS).
        body_id: Index of the body to check.

    Returns:
        True if the body is active (IS_ACTIVE == 1.0).
    """
    return bool(bodies[body_id, IS_ACTIVE] == 1.0)


def is_body_static(bodies: np.ndarray, body_id: int) -> bool:
    """Check whether a body is static.

    Args:
        bodies: Body state array of shape (N, NUM_FIELDS).
        body_id: Index of the body to check.

    Returns:
        True if the body is static (IS_STATIC == 1.0).
    """
    return bool(bodies[body_id, IS_STATIC] == 1.0)


def filter_active_bodies(bodies: np.ndarray) -> np.ndarray:
    """Return a boolean mask for active bodies.

    Args:
        bodies: Body state array of shape (N, NUM_FIELDS).

    Returns:
        Boolean array of shape (N,) where True = active.
    """
    return bodies[:, IS_ACTIVE] == 1.0


# ============================================================================
# Scale / Rounding Utilities
# ============================================================================


def round_to_nice_number(raw: float) -> float:
    """Round a value to the nearest 'nice' number (1, 2, or 5 × power of 10).

    Used for scale bars, grid spacing, and similar UI elements.

    Args:
        raw: The raw value to round.

    Returns:
        The nearest nice number.
    """
    magnitude = 10.0 ** math.floor(math.log10(raw))
    normalized = raw / magnitude
    if normalized < 1.5:
        return 1.0 * magnitude
    elif normalized < 3.5:
        return 2.0 * magnitude
    elif normalized < 7.0:
        return 5.0 * magnitude
    else:
        return 10.0 * magnitude
