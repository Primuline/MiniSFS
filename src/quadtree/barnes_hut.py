"""Barnes-Hut gravity approximation computation.

Traverses the quadtree and applies centroid approximation to distant nodes
satisfying the condition s/d < theta, avoiding O(n^2) pairwise calculations
and reducing complexity to O(n log n).

Typical usage::

    from src.quadtree.barnes_hut import compute_force
    fx, fy = compute_force(root_node, body_id, bodies, theta=0.5)
"""

import math
from typing import Tuple

import numpy as np

from src.config import GRAVITATIONAL_CONSTANT, SOFTENING
from src.core.types import MASS, X, Y

# Precompute squared softening distance
_SOFTENING_SQ = SOFTENING * SOFTENING


def compute_force(
    node: 'QuadtreeNode',
    target_id: int,
    bodies: np.ndarray,
    theta: float,
) -> Tuple[float, float]:
    """Recursively compute the total gravitational force on a target body using Barnes-Hut approximation.

    Traverses quadtree nodes:
    - If the node is a leaf, directly compute gravitational forces from all bodies within the node.
    - If the node is internal and satisfies s/d < theta (far-field condition),
      approximate the force using the node's centroid and total mass, without recursing into children.
    - If the approximation condition is not met, recurse into the four child nodes.

    Args:
        node: Current quadtree node (typically starting from the root)
        target_id: Row index of the target body in the bodies array
        bodies: Body state array of shape (N, NUM_FIELDS)
        theta: Barnes-Hut threshold (use centroid approximation when s / d < theta)

    Returns:
        (fx, fy) net force vector (N)
    """
    tx = float(bodies[target_id, X])
    ty = float(bodies[target_id, Y])
    tm = float(bodies[target_id, MASS])

    if tm <= 0.0:
        return (0.0, 0.0)

    fx, fy = _walk(node, target_id, tx, ty, tm, bodies, theta)
    return (fx, fy)


# ======================================================================
# Internal recursive functions
# ======================================================================


def _walk(
    node: 'QuadtreeNode',
    target_id: int,
    tx: float,
    ty: float,
    tm: float,
    bodies: np.ndarray,
    theta: float,
) -> Tuple[float, float]:
    """Recursively traverse the quadtree to compute gravitational force.

    Args:
        node: Current node
        target_id: Target body ID
        tx, ty: Target body coordinates
        tm: Target body mass
        bodies: Body state array
        theta: Barnes-Hut threshold

    Returns:
        (fx, fy) net force
    """
    if node.mass == 0.0 or (not node.divided and len(node.points) == 0):
        return (0.0, 0.0)

    # Compute node side length and distance from target to centroid
    bx, by, bw, bh = node.boundary
    s = max(bw, bh)
    dx = node.cx - tx
    dy = node.cy - ty
    d = math.sqrt(dx * dx + dy * dy)

    if node.divided:
        # Internal node: check if centroid approximation can be used
        if d > 0.0 and s / d < theta:
            # Far-field condition met, use centroid approximation
            return _compute_force_to_mass(tm, node.mass, dx, dy, d)
        else:
            # Approximation condition not met, recurse into children
            fx, fy = 0.0, 0.0
            for child in (node.nw, node.ne, node.sw, node.se):
                if child is not None and child.mass > 0.0:
                    cfx, cfy = _walk(child, target_id, tx, ty, tm, bodies, theta)
                    fx += cfx
                    fy += cfy
            return (fx, fy)
    else:
        # Leaf node: directly compute gravitational force for all points
        # If there are multiple points in the leaf and far-field condition is met, use node centroid
        if len(node.points) > 1 and d > 0.0 and s / d < theta:
            return _compute_force_to_mass(tm, node.mass, dx, dy, d)

        fx, fy = 0.0, 0.0
        for pid, px, py, pmass in node.points:
            if pid == target_id:
                continue
            if pmass <= 0.0:
                continue
            pdx = px - tx
            pdy = py - ty
            dist_sq = pdx * pdx + pdy * pdy + _SOFTENING_SQ
            dist = math.sqrt(dist_sq)
            f = GRAVITATIONAL_CONSTANT * tm * pmass / dist_sq
            fx += f * pdx / dist
            fy += f * pdy / dist
        return (fx, fy)


def _compute_force_to_mass(
    target_mass: float,
    node_mass: float,
    dx: float,
    dy: float,
    d: float,
) -> Tuple[float, float]:
    """Compute gravitational force between the target body and a node centroid.

    Args:
        target_mass: Target body mass
        node_mass: Node total mass
        dx: x-component from target to centroid
        dy: y-component from target to centroid
        d: Distance from target to centroid

    Returns:
        (fx, fy) force components
    """
    dist_sq = d * d + _SOFTENING_SQ
    f = GRAVITATIONAL_CONSTANT * target_mass * node_mass / dist_sq
    if d > 1e-15:
        fx = f * dx / d
        fy = f * dy / d
    else:
        fx = 0.0
        fy = 0.0
    return (fx, fy)
