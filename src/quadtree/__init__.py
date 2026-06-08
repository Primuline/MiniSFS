"""MiniSFS quadtree spatial data structure package.

Provides:
- Quadtree — Spatial partitioning to accelerate force computation and collision detection.
- Barnes-Hut approximation (compute_force) — O(n log n) gravitational acceleration.
- TrailBuffer — Deque-based body trail history.

Dependencies: NumPy, src.config, src.core
"""

from src.quadtree.quadtree import Quadtree, QuadtreeNode
from src.quadtree.barnes_hut import compute_force
from src.quadtree.trail import TrailBuffer

__all__ = [
    "Quadtree",
    "QuadtreeNode",
    "compute_force",
    "TrailBuffer",
]
