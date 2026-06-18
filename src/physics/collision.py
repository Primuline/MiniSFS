"""Collision detection and response module.

Supports three collision handling strategies:
    - Star vs Planet: Star absorbs the planet (mass and charge sum)
    - Planet vs Planet: Merge into a new body (center-of-mass position, momentum conservation)
    - Probe vs any body: Probe lands on the surface

Collision events are returned to the caller for the renderer to produce effects (flashes, fragmentation).

Usage::

    from src.physics.collision import detect_collisions, handle_collisions
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from src.config import BODY_TYPE_PLANET, BODY_TYPE_PROBE, BODY_TYPE_STAR
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
)

# Collision event description
# Format: {"type": "elastic"|"merge", "id_a": int, "id_b": int,
#        "pos_x": float, "pos_y": float, "vx_a": float, "vy_a": float, ...}
CollisionEvent = Dict[str, float | int | str]


def detect_collisions(
    bodies: np.ndarray,
    candidates: Optional[List[Tuple[int, int]]] = None,
) -> List[Tuple[int, int]]:
    """Detect all collision pairs.

    If candidates (broadphase candidate pairs) are provided, only those
    candidate pairs are checked; otherwise, an O(n^2) full traversal is
    performed (fallback path).

    Args:
        bodies: body state array of shape (N, NUM_FIELDS)
        candidates: list of candidate pairs from quadtree broadphase, optional

    Returns:
        List of actual collision pairs, each as (id_a, id_b), where id_a < id_b to avoid duplicates
    """
    n = bodies.shape[0]
    collisions: List[Tuple[int, int]] = []

    if n < 2:
        return collisions

    positions = bodies[:, [X, Y]]
    radii = bodies[:, RADIUS]
    active = bodies[:, IS_ACTIVE] == 1.0
    static = bodies[:, IS_STATIC] == 1.0

    # Only consider active bodies
    active_indices = np.where(active)[0]
    if len(active_indices) < 2:
        return collisions

    if candidates is not None:
        # Broadphase path: only check candidate pairs
        for i, j in candidates:
            # Skip inactive bodies
            if bodies[i, IS_ACTIVE] == 0.0 or bodies[j, IS_ACTIVE] == 0.0:
                continue
            # Skip if both are static
            if static[i] and static[j]:
                continue
            delta = positions[i] - positions[j]
            dist = np.sqrt(np.dot(delta, delta))
            min_dist = radii[i] + radii[j]
            if dist < min_dist:
                collisions.append((i, j))
    else:
        # Fallback path: O(n²) full traversal
        for i_idx, i in enumerate(active_indices):
            for j in active_indices[i_idx + 1:]:
                if static[i] and static[j]:
                    continue
                delta = positions[i] - positions[j]
                dist = np.sqrt(np.dot(delta, delta))
                min_dist = radii[i] + radii[j]
                if dist < min_dist:
                    collisions.append((i, j))

    return collisions


def _is_star(body: np.ndarray) -> bool:
    """Determine whether a body is a star (large mass, typically not mergeable).

    Args:
        body: 1D array of shape (NUM_FIELDS,) representing a single body.

    Returns:
        True if the body type is BODY_TYPE_STAR (0), False otherwise.
    """
    return body[BODY_TYPE] == 0.0


def _land_probe_on_host(
    bodies: np.ndarray,
    probe_id: int,
    host_id: int,
) -> CollisionEvent:
    """Place a probe on the host surface without removing it."""
    dx = float(bodies[probe_id, X] - bodies[host_id, X])
    dy = float(bodies[probe_id, Y] - bodies[host_id, Y])
    dist = float(np.sqrt(dx * dx + dy * dy))
    if dist < 1e-12:
        nx, ny = 0.0, -1.0
    else:
        nx, ny = dx / dist, dy / dist

    offset = float(bodies[host_id, RADIUS] + bodies[probe_id, RADIUS])
    bodies[probe_id, X] = bodies[host_id, X] + nx * offset
    bodies[probe_id, Y] = bodies[host_id, Y] + ny * offset
    bodies[probe_id, VX] = bodies[host_id, VX]
    bodies[probe_id, VY] = bodies[host_id, VY]
    bodies[probe_id, IS_ACTIVE] = 1.0

    return {
        "type": "probe_landed",
        "id_a": int(probe_id),
        "id_b": int(host_id),
        "host_body_id": int(host_id),
        "pos_x": float(bodies[probe_id, X]),
        "pos_y": float(bodies[probe_id, Y]),
        "normal_x": float(nx),
        "normal_y": float(ny),
        "offset_distance": offset,
    }


def resolve_elastic(
    bodies: np.ndarray,
    collision_list: List[Tuple[int, int]],
) -> Tuple[np.ndarray, List[CollisionEvent]]:
    """Elastic collision handling.

    Uses 1D elastic collision formulas to exchange velocity components along
    the collision normal:
        v1_new = ((m1 - m2)*v1 + 2*m2*v2) / (m1 + m2)
        v2_new = ((m2 - m1)*v2 + 2*m1*v1) / (m1 + m2)

    Args:
        bodies: body state array of shape (N, NUM_FIELDS)
        collision_list: list of collision pairs returned by detect_collisions

    Returns:
        (bodies, events) tuple: updated body states and list of collision events
    """
    events: List[CollisionEvent] = []

    for i, j in collision_list:
        if bodies[i, IS_ACTIVE] == 0.0 or bodies[j, IS_ACTIVE] == 0.0:
            continue
        if bodies[i, IS_STATIC] == 1.0 and bodies[j, IS_STATIC] == 1.0:
            continue

        # Masses
        m1 = bodies[i, MASS]
        m2 = bodies[j, MASS]

        # Position difference vector (collision normal)
        dx = bodies[j, X] - bodies[i, X]
        dy = bodies[j, Y] - bodies[i, Y]
        dist = np.sqrt(dx * dx + dy * dy)
        if dist < 1e-12:
            continue
        nx = dx / dist
        ny = dy / dist

        # Project velocities onto the normal direction
        v1n = bodies[i, VX] * nx + bodies[i, VY] * ny
        v2n = bodies[j, VX] * nx + bodies[j, VY] * ny

        total_mass = m1 + m2

        # Velocities along the normal after elastic collision
        v1n_new = ((m1 - m2) * v1n + 2.0 * m2 * v2n) / total_mass
        v2n_new = ((m2 - m1) * v2n + 2.0 * m1 * v1n) / total_mass

        # Update velocities (normal component change)
        dv1 = (v1n_new - v1n)
        dv2 = (v2n_new - v2n)
        bodies[i, VX] += dv1 * nx
        bodies[i, VY] += dv1 * ny
        bodies[j, VX] += dv2 * nx
        bodies[j, VY] += dv2 * ny

        # Slight separation to prevent sticking
        overlap = (bodies[i, RADIUS] + bodies[j, RADIUS]) - dist
        if overlap > 0:
            # Push apart proportionally by mass
            ratio_i = m2 / total_mass
            ratio_j = m1 / total_mass
            bodies[i, X] -= nx * overlap * ratio_i
            bodies[i, Y] -= ny * overlap * ratio_i
            bodies[j, X] += nx * overlap * ratio_j
            bodies[j, Y] += ny * overlap * ratio_j

        events.append({
            "type": "elastic",
            "id_a": int(i),
            "id_b": int(j),
            "pos_x": float((bodies[i, X] + bodies[j, X]) / 2.0),
            "pos_y": float((bodies[i, Y] + bodies[j, Y]) / 2.0),
        })

    return bodies, events


def resolve_merge(
    bodies: np.ndarray,
    collision_list: List[Tuple[int, int]],
) -> Tuple[np.ndarray, List[CollisionEvent]]:
    """Merge collision handling.

    The smaller body is absorbed by the larger one. After merging, the larger
    body retains its mass and position, and the velocity is weighted by momentum
    conservation. The smaller body is marked as IS_ACTIVE = 0.
    Stars cannot be merged by other bodies.

    Args:
        bodies: body state array of shape (N, NUM_FIELDS)
        collision_list: list of collision pairs returned by detect_collisions

    Returns:
        (bodies, events) tuple: updated body states and list of collision events
    """
    events: List[CollisionEvent] = []

    for i, j in collision_list:
        if bodies[i, IS_ACTIVE] == 0.0 or bodies[j, IS_ACTIVE] == 0.0:
            continue
        if bodies[i, IS_STATIC] == 1.0 and bodies[j, IS_STATIC] == 1.0:
            continue

        m1 = bodies[i, MASS]
        m2 = bodies[j, MASS]

        # Stars cannot be merged (unless colliding with another star)
        is_star_i = _is_star(bodies[i])
        is_star_j = _is_star(bodies[j])

        if is_star_i and is_star_j:
            # Two stars colliding: use elastic collision
            continue
        if is_star_i:
            # Small body j is absorbed by star i
            absorber, absorbed = i, j
            absorber_mass, absorbed_mass = m1, m2
        elif is_star_j:
            absorber, absorbed = j, i
            absorber_mass, absorbed_mass = m2, m1
        elif m1 >= m2:
            absorber, absorbed = i, j
            absorber_mass, absorbed_mass = m1, m2
        else:
            absorber, absorbed = j, i
            absorber_mass, absorbed_mass = m2, m1

        # Momentum-conserving velocity update
        total_momentum_x = (bodies[i, MASS] * bodies[i, VX]
                            + bodies[j, MASS] * bodies[j, VX])
        total_momentum_y = (bodies[i, MASS] * bodies[i, VY]
                            + bodies[j, MASS] * bodies[j, VY])
        new_mass = bodies[i, MASS] + bodies[j, MASS]

        # Absorber gets the merged properties
        bodies[absorber, VX] = total_momentum_x / new_mass
        bodies[absorber, VY] = total_momentum_y / new_mass
        bodies[absorber, MASS] = new_mass
        # New radius: equivalent radius from volume sum
        old_radius = bodies[absorber, RADIUS]
        new_radius = (old_radius ** 3 + bodies[absorbed, RADIUS] ** 3) ** (1.0 / 3.0)
        bodies[absorber, RADIUS] = new_radius

        # Mark the absorbed body as inactive
        bodies[absorbed, IS_ACTIVE] = 0.0

        events.append({
            "type": "merge",
            "id_a": int(absorber),
            "id_b": int(absorbed),
            "pos_x": float(bodies[absorber, X]),
            "pos_y": float(bodies[absorber, Y]),
        })

    return bodies, events


def handle_collisions(
    bodies: np.ndarray,
    merge_threshold: float = 10.0,
    collision_pairs: Optional[List[Tuple[int, int]]] = None,
) -> Tuple[np.ndarray, List[CollisionEvent]]:
    """Collision detection and automatic response (new rules).

    Handles collisions based on body type and collision rules:
        - Star vs Planet: mass sum (merged into star), charge sum, planet removed
        - Planet vs Planet: mass sum, charge sum, momentum sum; position at their
          center of mass; both original entities removed, merged result placed at
          the first entity's position
        - Probe vs any non-probe body: probe lands on the surface

    Args:
        bodies: body state array of shape (N, NUM_FIELDS)
        merge_threshold: retained parameter (no longer used), kept for API compatibility
        collision_pairs: list of candidate pairs from quadtree broadphase, optional

    Returns:
        (bodies, events) tuple: updated body states and list of collision events
    """
    collision_list = detect_collisions(bodies, candidates=collision_pairs)
    if not collision_list:
        return bodies, []

    events: List[CollisionEvent] = []
    processed: set = set()  # Bodies already involved in a collision, to avoid duplicate processing

    for i, j in collision_list:
        # Skip already processed or inactive bodies
        if bodies[i, IS_ACTIVE] == 0.0 or bodies[j, IS_ACTIVE] == 0.0:
            continue
        if i in processed or j in processed:
            continue

        type_i = int(bodies[i, BODY_TYPE])
        type_j = int(bodies[j, BODY_TYPE])

        # ================================================================
        # Rule 1: Probe vs any body -> place the probe on the host surface
        # ================================================================
        if type_i == BODY_TYPE_PROBE:
            events.append(_land_probe_on_host(bodies, i, j))
            processed.add(i)
            continue

        if type_j == BODY_TYPE_PROBE:
            events.append(_land_probe_on_host(bodies, j, i))
            processed.add(j)
            continue

        # ================================================================
        # Rule 2: Star vs Planet -> merge into star
        # ================================================================
        if type_i == BODY_TYPE_STAR and type_j == BODY_TYPE_PLANET:
            bodies[i, MASS] += bodies[j, MASS]
            bodies[i, CHARGE] += bodies[j, CHARGE]
            bodies[j, IS_ACTIVE] = 0.0
            processed.add(j)
            events.append({
                "type": "star_merge",
                "id_a": int(i),
                "id_b": int(j),
                "pos_x": float(bodies[i, X]),
                "pos_y": float(bodies[i, Y]),
            })
            continue

        if type_j == BODY_TYPE_STAR and type_i == BODY_TYPE_PLANET:
            bodies[j, MASS] += bodies[i, MASS]
            bodies[j, CHARGE] += bodies[i, CHARGE]
            bodies[i, IS_ACTIVE] = 0.0
            processed.add(i)
            events.append({
                "type": "star_merge",
                "id_a": int(j),
                "id_b": int(i),
                "pos_x": float(bodies[j, X]),
                "pos_y": float(bodies[j, Y]),
            })
            continue

        # ================================================================
        # Rule 3: Planet vs Planet -> merge (center of mass, momentum conservation)
        # ================================================================
        if type_i == BODY_TYPE_PLANET and type_j == BODY_TYPE_PLANET:
            m1 = bodies[i, MASS]
            m2 = bodies[j, MASS]
            total_mass = m1 + m2

            # Center of mass position
            cx = (bodies[i, X] * m1 + bodies[j, X] * m2) / total_mass
            cy = (bodies[i, Y] * m1 + bodies[j, Y] * m2) / total_mass

            # Momentum-conserving post-merge velocity
            total_vx = (bodies[i, VX] * m1 + bodies[j, VX] * m2) / total_mass
            total_vy = (bodies[i, VY] * m1 + bodies[j, VY] * m2) / total_mass

            # Merge into i (reuse i)
            bodies[i, X] = cx
            bodies[i, Y] = cy
            bodies[i, VX] = total_vx
            bodies[i, VY] = total_vy
            bodies[i, MASS] = total_mass
            bodies[i, CHARGE] = bodies[i, CHARGE] + bodies[j, CHARGE]
            # Radius: cubic root of volume sum
            bodies[i, RADIUS] = (
                bodies[i, RADIUS] ** 3 + bodies[j, RADIUS] ** 3
            ) ** (1.0 / 3.0)

            bodies[j, IS_ACTIVE] = 0.0
            processed.add(j)

            events.append({
                "type": "planet_merge",
                "id_a": int(i),
                "id_b": int(j),
                "pos_x": float(cx),
                "pos_y": float(cy),
            })
            continue

        # ================================================================
        # Other collision types (undefined rules): skip (preserve original state)
        # ================================================================

    return bodies, events
