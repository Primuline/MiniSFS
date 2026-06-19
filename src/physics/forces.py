"""Celestial force calculation module.

Provides vectorized (O(n^2)) computation of Newtonian gravitational and Coulomb forces.
Can be combined with Barnes-Hut acceleration using a quadtree for O(n log n) approximate computation in the future.

Also provides a single-star trajectory prediction function for trajectory preview when setting placement velocity.

Usage::

    from src.physics.forces import compute_gravitational_forces, compute_coulomb_forces

    # Compute the net gravitational force on all active bodies
    grav_forces = compute_gravitational_forces(bodies, G, softening)
    # Compute the net Coulomb force
    coul_forces = compute_coulomb_forces(bodies, K, softening)
    # Combine
    total_forces = grav_forces + coul_forces
"""

import math
from typing import Dict, Optional, Tuple

import numpy as np

from src.config import ESCAPE_RATIO, MAX_TRAJECTORY_STEPS
from src.core.utils.tools import normalize_angle_delta
from src.core.types import (
    BODY_TYPE,
    BODY_TYPE_STAR,
    CHARGE,
    IS_ACTIVE,
    IS_STATIC,
    MASS,
    RADIUS,
    X,
    Y,
)


def compute_gravitational_forces(
    bodies: np.ndarray,
    g: float,
    softening: float,
) -> np.ndarray:
    """Compute the total gravitational force on all bodies.

    Uses vectorized O(n^2) full computation. Returns a force array of shape (N, 2).
    Static bodies experience no force (their acceleration is not computed), but do exert gravity on other bodies.
    Inactive bodies neither exert gravity nor experience force.

    Args:
        bodies: body state array of shape (N, NUM_FIELDS)
        g: gravitational constant (e.g., 6.67430e-11)
        softening: softening parameter (m), prevents force divergence as r -> 0

    Returns:
        net force array (fx, fy) of shape (N, 2), unit N
    """
    n = bodies.shape[0]
    forces = np.zeros((n, 2), dtype=np.float64)

    if n < 2:
        return forces

    # Extract positions and masses
    positions = bodies[:, [X, Y]]       # shape (N, 2)
    masses = bodies[:, MASS]            # shape (N,)
    is_active = bodies[:, IS_ACTIVE] == 1.0
    is_static = bodies[:, IS_STATIC] == 1.0

    # Inactive bodies do not produce gravity (mass treated as 0)
    effective_masses = masses.copy()
    effective_masses[~is_active] = 0.0

    # Compute displacement vectors for all pairs: positions[i] - positions[j]
    # Using broadcasting: (N,1,2) - (1,N,2) -> (N,N,2)
    delta = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]  # (N, N, 2)

    # Squared distance + softening^2 (avoid division by zero)
    r_squared = np.sum(delta ** 2, axis=-1) + softening ** 2          # (N, N)
    # Prevent zero on diagonal (self-interaction) even when softening=0,
    # which would otherwise produce inf*0=NaN and pollute all force vectors.
    np.fill_diagonal(r_squared, max(softening ** 2, 1e-30))
    r = np.sqrt(r_squared)                                             # (N, N)

    # Force magnitude: F = G * m_i * m_j / r^2
    # Note: F_ij = G * m_i * m_j / r^2, direction from j to i
    force_magnitude = g * effective_masses[np.newaxis, :] * effective_masses[:, np.newaxis] / r_squared  # (N, N)

    # Force vector: -(F_mag / r) * delta (negative sign makes direction from i to j, i.e., gravitational attraction)
    # delta[i,j] = pos_i - pos_j points from j to i, but gravity needs direction from i to j
    # shape (N, N, 2): each component of delta multiplied by -force_magnitude / r
    inv_r = np.where(r > 0, 1.0 / r, 0.0)
    force_vectors = -delta * (force_magnitude * inv_r)[:, :, np.newaxis]  # (N, N, 2)

    # Sum over j to get the net force on each body i
    forces[:, :] = np.sum(force_vectors, axis=1)  # (N, 2)

    # Static and inactive bodies experience no force
    no_force_mask = ~is_active | is_static
    forces[no_force_mask] = 0.0

    return forces


def compute_coulomb_forces(
    bodies: np.ndarray,
    k: float,
    softening: float,
) -> np.ndarray:
    """Compute the total Coulomb force on all bodies.

    Uses vectorized O(n^2) full computation. Returns a force array of shape (N, 2).
    Opposite charges attract, like charges repel.
    Static bodies experience no force but exert Coulomb force on other bodies.
    Inactive bodies neither exert Coulomb force nor experience force.

    Args:
        bodies: body state array of shape (N, NUM_FIELDS)
        k: Coulomb constant (e.g., 8.98755e9)
        softening: softening parameter (m)

    Returns:
        net force array (fx, fy) of shape (N, 2), unit N
    """
    n = bodies.shape[0]
    forces = np.zeros((n, 2), dtype=np.float64)

    if n < 2:
        return forces

    positions = bodies[:, [X, Y]]       # shape (N, 2)
    charges = bodies[:, CHARGE]         # shape (N,)
    is_active = bodies[:, IS_ACTIVE] == 1.0
    is_static = bodies[:, IS_STATIC] == 1.0

    # Charge of inactive bodies is treated as 0
    effective_charges = charges.copy()
    effective_charges[~is_active] = 0.0

    delta = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]  # (N, N, 2)
    r_squared = np.sum(delta ** 2, axis=-1) + softening ** 2          # (N, N)
    # Prevent zero on diagonal (self-interaction) even when softening=0
    np.fill_diagonal(r_squared, max(softening ** 2, 1e-30))
    r = np.sqrt(r_squared)                                             # (N, N)

    # Coulomb force: F = k * q_i * q_j / r^2 (positive = repulsion, negative = attraction)
    force_magnitude = k * effective_charges[np.newaxis, :] * effective_charges[:, np.newaxis] / r_squared  # (N, N)

    inv_r = np.where(r > 0, 1.0 / r, 0.0)
    force_vectors = delta * (force_magnitude * inv_r)[:, :, np.newaxis]  # (N, N, 2)

    forces[:, :] = np.sum(force_vectors, axis=1)  # (N, 2)

    # Static and inactive bodies experience no force
    no_force_mask = ~is_active | is_static
    forces[no_force_mask] = 0.0

    return forces


def compute_total_forces(
    bodies: np.ndarray,
    g: float,
    k: float,
    softening: float,
) -> np.ndarray:
    """Compute the total net force on all bodies (gravity + Coulomb).

    Args:
        bodies: body state array of shape (N, NUM_FIELDS)
        g: gravitational constant
        k: Coulomb constant
        softening: softening parameter (m)

    Returns:
        net force array (fx, fy) of shape (N, 2)
    """
    grav = compute_gravitational_forces(bodies, g, softening)
    coul = compute_coulomb_forces(bodies, k, softening)
    return grav + coul


# ============================================================================
# Trajectory preview functions
# ============================================================================


def find_nearest_star(
    pos: np.ndarray,
    bodies: np.ndarray,
) -> Optional[Tuple[int, np.ndarray, float, float]]:
    """Find the nearest active star to a given position among bodies.

    Args:
        pos: query coordinates of shape (2,) (m)
        bodies: body state array of shape (N, NUM_FIELDS)

    Returns:
        Tuple of (index, star_pos, star_mass, star_radius), returns None if no star is found.

        - index: row index of the star in bodies
        - star_pos: star position array of shape (2,) (m)
        - star_mass: star mass (kg)
        - star_radius: star radius (m)
    """
    best_idx: Optional[int] = None
    best_dist_sq: float = float("inf")

    for i in range(bodies.shape[0]):
        if int(bodies[i, BODY_TYPE]) != 0:  # BODY_TYPE_STAR == 0
            continue
        if bodies[i, IS_ACTIVE] == 0.0:
            continue
        dx = float(bodies[i, X] - pos[0])
        dy = float(bodies[i, Y] - pos[1])
        dist_sq = dx * dx + dy * dy
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_idx = i

    if best_idx is None:
        return None

    idx = best_idx
    star_pos = bodies[idx, [X, Y]].copy()  # shape (2,)
    star_mass = float(bodies[idx, MASS])
    star_radius = float(bodies[idx, RADIUS])
    return (idx, star_pos, star_mass, star_radius)


def find_dominant_placement_gravity_source(
    pos: np.ndarray,
    bodies: np.ndarray,
    *,
    exclude_body_id: Optional[int] = None,
) -> Optional[Tuple[int, np.ndarray, float, float]]:
    """Find a dominant static star source for placement trajectory preview.

    Outside an explicit reference frame, placement preview is shown only when
    one static star dominates the local gravitational field clearly enough.
    """
    strengths: list[Tuple[float, int]] = []

    for i in range(bodies.shape[0]):
        if exclude_body_id is not None and i == exclude_body_id:
            continue
        if bodies[i, IS_ACTIVE] == 0.0:
            continue
        if float(bodies[i, MASS]) <= 0.0:
            continue
        dx = float(bodies[i, X] - pos[0])
        dy = float(bodies[i, Y] - pos[1])
        dist_sq = dx * dx + dy * dy
        if dist_sq < 1.0:
            strength = float("inf")
        else:
            strength = float(bodies[i, MASS]) / dist_sq
        strengths.append((strength, i))

    if not strengths:
        return None

    strengths.sort(reverse=True)
    strongest, idx = strengths[0]
    if (
        int(bodies[idx, BODY_TYPE]) != BODY_TYPE_STAR
        or int(bodies[idx, IS_STATIC]) != 1
    ):
        return None

    if len(strengths) > 1:
        second_strongest = strengths[1][0]
        if strongest <= second_strongest * 10.0:
            return None

    source_pos = bodies[idx, [X, Y]].copy()
    source_mass = float(bodies[idx, MASS])
    source_radius = float(bodies[idx, RADIUS])
    return (idx, source_pos, source_mass, source_radius)


def predict_single_star_trajectory(
    pos: np.ndarray,
    vel: np.ndarray,
    star_pos: np.ndarray,
    star_mass: float,
    star_radius: float,
    body_radius: float,
    g: float,
    softening: float,
    steps: int = 2000,
    dt: float = 5000.0,
) -> Dict[str, object]:
    """Predict the trajectory of a single body under a single gravitational source.

    Uses Euler numerical integration to compute the two-body problem trajectory.
    The gravitational source is treated as fixed; only the force on the body being placed is computed.
    Termination conditions (priority order): collision > escape > orbit completed > max steps.

    Args:
        pos: world coordinates of the preview position of shape (2,) (m)
        vel: set velocity vector of shape (2,) (m/s)
        star_pos: source position of shape (2,) (m)
        star_mass: source mass (kg)
        star_radius: source radius (m)
        body_radius: radius of the body being placed (m)
        g: gravitational constant
        softening: softening parameter (m)
        steps: maximum number of integration steps (safety limit)
        dt: time step interval (seconds)

    Returns:
        Dictionary containing the following keys:
            - "trajectory": trajectory world coordinate array of shape (N, 2) (raw density)
            - "collided": whether collided with the star
            - "escaped": whether escaped
            - "orbited": whether completed one orbit around the source
    """
    pos_cur = pos.copy().astype(np.float64)
    vel_cur = vel.copy().astype(np.float64)
    star_pos_f64 = star_pos.astype(np.float64)

    # Initial distance for escape detection
    initial_delta = pos_cur - star_pos_f64
    initial_dist = float(np.linalg.norm(initial_delta))
    escape_threshold: float = ESCAPE_RATIO * max(initial_dist, 1.0)
    collision_radius: float = star_radius + body_radius

    trajectory: list = [pos_cur.copy()]
    collided: bool = False
    escaped: bool = False
    orbited: bool = False

    # Angle accumulation tracking
    total_angle: float = 0.0
    prev_angle: float = math.atan2(
        pos_cur[1] - star_pos_f64[1],
        pos_cur[0] - star_pos_f64[0],
    )

    max_steps = min(steps, MAX_TRAJECTORY_STEPS)

    for _ in range(max_steps):
        r_vec = pos_cur - star_pos_f64
        dist = float(np.linalg.norm(r_vec)) + softening

        # 1. Collision detection (highest priority)
        if dist < collision_radius:
            collided = True
            # Fallback interpolation to star surface: interpolate from last known safe position toward surface
            if len(trajectory) >= 2:
                last_safe = trajectory[-1]
                r_safe = last_safe - star_pos_f64
                d_safe = float(np.linalg.norm(r_safe))
                cur_raw = dist - softening  # remove softening
                if d_safe > cur_raw:
                    # Linearly interpolate between safe position and penetrated position to collision radius
                    t = (d_safe - collision_radius) / (d_safe - cur_raw)
                    t = max(0.0, min(t, 1.0))
                    hit_pt = last_safe + (pos_cur - last_safe) * t
                    trajectory.append(hit_pt)
                    trajectory.append(surface_pt)
            else:
                trajectory.append(pos_cur.copy())
            break

        # 2. Escape detection
        if dist > escape_threshold:
            escaped = True
            trajectory.append(pos_cur.copy())
            break

        # 3. Angle change detection
        current_angle = math.atan2(r_vec[1], r_vec[0])
        delta_angle = current_angle - prev_angle
        # Normalize to [-pi, pi]
        delta_angle = normalize_angle_delta(delta_angle)
        total_angle += abs(delta_angle)
        prev_angle = current_angle

        # Completed one orbit
        if total_angle >= 2.0 * math.pi:
            orbited = True
            trajectory.append(pos_cur.copy())
            break

        # 4. Integrate one step (Euler method)
        acc = -g * star_mass * r_vec / (dist ** 3)
        vel_cur += acc * dt
        pos_cur += vel_cur * dt
        trajectory.append(pos_cur.copy())

    return {
        "trajectory": np.array(trajectory, dtype=np.float64),
        "collided": collided,
        "escaped": escaped,
        "orbited": orbited,
    }
