"""Quadtree spatial partitioning implementation.

Provides spatial partitioning to accelerate gravity computation and collision detection.
Rebuilt every frame (clear + insert all), supports circular range queries, nearest-neighbor queries, collision candidate queries.

Typical usage::

    tree = Quadtree(boundary=Rect(-1000, -1000, 2000, 2000))
    tree.rebuild(bodies)
    nearby = tree.query_range(0, 0, 50)
    nearest = tree.query_nearest(10, 20)
    force = tree.barnes_hut_force(0, bodies, theta=0.5)
"""

import math
from typing import List, Optional, Tuple

import numpy as np

from src.config import QUADTREE_CAPACITY
from src.core.interfaces import IQuadtree, Rect
from src.core.types import MASS, X, Y, IS_ACTIVE


class QuadtreeNode:
    """Quadtree node storing boundary, child node pointers, centroid statistics, and point list.

    Leaf nodes store the actual point list; internal nodes clear the point list after splitting and create four children.
    Each node maintains the subtree total mass (mass) and centroid (cx, cy) for Barnes-Hut approximation.

    Attributes:
        boundary: Axis-aligned rectangular region covered by this node
        capacity: Split threshold (splits when point count exceeds this value)
        points: Point list within leaf nodes, each entry is (body_id, x, y, mass)
        nw, ne, sw, se: Four child nodes (only valid when divided=True)
        divided: Whether this node has been subdivided
        mass: Subtree total mass
        cx: Subtree centroid x-coordinate
        cy: Subtree centroid y-coordinate
    """

    __slots__ = (
        'boundary', 'capacity', 'points',
        'nw', 'ne', 'sw', 'se', 'divided',
        'mass', 'cx', 'cy',
    )

    def __init__(self, boundary: Rect, capacity: int) -> None:
        """Initialize a quadtree node.

        Args:
            boundary: Rectangular region covered by the node
            capacity: Split threshold
        """
        self.boundary = boundary
        self.capacity = capacity
        self.points: List[Tuple[int, float, float, float]] = []
        self.nw: Optional['QuadtreeNode'] = None
        self.ne: Optional['QuadtreeNode'] = None
        self.sw: Optional['QuadtreeNode'] = None
        self.se: Optional['QuadtreeNode'] = None
        self.divided: bool = False
        self.mass: float = 0.0
        self.cx: float = 0.0
        self.cy: float = 0.0

    def insert(self, body_id: int, x: float, y: float, mass: float) -> bool:
        """Insert a point into this node or its children.

        Args:
            body_id: Row index of the body in the bodies array
            x: x-coordinate
            y: y-coordinate
            mass: Body mass

        Returns:
            True if inserted successfully, False if outside node boundary
        """
        bx, by, bw, bh = self.boundary
        if not (bx <= x <= bx + bw and by <= y <= by + bh):
            return False

        # Update node centroid statistics
        total_mass = self.mass + mass
        if total_mass > 0.0:
            self.cx = (self.cx * self.mass + x * mass) / total_mass
            self.cy = (self.cy * self.mass + y * mass) / total_mass
        self.mass = total_mass

        if not self.divided:
            if len(self.points) < self.capacity:
                self.points.append((body_id, x, y, mass))
                return True
            self._subdivide()

        return self._insert_to_child(body_id, x, y, mass)

    # ------------------------------------------------------------------
    # Non-public helpers
    # ------------------------------------------------------------------

    def _subdivide(self) -> None:
        """Split this node into four child nodes and redistribute existing points."""
        x, y, w, h = self.boundary
        hw = w * 0.5
        hh = h * 0.5

        self.nw = QuadtreeNode(Rect(x, y, hw, hh), self.capacity)
        self.ne = QuadtreeNode(Rect(x + hw, y, hw, hh), self.capacity)
        self.sw = QuadtreeNode(Rect(x, y + hh, hw, hh), self.capacity)
        self.se = QuadtreeNode(Rect(x + hw, y + hh, hw, hh), self.capacity)
        self.divided = True

        # Redistribute existing points to child nodes
        existing_points = self.points
        self.points = []
        for pid, px, py, pmass in existing_points:
            self._insert_to_child(pid, px, py, pmass)

    def _insert_to_child(self, body_id: int, x: float, y: float, mass: float) -> bool:
        """Insert a point into the appropriate child node."""
        cx = self.boundary.x + self.boundary.w * 0.5
        cy = self.boundary.y + self.boundary.h * 0.5

        if y <= cy:
            if x <= cx:
                return self.nw.insert(body_id, x, y, mass)  # type: ignore[union-attr]
            else:
                return self.ne.insert(body_id, x, y, mass)  # type: ignore[union-attr]
        else:
            if x <= cx:
                return self.sw.insert(body_id, x, y, mass)  # type: ignore[union-attr]
            else:
                return self.se.insert(body_id, x, y, mass)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def query_range(self, cx: float, cy: float, radius: float,
                    result: List[int]) -> None:
        """Recursively query body_ids within a circular area, appending to result.

        Args:
            cx: Circle center x
            cy: Circle center y
            radius: Circle radius
            result: Output list
        """
        if self.mass == 0.0:
            return
        if not _circle_intersects_rect(cx, cy, radius, self.boundary):
            return

        if self.divided:
            for child in (self.nw, self.ne, self.sw, self.se):
                child.query_range(cx, cy, radius, result)  # type: ignore[union-attr]
        else:
            r2 = radius * radius
            for pid, px, py, _ in self.points:
                dx = px - cx
                dy = py - cy
                if dx * dx + dy * dy <= r2:
                    result.append(pid)

    def query_nearest(self, x: float, y: float) -> Optional[int]:
        """Recursively find the body ID nearest to (x, y).

        Args:
            x: Query point x-coordinate
            y: Query point y-coordinate

        Returns:
            Nearest body ID, or None if no body exists
        """
        best_id: Optional[int] = None
        best_dist_sq: float = float('inf')

        def _search(node: QuadtreeNode) -> None:
            nonlocal best_id, best_dist_sq

            if node.mass == 0.0:
                return

            # Compute minimum distance from query point to node boundary for pruning
            bx, by, bw, bh = node.boundary
            dx = max(bx - x, 0.0, x - (bx + bw))
            dy = max(by - y, 0.0, y - (by + bh))
            min_dist_sq = dx * dx + dy * dy
            if min_dist_sq >= best_dist_sq:
                return

            if node.divided:
                # Sort by distance to child node center, search closer ones first
                children = [node.nw, node.ne, node.sw, node.se]
                children.sort(
                    key=lambda c: _point_dist_sq(x, y, c.cx, c.cy) if c else float('inf')
                )
                for child in children:
                    if child is not None:
                        _search(child)
            else:
                for pid, px, py, _ in node.points:
                    d_sq = (px - x) * (px - x) + (py - y) * (py - y)
                    if d_sq < best_dist_sq:
                        best_dist_sq = d_sq
                        best_id = pid

        _search(self)
        return best_id

    def collect_pairs(self, pairs: set) -> None:
        """Collect body pairs sharing the same leaf node (collision candidates).

        Args:
            pairs: Output set, each entry is (min_id, max_id)
        """
        if self.mass == 0.0:
            return
        if self.divided:
            for child in (self.nw, self.ne, self.sw, self.se):
                child.collect_pairs(pairs)  # type: ignore[union-attr]
        else:
            pts = self.points
            n = len(pts)
            for i in range(n):
                pid_i = pts[i][0]
                for j in range(i + 1, n):
                    pid_j = pts[j][0]
                    if pid_i != pid_j:
                        pairs.add((min(pid_i, pid_j), max(pid_i, pid_j)))


# ============================================================================
# Quadtree main class
# ============================================================================


class Quadtree(IQuadtree):
    """Quadtree implementation, implementing the IQuadtree interface.

    Supports dynamic insertion, full rebuild, circular range queries, nearest-neighbor queries, and Barnes-Hut gravity approximation.

    Args:
        boundary: Rectangular region covered by the root node
        capacity: Maximum capacity per node (default QUADTREE_CAPACITY)
    """

    def __init__(self, boundary: Rect, capacity: int = QUADTREE_CAPACITY) -> None:
        self._capacity = capacity
        self._root = QuadtreeNode(boundary, capacity)

    # ------------------------------------------------------------------
    # IQuadtree interface methods
    # ------------------------------------------------------------------

    def insert(self, body_id: int, x: float, y: float) -> bool:
        """Insert a body into the quadtree.

        Note:
            This method inserts with mass=1.0 and does not affect centroid calculations.
            Use rebuild() for batch insertion to correctly compute mass statistics.

        Args:
            body_id: Row index of the body in the bodies array
            x: x-coordinate
            y: y-coordinate

        Returns:
            True if inserted successfully, False if outside boundary
        """
        return self._root.insert(body_id, x, y, 1.0)

    def rebuild(self, bodies: np.ndarray) -> None:
        """Clear and rebuild the quadtree.

        Automatically computes the bounding rectangle (square, 10% margin) based on all active body positions.

        Args:
            bodies: Body state array of shape (N, NUM_FIELDS)
        """
        active_indices = np.where(bodies[:, IS_ACTIVE] == 1.0)[0]
        n_active = len(active_indices)

        if n_active == 0:
            self._root = QuadtreeNode(Rect(0.0, 0.0, 1.0, 1.0), self._capacity)
            return

        xs = bodies[active_indices, X]
        ys = bodies[active_indices, Y]
        masses = bodies[active_indices, MASS]

        min_x = float(np.min(xs))
        max_x = float(np.max(xs))
        min_y = float(np.min(ys))
        max_y = float(np.max(ys))

        size = max(max_x - min_x, max_y - min_y, 1.0)
        size *= 1.1  # 10% margin
        center_x = (min_x + max_x) * 0.5
        center_y = (min_y + max_y) * 0.5

        boundary = Rect(center_x - size * 0.5, center_y - size * 0.5, size, size)
        self._root = QuadtreeNode(boundary, self._capacity)

        for i in range(n_active):
            body_id = int(active_indices[i])
            self._root.insert(body_id, float(xs[i]), float(ys[i]), float(masses[i]))

    def query_range(self, x: float, y: float, radius: float) -> List[int]:
        """Range query: return body IDs within the specified circular area.

        Args:
            x: Circle center x-coordinate
            y: Circle center y-coordinate
            radius: Circle radius

        Returns:
            List of body IDs within the area
        """
        result: List[int] = []
        self._root.query_range(x, y, radius, result)
        return result

    def query_nearest(self, x: float, y: float) -> Optional[int]:
        """Nearest neighbor query: return the body ID closest to the specified coordinates.

        Args:
            x: Query point x-coordinate
            y: Query point y-coordinate

        Returns:
            Nearest body ID, or None if no body exists
        """
        return self._root.query_nearest(x, y)

    def barnes_hut_force(
        self, body_id: int, bodies: np.ndarray, theta: float
    ) -> Tuple[float, float]:
        """Compute total gravitational force on a body using Barnes-Hut approximation.

        Delegates computation to the barnes_hut.compute_force function.

        Args:
            body_id: ID of the target body
            bodies: State array of all bodies
            theta: Barnes-Hut threshold (typically 0.5)

        Returns:
            (fx, fy) net force vector (N)
        """
        from src.quadtree.barnes_hut import compute_force
        return compute_force(self._root, body_id, bodies, theta)

    # ------------------------------------------------------------------
    # Extension methods (non-interface)
    # ------------------------------------------------------------------

    def query_collision_candidates(self) -> List[Tuple[int, int]]:
        """Return body pairs sharing the same leaf node, as collision detection candidates.

        This is part of the collision detection broad phase:
        returns body pairs co-located in leaf nodes for subsequent precise collision detection.

        Returns:
            List of (id1, id2), guaranteed id1 < id2
        """
        pairs: set = set()
        self._root.collect_pairs(pairs)
        return list(pairs)

    def get_statistics(self) -> dict:
        """Return quadtree statistics.

        Returns:
            Dictionary containing node count, total mass, depth, etc.
        """
        node_count = 0
        max_depth = 0

        def _count(node: QuadtreeNode, depth: int) -> None:
            nonlocal node_count, max_depth
            node_count += 1
            max_depth = max(max_depth, depth)
            if node.divided:
                for child in (node.nw, node.ne, node.sw, node.se):
                    _count(child, depth + 1)  # type: ignore[arg-type]

        _count(self._root, 0)
        return {
            'node_count': node_count,
            'max_depth': max_depth,
            'total_mass': self._root.mass,
            'total_points': len(self._root.points) if not self._root.divided else -1,
        }


# ============================================================================
# Internal utility functions
# ============================================================================


def _circle_intersects_rect(
    cx: float, cy: float, r: float, rect: Rect
) -> bool:
    """Check whether a circle intersects an axis-aligned rectangle.

    Finds the point on the rectangle closest to the circle center and checks if the distance <= r.

    Args:
        cx: Circle center x
        cy: Circle center y
        r: Circle radius
        rect: Rectangle

    Returns:
        True if intersecting
    """
    closest_x = max(rect.x, min(cx, rect.x + rect.w))
    closest_y = max(rect.y, min(cy, rect.y + rect.h))
    dx = cx - closest_x
    dy = cy - closest_y
    return dx * dx + dy * dy <= r * r


def _point_dist_sq(x1: float, y1: float, x2: float, y2: float) -> float:
    """Return the squared distance between two points."""
    dx = x1 - x2
    dy = y1 - y2
    return dx * dx + dy * dy
