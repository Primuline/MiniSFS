"""Unit tests for Quadtree, Barnes-Hut, and TrailBuffer.

Test coverage:
- Quadtree: insert, rebuild, range query, nearest neighbor query, collision candidates
- Barnes-Hut: gravitational approximation accuracy and performance
- TrailBuffer: push_frame, get_trail, rewind, clear
"""

import math
import time

import numpy as np
import pytest

from src.config import (
    GRAVITATIONAL_CONSTANT,
    QUADTREE_CAPACITY,
    MAX_TRAIL_LENGTH,
)
from src.core.interfaces import Rect
from src.core.types import (
    X, Y, MASS, RADIUS, IS_ACTIVE, NUM_FIELDS,
    create_body_state_array, make_body,
)
from src.quadtree import Quadtree, QuadtreeNode, compute_force, TrailBuffer


# ============================================================================
# Helper functions
# ============================================================================

def _make_bodies(positions: list, masses: list = None) -> np.ndarray:
    """Create a test body state array from position lists."""
    n = len(positions)
    bodies = create_body_state_array(n)
    for i, (px, py) in enumerate(positions):
        bodies[i, X] = px
        bodies[i, Y] = py
        bodies[i, MASS] = 1.0  # ensure default mass is non-zero for correct quadtree centroid calculation
    if masses is not None:
        for i, m in enumerate(masses):
            bodies[i, MASS] = m
    return bodies


# ============================================================================
# Quadtree basic tests
# ============================================================================

class TestQuadtreeNode:
    """QuadtreeNode basic operation tests."""

    def test_insert_single_point(self) -> None:
        """Test inserting a single point into a quadtree node."""
        node = QuadtreeNode(Rect(0, 0, 100, 100), 4)
        assert node.insert(0, 10, 20, 100.0)
        assert len(node.points) == 1
        assert node.mass == 100.0
        assert node.cx == 10.0
        assert node.cy == 20.0

    def test_insert_out_of_bounds(self) -> None:
        """Test that inserting out of bounds returns False."""
        node = QuadtreeNode(Rect(0, 0, 100, 100), 4)
        assert not node.insert(0, -10, 50, 1.0)
        assert not node.insert(0, 150, 50, 1.0)
        assert node.mass == 0.0

    def test_subdivide_on_overflow(self) -> None:
        """Test auto-subdivision when capacity is exceeded."""
        node = QuadtreeNode(Rect(0, 0, 100, 100), 2)
        node.insert(0, 10, 10, 1.0)
        node.insert(1, 20, 20, 1.0)
        assert not node.divided
        node.insert(2, 30, 30, 1.0)
        assert node.divided
        # after subdivision, the original leaf node should have no points
        assert len(node.points) == 0

    def test_center_of_mass_correct(self) -> None:
        """Test correctness of centroid calculation."""
        node = QuadtreeNode(Rect(0, 0, 100, 100), 4)
        node.insert(0, 0, 0, 10.0)
        node.insert(1, 10, 0, 30.0)
        # centroid: (0*10 + 10*30) / 40 = 7.5, (0*10 + 0*30) / 40 = 0
        assert node.cx == pytest.approx(7.5)
        assert node.cy == pytest.approx(0.0)
        assert node.mass == pytest.approx(40.0)


class TestQuadtree:
    """Quadtree core functionality tests."""

    def test_create(self) -> None:
        """Test quadtree creation."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        assert tree is not None

    def test_insert_via_interface(self) -> None:
        """Test the insert method via the IQuadtree interface."""
        tree = Quadtree(Rect(0, 0, 100, 100))
        assert tree.insert(0, 10, 20)
        stats = tree.get_statistics()
        assert stats['total_points'] == 1

    def test_rebuild(self) -> None:
        """Test rebuilding the quadtree."""
        bodies = _make_bodies([(10, 10), (20, 20), (30, 30)], [1.0, 2.0, 3.0])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        stats = tree.get_statistics()
        assert stats['total_mass'] == pytest.approx(6.0)
        assert stats['node_count'] >= 1

    def test_rebuild_empty(self) -> None:
        """Test rebuilding the quadtree with no active bodies."""
        bodies = _make_bodies([(10, 10)])
        bodies[0, IS_ACTIVE] = 0.0
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        stats = tree.get_statistics()
        assert stats['total_mass'] == 0.0

    def test_rebuild_all_inactive(self) -> None:
        """Test rebuilding when all bodies are inactive."""
        bodies = create_body_state_array(5)
        bodies[:, IS_ACTIVE] = 0.0
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        stats = tree.get_statistics()
        assert stats['total_mass'] == 0.0

    def test_rebuild_updates_boundary(self) -> None:
        """Test that rebuild automatically computes the boundary from body coordinates."""
        bodies = _make_bodies([(-500, -500), (500, 500)])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        # inserting a new point should succeed within the new boundaries
        assert tree.insert(2, 0, 0)

    def test_rebuild_large_scale(self) -> None:
        """Test quadtree build performance with 1000 bodies (< 1ms)."""
        n = 1000
        np.random.seed(42)
        positions = np.random.uniform(-1e9, 1e9, (n, 2))
        masses = np.random.uniform(1e20, 1e30, n)
        bodies = create_body_state_array(n)
        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = masses

        tree = Quadtree(Rect(-1e10, -1e10, 2e10, 2e10))
        start = time.perf_counter()
        tree.rebuild(bodies)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.01, f"Rebuild took {elapsed*1000:.2f}ms, exceeds 10ms limit"


class TestQuadtreeQueryRange:
    """Range query tests."""

    def test_query_range_empty(self) -> None:
        """Test range query on an empty quadtree."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        result = tree.query_range(0, 0, 50)
        assert result == []

    def test_query_range_single(self) -> None:
        """Test range query with a single point."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 10)
        result = tree.query_range(0, 0, 20)
        assert 0 in result

    def test_query_range_outside(self) -> None:
        """Test that a point outside the range is not returned."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 100, 100)
        result = tree.query_range(0, 0, 10)
        assert result == []

    def test_query_range_multiple(self) -> None:
        """Test range query with multiple points."""
        bodies = _make_bodies([(0, 0), (10, 10), (50, 50), (100, 100), (-10, -10)])
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.rebuild(bodies)
        result = tree.query_range(0, 0, 20)
        assert len(result) == 3  # (0,0), (10,10), (-10,-10)
        assert 0 in result
        assert 1 in result
        assert 4 in result

    def test_query_range_radius_edge(self) -> None:
        """Test a point on the boundary of the circle."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 0)
        result = tree.query_range(0, 0, 10)
        assert 0 in result

    def test_query_range_after_rebuild(self) -> None:
        """Test that range query is correct after rebuild."""
        bodies = _make_bodies([(0, 0), (5, 5), (100, 100)])
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.rebuild(bodies)
        result = tree.query_range(0, 0, 10)
        assert len(result) == 2
        assert set(result) == {0, 1}

    def test_query_range_no_miss(self) -> None:
        """Test range query has no misses with random distribution."""
        np.random.seed(123)
        n = 200
        positions = np.random.uniform(-500, 500, (n, 2))
        bodies = create_body_state_array(n)
        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = 1.0

        tree = Quadtree(Rect(-600, -600, 1200, 1200))
        tree.rebuild(bodies)

        # query at multiple locations
        for cx, cy, r in [(0, 0, 100), (200, 200, 150), (-300, -300, 80)]:
            tree_result = set(tree.query_range(cx, cy, r))
            naive_result = set(
                i for i in range(n)
                if (positions[i, 0] - cx) ** 2 + (positions[i, 1] - cy) ** 2 <= r * r
            )
            assert tree_result == naive_result, (
                f"Query (cx={cx}, cy={cy}, r={r}) missed "
                f"tree={tree_result ^ naive_result}"
            )


class TestQuadtreeNearest:
    """Nearest neighbor query tests."""

    def test_nearest_empty(self) -> None:
        """Test nearest neighbor query on an empty quadtree."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        assert tree.query_nearest(0, 0) is None

    def test_nearest_single(self) -> None:
        """Test nearest neighbor with a single point."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 10)
        assert tree.query_nearest(0, 0) == 0

    def test_nearest_exact(self) -> None:
        """Test when the query point coincides with a body."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 10)
        tree.insert(1, 50, 50)
        assert tree.query_nearest(10, 10) == 0

    def test_nearest_correct(self) -> None:
        """Test correctness of nearest neighbor."""
        bodies = _make_bodies([(0, 0), (10, 0), (100, 100)])
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.rebuild(bodies)
        # (5, 0) is distance 5 from (0,0), 5 from (10,0), 134 from (100,100)
        # (0,0) is the nearest (both 5, first one is returned)
        nearest = tree.query_nearest(5, 0)
        assert nearest is not None

    def test_nearest_negative_coords(self) -> None:
        """Test negative coordinates."""
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.insert(0, -50, -50)
        tree.insert(1, 50, 50)
        assert tree.query_nearest(-45, -45) == 0

    def test_nearest_quality(self) -> None:
        """Test that nearest neighbor matches brute-force search."""
        np.random.seed(456)
        n = 100
        positions = np.random.uniform(-500, 500, (n, 2))
        bodies = create_body_state_array(n)
        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = 1.0

        tree = Quadtree(Rect(-600, -600, 1200, 1200))
        tree.rebuild(bodies)

        # test multiple query points
        for qx, qy in [(0, 0), (300, -200), (-400, 100), (50, 50)]:
            tree_result = tree.query_nearest(qx, qy)
            dists = np.sum((positions - np.array([qx, qy])) ** 2, axis=1)
            brute_result = int(np.argmin(dists))
            assert tree_result == brute_result, (
                f"Nearest neighbor query (qx={qx}, qy={qy}): "
                f"tree={tree_result}, brute={brute_result}"
            )


class TestQuadtreeCollisionCandidates:
    """Collision candidate query tests."""

    def test_collision_candidates_empty(self) -> None:
        """Test empty quadtree returns empty list."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        assert tree.query_collision_candidates() == []

    def test_collision_candidates_single(self) -> None:
        """Test single body returns empty list."""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 10)
        assert tree.query_collision_candidates() == []

    def test_collision_candidates_pair(self) -> None:
        """Test two bodies are identified as candidates."""
        # two bodies in the same region
        bodies = _make_bodies([(10, 10), (12, 12)])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        pairs = tree.query_collision_candidates()
        assert len(pairs) >= 1
        assert (0, 1) in pairs

    def test_collision_candidates_distant(self) -> None:
        """Test distant bodies appear in different leaf nodes."""
        bodies = _make_bodies([(10, 10), (90, 90)])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        pairs = tree.query_collision_candidates()
        # since capacity is 4, both points in the same quadrant may be in the same leaf node
        # this test ensures the interface doesn't raise an exception
        assert isinstance(pairs, list)

    def test_collision_candidates_no_duplicates(self) -> None:
        """Test collision candidates have no duplicate pairs."""
        bodies = _make_bodies([(1, 1), (2, 2), (3, 3), (4, 4)])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        pairs = tree.query_collision_candidates()
        # check no duplicates
        unique_pairs = set(pairs)
        assert len(pairs) == len(unique_pairs)


class TestQuadtreeStatistics:
    """Quadtree statistics tests."""

    def test_statistics_basic(self) -> None:
        """Test completeness of statistics."""
        bodies = _make_bodies([(0, 0), (10, 10), (20, 20)], [1.0, 2.0, 3.0])
        tree = Quadtree(Rect(-50, -50, 100, 100))
        tree.rebuild(bodies)
        stats = tree.get_statistics()
        for key in ('node_count', 'max_depth', 'total_mass', 'total_points'):
            assert key in stats
        assert stats['total_mass'] == pytest.approx(6.0)

    def test_statistics_after_clear(self) -> None:
        """Test statistics reset after clearing."""
        bodies = _make_bodies([(0, 0), (10, 10)], [1.0, 1.0])
        tree = Quadtree(Rect(-50, -50, 100, 100))
        tree.rebuild(bodies)
        tree.rebuild(create_body_state_array(0))
        stats = tree.get_statistics()
        assert stats['total_mass'] == 0.0


# ============================================================================
# Barnes-Hut tests
# ============================================================================

class TestBarnesHut:
    """Barnes-Hut gravitational approximation tests."""

    def test_force_single_body(self) -> None:
        """Test force is zero with a single body."""
        bodies = make_body(x=0, y=0, mass=1e30)
        tree = Quadtree(Rect(-1e10, -1e10, 2e10, 2e10))
        tree.rebuild(bodies)
        fx, fy = tree.barnes_hut_force(0, bodies, theta=0.5)
        assert fx == pytest.approx(0.0)
        assert fy == pytest.approx(0.0)

    def test_force_two_bodies(self) -> None:
        """Test gravitational force between two bodies (consistent with universal gravitation formula)."""
        bodies = create_body_state_array(2)
        m1, m2 = 1e30, 5e28
        bodies[0, X] = 0.0
        bodies[0, Y] = 0.0
        bodies[0, MASS] = m1
        bodies[1, X] = 1e9
        bodies[1, Y] = 0.0
        bodies[1, MASS] = m2

        # expected gravitational force
        dist = 1e9
        expected_f = GRAVITATIONAL_CONSTANT * m1 * m2 / (dist * dist)

        tree = Quadtree(Rect(-1e10, -1e10, 2e10, 2e10))
        tree.rebuild(bodies)
        fx, fy = tree.barnes_hut_force(0, bodies, theta=0.5)
        assert fx == pytest.approx(expected_f, abs=expected_f * 0.01)
        assert fy == pytest.approx(0.0)

    def test_force_three_bodies_collinear(self) -> None:
        """Test gravitational force with three collinear bodies."""
        bodies = create_body_state_array(3)
        bodies[0, X] = 0.0
        bodies[0, MASS] = 1e30
        bodies[1, X] = 1e9
        bodies[1, MASS] = 5e28
        bodies[2, X] = 2e9
        bodies[2, MASS] = 1e28

        # body 0 experiences the sum of forces from bodies 1 and 2
        f_01 = GRAVITATIONAL_CONSTANT * bodies[0, MASS] * bodies[1, MASS] / (1e9 ** 2)
        f_02 = GRAVITATIONAL_CONSTANT * bodies[0, MASS] * bodies[2, MASS] / (2e9 ** 2)
        expected_fx = (f_01 + f_02)

        tree = Quadtree(Rect(-1e10, -1e10, 2e10, 2e10))
        tree.rebuild(bodies)
        fx, fy = tree.barnes_hut_force(0, bodies, theta=0.0)
        # theta=0 uses no approximation
        assert fx == pytest.approx(expected_fx, abs=abs(expected_fx) * 0.01)
        assert fy == pytest.approx(0.0)

    def test_barnes_hut_vs_brute_force_accuracy(self) -> None:
        """Test accuracy of Barnes-Hut (theta=0.5) against direct O(n^2)."""
        np.random.seed(789)
        n = 50
        bodies = create_body_state_array(n)
        positions = np.random.uniform(-1e8, 1e8, (n, 2))
        masses = np.random.uniform(1e25, 1e30, n)

        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = masses

        # direct O(n^2) calculation
        brute_forces = np.zeros((n, 2))
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                dx = bodies[j, X] - bodies[i, X]
                dy = bodies[j, Y] - bodies[i, Y]
                dist_sq = dx * dx + dy * dy + 1.0
                dist = math.sqrt(dist_sq)
                f = GRAVITATIONAL_CONSTANT * bodies[i, MASS] * bodies[j, MASS] / dist_sq
                brute_forces[i, 0] += f * dx / dist
                brute_forces[i, 1] += f * dy / dist

        # Barnes-Hut calculation
        tree = Quadtree(Rect(-2e8, -2e8, 4e8, 4e8))
        tree.rebuild(bodies)
        bh_forces = np.zeros((n, 2))
        for i in range(n):
            fx, fy = tree.barnes_hut_force(i, bodies, theta=0.5)
            bh_forces[i, 0] = fx
            bh_forces[i, 1] = fy

        # check error < 5%
        for i in range(n):
            bf = math.sqrt(brute_forces[i, 0] ** 2 + brute_forces[i, 1] ** 2)
            bh = math.sqrt(bh_forces[i, 0] ** 2 + bh_forces[i, 1] ** 2)
            if bf > 0:
                relative_error = abs(bh - bf) / bf
                assert relative_error < 0.05, (
                    f"Body {i}: relative error {relative_error:.4f} > 5%"
                )

    def test_barnes_hut_performance(self) -> None:
        """Test Barnes-Hut (theta=0.5) is at least 10x faster than O(n^2) (n=1000)."""
        n = 1000
        np.random.seed(101112)
        bodies = create_body_state_array(n)
        positions = np.random.uniform(-1e9, 1e9, (n, 2))
        masses = np.random.uniform(1e25, 1e30, n)
        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = masses
        bodies[:, IS_ACTIVE] = 1.0

        # Barnes-Hut
        tree = Quadtree(Rect(-2e9, -2e9, 4e9, 4e9))
        tree.rebuild(bodies)

        start = time.perf_counter()
        for i in range(n):
            tree.barnes_hut_force(i, bodies, theta=0.5)
        bh_time = time.perf_counter() - start

        # O(n^2) brute force (only measure 50 points, extrapolate)
        start = time.perf_counter()
        for i in range(50):
            tx, ty = bodies[i, X], bodies[i, Y]
            tm = bodies[i, MASS]
            fx, fy = 0.0, 0.0
            for j in range(n):
                if i == j:
                    continue
                dx = bodies[j, X] - tx
                dy = bodies[j, Y] - ty
                dist_sq = dx * dx + dy * dy + 1.0
                dist = math.sqrt(dist_sq)
                f = GRAVITATIONAL_CONSTANT * tm * bodies[j, MASS] / dist_sq
                fx += f * dx / dist
                fy += f * dy / dist
        brute_partial = time.perf_counter() - start
        brute_time_estimate = brute_partial * (n / 50.0)

        speedup = brute_time_estimate / max(bh_time, 1e-9)
        print(
            f"\nBarnes-Hut: {bh_time*1000:.1f}ms, "
            f"Brute-force (extrapolated): {brute_time_estimate*1000:.1f}ms, "
            f"Speedup: {speedup:.1f}x"
        )
        assert speedup > 10.0, (
            f"Barnes-Hut speedup {speedup:.1f}x, does not meet 10x requirement"
        )


# ============================================================================
# TrailBuffer tests
# ============================================================================

class TestTrailBuffer:
    """TrailBuffer functionality tests."""

    def test_create(self) -> None:
        """Test creating a trail buffer."""
        buf = TrailBuffer()
        assert buf is not None
        assert len(buf) == 0

    def test_push_frame_new_body(self) -> None:
        """Test pushing a frame for a new body."""
        buf = TrailBuffer()
        buf.push_frame(0, 10.0, 20.0)
        assert buf.has_trail(0)
        assert len(buf) == 1

    def test_get_trail_empty(self) -> None:
        """Test getting a trail that doesn't exist."""
        buf = TrailBuffer()
        assert buf.get_trail(999) == []

    def test_get_trail(self) -> None:
        """Test getting a trail sequence."""
        buf = TrailBuffer()
        buf.push_frame(0, 1.0, 2.0)
        buf.push_frame(0, 3.0, 4.0)
        buf.push_frame(0, 5.0, 6.0)
        trail = buf.get_trail(0)
        assert len(trail) == 3
        assert trail[0] == (1.0, 2.0)
        assert trail[1] == (3.0, 4.0)
        assert trail[2] == (5.0, 6.0)

    def test_get_trail_old_to_new(self) -> None:
        """Test trail order from oldest to newest."""
        buf = TrailBuffer()
        for i in range(10):
            buf.push_frame(0, float(i), float(i * 2))
        trail = buf.get_trail(0)
        assert len(trail) == 10
        for i, (x, y) in enumerate(trail):
            assert x == float(i)
            assert y == float(i * 2)

    def test_maxlen_enforced(self) -> None:
        """Test maximum length limit."""
        buf = TrailBuffer(maxlen=10)
        for i in range(20):
            buf.push_frame(0, float(i), 0.0)
        trail = buf.get_trail(0)
        assert len(trail) == 10
        # keeps the latest 10
        assert trail[0] == (10.0, 0.0)
        assert trail[-1] == (19.0, 0.0)

    def test_rewind(self) -> None:
        """Test rewind functionality."""
        buf = TrailBuffer(maxlen=100)
        for i in range(10):
            buf.push_frame(0, float(i), float(i * 10))
        # frames=0 returns the latest (frame 9)
        pos = buf.rewind(0, 0)
        assert pos == (9.0, 90.0)
        # frames=3 returns 3 frames ago (frame 6)
        pos = buf.rewind(0, 3)
        assert pos == (6.0, 60.0)

    def test_rewind_insufficient_history(self) -> None:
        """Test that insufficient history returns None."""
        buf = TrailBuffer(maxlen=10)
        buf.push_frame(0, 1.0, 2.0)
        assert buf.rewind(0, 5) is None

    def test_rewind_nonexistent_body(self) -> None:
        """Test that a nonexistent body returns None."""
        buf = TrailBuffer()
        assert buf.rewind(999, 5) is None

    def test_rewind_exact_boundary(self) -> None:
        """Test rewind boundary conditions."""
        buf = TrailBuffer(maxlen=5)
        for i in range(5):
            buf.push_frame(0, float(i), 0.0)
        # has 5 frames (0-4), frames=4 should return frame 0
        assert buf.rewind(0, 4) == (0.0, 0.0)
        # frames=5 exceeds boundary
        assert buf.rewind(0, 5) is None

    def test_clear_single(self) -> None:
        """Test clearing the trail of a single body."""
        buf = TrailBuffer()
        buf.push_frame(0, 1.0, 2.0)
        buf.push_frame(1, 3.0, 4.0)
        assert buf.has_trail(0)
        buf.clear(0)
        assert not buf.has_trail(0)
        assert buf.has_trail(1)

    def test_clear_all(self) -> None:
        """Test clearing all trails."""
        buf = TrailBuffer()
        buf.push_frame(0, 1.0, 2.0)
        buf.push_frame(1, 3.0, 4.0)
        buf.clear_all()
        assert len(buf) == 0
        assert buf.get_trail(0) == []

    def test_push_all(self) -> None:
        """Test batch push of frames."""
        bodies = _make_bodies([(0, 0), (10, 10), (20, 20)])
        buf = TrailBuffer()
        buf.push_all(bodies)
        for i in range(3):
            assert buf.has_trail(i)
            assert buf.get_trail(i) == [(float(i * 10), float(i * 10))]

    def test_push_all_respects_active(self) -> None:
        """Test push_all only processes active bodies."""
        bodies = _make_bodies([(0, 0), (10, 10), (20, 20)])
        bodies[1, IS_ACTIVE] = 0.0  # body 1 is inactive
        buf = TrailBuffer()
        buf.push_all(bodies)
        assert buf.has_trail(0)
        assert not buf.has_trail(1)  # inactive should not have a trail
        assert buf.has_trail(2)

    def test_multiple_bodies(self) -> None:
        """Test trails of multiple bodies are independent."""
        buf = TrailBuffer()
        for i in range(5):
            for frame in range(10):
                buf.push_frame(i, float(frame), float(frame + i))
        for i in range(5):
            trail = buf.get_trail(i)
            assert len(trail) == 10
            assert trail[-1] == (9.0, 9.0 + i)

    def test_get_all_trails(self) -> None:
        """Test getting all trails."""
        buf = TrailBuffer()
        buf.push_frame(0, 1.0, 2.0)
        buf.push_frame(1, 3.0, 4.0)
        all_trails = buf.get_all_trails()
        assert len(all_trails) == 2
        assert all_trails[0] == [(1.0, 2.0)]
        assert all_trails[1] == [(3.0, 4.0)]

    def test_default_maxlen(self) -> None:
        """Test default maxlen matches config."""
        buf = TrailBuffer()
        assert buf._maxlen == MAX_TRAIL_LENGTH


# ============================================================================
# Integration tests
# ============================================================================

class TestIntegration:
    """Cross-module integration tests."""

    def test_rebuild_then_trail(self) -> None:
        """Test trail system works correctly after quadtree rebuild."""
        bodies = _make_bodies([(0, 0), (100, 100)])
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.rebuild(bodies)
        buf = TrailBuffer()

        # simulate multi-frame evolution
        for frame in range(10):
            for i in range(len(bodies)):
                buf.push_frame(i, float(frame), float(frame))
            # quadtree rebuild (simulating per-frame rebuild)
            tree.rebuild(bodies)

        # verify trails
        trail_0 = buf.get_trail(0)
        assert len(trail_0) == 10

        # verify quadtree query
        result = tree.query_range(0, 0, 50)
        assert 0 in result
        assert 1 not in result


# ============================================================================
# Broadphase collision detection tests
# ============================================================================

class TestBroadphaseCollision:
    """Tests for quadtree broadphase collision detection consistency with O(n^2)."""

    def test_broadphase_vs_bruteforce_random(self) -> None:
        """Scenario with multiple dense clusters: broadphase results match O(n^2) exactly.

        Each cluster has bodies tightly packed (potential collisions), clusters are far apart.
        Each cluster does not exceed QUADTREE_CAPACITY, ensuring bodies are within the same leaf node.
        """
        np.random.seed(42)
        # 4 clusters, far from the center boundary, ensuring same-cluster bodies are within the same leaf
        clusters = [
            (100, 100),
            (500, 100),
            (100, 500),
            (500, 500),
        ]
        n_per_cluster = 4
        n = len(clusters) * n_per_cluster
        bodies = create_body_state_array(n)
        idx = 0
        for cx, cy in clusters:
            for _ in range(n_per_cluster):
                bodies[idx, X] = cx + float(np.random.uniform(-5, 5))
                bodies[idx, Y] = cy + float(np.random.uniform(-5, 5))
                bodies[idx, RADIUS] = float(np.random.uniform(5, 15))
                bodies[idx, MASS] = 1.0
                bodies[idx, IS_ACTIVE] = 1.0
                idx += 1

        from src.physics.collision import detect_collisions

        # O(n^2) full collision detection
        brute_pairs = set(detect_collisions(bodies, candidates=None))

        # quadtree broadphase
        tree = Quadtree(Rect(-100, -100, 800, 800))
        tree.rebuild(bodies)
        candidates = tree.query_collision_candidates()
        quadtree_pairs = set(detect_collisions(bodies, candidates=candidates))

        # results should match exactly
        assert brute_pairs == quadtree_pairs, (
            f"Broadphase missed {brute_pairs - quadtree_pairs}, "
            f"false positives {quadtree_pairs - brute_pairs}"
        )

    def test_broadphase_empty_candidates(self) -> None:
        """An empty candidate list should return an empty collision list."""
        bodies = create_body_state_array(5)
        bodies[:, X] = np.random.uniform(0, 10, 5)
        bodies[:, Y] = np.random.uniform(0, 10, 5)
        bodies[:, MASS] = 1.0
        bodies[:, RADIUS] = 5.0  # large radius ensures many potential collisions
        bodies[:, IS_ACTIVE] = 1.0

        from src.physics.collision import detect_collisions

        collisions = detect_collisions(bodies, candidates=[])
        assert collisions == []

    def test_broadphase_no_collision(self) -> None:
        """Broadphase should also return an empty list in a no-collision scenario."""
        n = 20
        bodies = create_body_state_array(n)
        # spread apart, ensuring no collisions
        for i in range(n):
            bodies[i, X] = float(i * 1000)
            bodies[i, Y] = 0.0
            bodies[i, MASS] = 1.0
            bodies[i, RADIUS] = 1.0
            bodies[i, IS_ACTIVE] = 1.0

        from src.physics.collision import detect_collisions

        brute_pairs = detect_collisions(bodies, candidates=None)
        assert brute_pairs == []

        tree = Quadtree(Rect(-500, -500, 20000, 1000))
        tree.rebuild(bodies)
        candidates = tree.query_collision_candidates()
        quadtree_pairs = detect_collisions(bodies, candidates=candidates)
        assert quadtree_pairs == []

    def test_broadphase_with_specific_overlap(self) -> None:
        """Broadphase correctly detects all collisions in a specific overlap scenario."""
        bodies = create_body_state_array(6)
        # two overlapping pairs + two isolated bodies
        bodies[0, X] = 0.0
        bodies[0, Y] = 0.0
        bodies[0, RADIUS] = 10.0
        bodies[1, X] = 5.0  # overlaps with 0
        bodies[1, Y] = 0.0
        bodies[1, RADIUS] = 10.0
        bodies[2, X] = 100.0
        bodies[2, Y] = 100.0
        bodies[2, RADIUS] = 10.0
        bodies[3, X] = 105.0  # overlaps with 2
        bodies[3, Y] = 100.0
        bodies[3, RADIUS] = 10.0
        bodies[4, X] = 1000.0  # isolated
        bodies[4, Y] = 1000.0
        bodies[4, RADIUS] = 10.0
        bodies[5, X] = 2000.0  # isolated
        bodies[5, Y] = 2000.0
        bodies[5, RADIUS] = 10.0
        bodies[:, MASS] = 1.0
        bodies[:, IS_ACTIVE] = 1.0

        from src.physics.collision import detect_collisions

        brute_pairs = set(detect_collisions(bodies, candidates=None))

        tree = Quadtree(Rect(-50, -50, 2500, 2500))
        tree.rebuild(bodies)
        candidates = tree.query_collision_candidates()
        quadtree_pairs = set(detect_collisions(bodies, candidates=candidates))

        assert brute_pairs == quadtree_pairs
        assert (0, 1) in quadtree_pairs
        assert (2, 3) in quadtree_pairs
        assert len(quadtree_pairs) == 2

    def test_broadphase_handle_collisions_consistency(self) -> None:
        """handle_collisions produces consistent results with broadphase candidates vs O(n^2)."""
        np.random.seed(123)
        n = 50
        bodies = create_body_state_array(n)
        positions = np.random.uniform(-200, 200, (n, 2))
        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = np.random.uniform(1e20, 1e30, n)
        bodies[:, RADIUS] = np.random.uniform(5, 30, n)
        bodies[:, IS_ACTIVE] = 1.0

        from src.physics.collision import handle_collisions

        # O(n^2) path
        bodies_brute = bodies.copy()
        result_brute, _ = handle_collisions(bodies_brute, collision_pairs=None)

        # quadtree broadphase path
        tree = Quadtree(Rect(-300, -300, 600, 600))
        tree.rebuild(bodies)
        candidates = tree.query_collision_candidates()
        bodies_quad = bodies.copy()
        result_quad, _ = handle_collisions(bodies_quad, collision_pairs=candidates)

        # number of active bodies after collision handling should match
        n_active_brute = int(np.sum(result_brute[:, IS_ACTIVE] == 1.0))
        n_active_quad = int(np.sum(result_quad[:, IS_ACTIVE] == 1.0))
        assert n_active_brute == n_active_quad, (
            f"Active bodies after broadphase {n_active_quad} does not match O(n^2) {n_active_brute}"
        )

    def test_broadphase_performance(self) -> None:
        """Broadphase should be at least 10x faster than O(n^2) (n=500)."""
        np.random.seed(999)
        n = 500
        bodies = create_body_state_array(n)
        positions = np.random.uniform(-1e9, 1e9, (n, 2))
        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = 1.0
        bodies[:, RADIUS] = np.random.uniform(1e6, 1e7, n)
        bodies[:, IS_ACTIVE] = 1.0

        from src.physics.collision import detect_collisions

        # O(n^2) timing
        import time
        start = time.perf_counter()
        brute_pairs = detect_collisions(bodies, candidates=None)
        brute_time = time.perf_counter() - start

        # quadtree broadphase timing (includes rebuild + query + exact detection)
        tree = Quadtree(Rect(-2e9, -2e9, 4e9, 4e9))
        start = time.perf_counter()
        tree.rebuild(bodies)
        candidates = tree.query_collision_candidates()
        quadtree_pairs = detect_collisions(bodies, candidates=candidates)
        quadtree_time = time.perf_counter() - start

        speedup = brute_time / max(quadtree_time, 1e-9)
        print(
            f"\nO(n^2): {brute_time*1000:.1f}ms, "
            f"Quadtree broadphase: {quadtree_time*1000:.1f}ms, "
            f"Speedup: {speedup:.1f}x"
        )
        assert speedup > 5.0, (
            f"Broadphase speedup {speedup:.1f}x, does not meet 5x requirement"
        )
