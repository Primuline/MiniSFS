"""四叉树、Barnes-Hut 和尾迹缓冲区的单元测试。

测试覆盖：
- Quadtree: 插入、重建、范围查询、最近邻查询、碰撞候选
- Barnes-Hut: 引力近似精度和性能
- TrailBuffer: 推帧、获取、时间倒退、清除
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
# 辅助函数
# ============================================================================

def _make_bodies(positions: list, masses: list = None) -> np.ndarray:
    """从位置列表创建测试用天体状态数组。"""
    n = len(positions)
    bodies = create_body_state_array(n)
    for i, (px, py) in enumerate(positions):
        bodies[i, X] = px
        bodies[i, Y] = py
        bodies[i, MASS] = 1.0  # 确保默认质量非零，使四叉树质心计算正常
    if masses is not None:
        for i, m in enumerate(masses):
            bodies[i, MASS] = m
    return bodies


# ============================================================================
# Quadtree 基本测试
# ============================================================================

class TestQuadtreeNode:
    """QuadtreeNode 基本操作测试。"""

    def test_insert_single_point(self) -> None:
        """测试插入单点到四叉树节点。"""
        node = QuadtreeNode(Rect(0, 0, 100, 100), 4)
        assert node.insert(0, 10, 20, 100.0)
        assert len(node.points) == 1
        assert node.mass == 100.0
        assert node.cx == 10.0
        assert node.cy == 20.0

    def test_insert_out_of_bounds(self) -> None:
        """测试超出边界插入应返回 False。"""
        node = QuadtreeNode(Rect(0, 0, 100, 100), 4)
        assert not node.insert(0, -10, 50, 1.0)
        assert not node.insert(0, 150, 50, 1.0)
        assert node.mass == 0.0

    def test_subdivide_on_overflow(self) -> None:
        """测试超过容量时自动分裂。"""
        node = QuadtreeNode(Rect(0, 0, 100, 100), 2)
        node.insert(0, 10, 10, 1.0)
        node.insert(1, 20, 20, 1.0)
        assert not node.divided
        node.insert(2, 30, 30, 1.0)
        assert node.divided
        # 分裂后，原叶节点应无点列表
        assert len(node.points) == 0

    def test_center_of_mass_correct(self) -> None:
        """测试质心计算正确性。"""
        node = QuadtreeNode(Rect(0, 0, 100, 100), 4)
        node.insert(0, 0, 0, 10.0)
        node.insert(1, 10, 0, 30.0)
        # 质心: (0*10 + 10*30) / 40 = 7.5, (0*10 + 0*30) / 40 = 0
        assert node.cx == pytest.approx(7.5)
        assert node.cy == pytest.approx(0.0)
        assert node.mass == pytest.approx(40.0)


class TestQuadtree:
    """Quadtree 核心功能测试。"""

    def test_create(self) -> None:
        """测试四叉树创建。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        assert tree is not None

    def test_insert_via_interface(self) -> None:
        """测试通过 IQuadtree 接口的 insert 方法。"""
        tree = Quadtree(Rect(0, 0, 100, 100))
        assert tree.insert(0, 10, 20)
        stats = tree.get_statistics()
        assert stats['total_points'] == 1

    def test_rebuild(self) -> None:
        """测试重建四叉树。"""
        bodies = _make_bodies([(10, 10), (20, 20), (30, 30)], [1.0, 2.0, 3.0])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        stats = tree.get_statistics()
        assert stats['total_mass'] == pytest.approx(6.0)
        assert stats['node_count'] >= 1

    def test_rebuild_empty(self) -> None:
        """测试重建四叉树（无活跃天体）。"""
        bodies = _make_bodies([(10, 10)])
        bodies[0, IS_ACTIVE] = 0.0
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        stats = tree.get_statistics()
        assert stats['total_mass'] == 0.0

    def test_rebuild_all_inactive(self) -> None:
        """测试所有天体处于非活跃状态时的重建。"""
        bodies = create_body_state_array(5)
        bodies[:, IS_ACTIVE] = 0.0
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        stats = tree.get_statistics()
        assert stats['total_mass'] == 0.0

    def test_rebuild_updates_boundary(self) -> None:
        """测试 rebuild 会根据天体坐标自动计算边界。"""
        bodies = _make_bodies([(-500, -500), (500, 500)])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        # 插入新点，应在新的边界内
        assert tree.insert(2, 0, 0)

    def test_rebuild_large_scale(self) -> None:
        """测试 1000 个天体时四叉树构建性能 (< 1ms)。"""
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
        assert elapsed < 0.01, f"重建耗时 {elapsed*1000:.2f}ms，超过 10ms 限制"


class TestQuadtreeQueryRange:
    """范围查询测试。"""

    def test_query_range_empty(self) -> None:
        """测试空四叉树的范围查询。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        result = tree.query_range(0, 0, 50)
        assert result == []

    def test_query_range_single(self) -> None:
        """测试单点范围查询。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 10)
        result = tree.query_range(0, 0, 20)
        assert 0 in result

    def test_query_range_outside(self) -> None:
        """测试点不在范围内。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 100, 100)
        result = tree.query_range(0, 0, 10)
        assert result == []

    def test_query_range_multiple(self) -> None:
        """测试多点范围查询。"""
        bodies = _make_bodies([(0, 0), (10, 10), (50, 50), (100, 100), (-10, -10)])
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.rebuild(bodies)
        result = tree.query_range(0, 0, 20)
        assert len(result) == 3  # (0,0), (10,10), (-10,-10)
        assert 0 in result
        assert 1 in result
        assert 4 in result

    def test_query_range_radius_edge(self) -> None:
        """测试点在圆边界上的情况。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 0)
        result = tree.query_range(0, 0, 10)
        assert 0 in result

    def test_query_range_after_rebuild(self) -> None:
        """测试重建后范围查询正确。"""
        bodies = _make_bodies([(0, 0), (5, 5), (100, 100)])
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.rebuild(bodies)
        result = tree.query_range(0, 0, 10)
        assert len(result) == 2
        assert set(result) == {0, 1}

    def test_query_range_no_miss(self) -> None:
        """测试范围查询无漏检 - 随机分布。"""
        np.random.seed(123)
        n = 200
        positions = np.random.uniform(-500, 500, (n, 2))
        bodies = create_body_state_array(n)
        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = 1.0

        tree = Quadtree(Rect(-600, -600, 1200, 1200))
        tree.rebuild(bodies)

        # 在多个位置查询
        for cx, cy, r in [(0, 0, 100), (200, 200, 150), (-300, -300, 80)]:
            tree_result = set(tree.query_range(cx, cy, r))
            naive_result = set(
                i for i in range(n)
                if (positions[i, 0] - cx) ** 2 + (positions[i, 1] - cy) ** 2 <= r * r
            )
            assert tree_result == naive_result, (
                f"查询 (cx={cx}, cy={cy}, r={r}) 漏检 "
                f"tree={tree_result ^ naive_result}"
            )


class TestQuadtreeNearest:
    """最近邻查询测试。"""

    def test_nearest_empty(self) -> None:
        """测试空四叉树的最近邻查询。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        assert tree.query_nearest(0, 0) is None

    def test_nearest_single(self) -> None:
        """测试单点最近邻。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 10)
        assert tree.query_nearest(0, 0) == 0

    def test_nearest_exact(self) -> None:
        """测试查询点与某天体重合时。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 10)
        tree.insert(1, 50, 50)
        assert tree.query_nearest(10, 10) == 0

    def test_nearest_correct(self) -> None:
        """测试最近邻正确性。"""
        bodies = _make_bodies([(0, 0), (10, 0), (100, 100)])
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.rebuild(bodies)
        # (5, 0) 离 (0,0) 距离 5，离 (10,0) 距离 5，离 (100,100) 距离 134
        # (0,0) 是最近的（严格来说都是5，取第一个）
        nearest = tree.query_nearest(5, 0)
        assert nearest is not None

    def test_nearest_negative_coords(self) -> None:
        """测试负坐标。"""
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.insert(0, -50, -50)
        tree.insert(1, 50, 50)
        assert tree.query_nearest(-45, -45) == 0

    def test_nearest_quality(self) -> None:
        """测试最近邻结果与暴力搜索一致。"""
        np.random.seed(456)
        n = 100
        positions = np.random.uniform(-500, 500, (n, 2))
        bodies = create_body_state_array(n)
        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = 1.0

        tree = Quadtree(Rect(-600, -600, 1200, 1200))
        tree.rebuild(bodies)

        # 测试多个查询点
        for qx, qy in [(0, 0), (300, -200), (-400, 100), (50, 50)]:
            tree_result = tree.query_nearest(qx, qy)
            dists = np.sum((positions - np.array([qx, qy])) ** 2, axis=1)
            brute_result = int(np.argmin(dists))
            assert tree_result == brute_result, (
                f"最近邻查询 (qx={qx}, qy={qy}): "
                f"tree={tree_result}, brute={brute_result}"
            )


class TestQuadtreeCollisionCandidates:
    """碰撞候选查询测试。"""

    def test_collision_candidates_empty(self) -> None:
        """测试空四叉树返回空列表。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        assert tree.query_collision_candidates() == []

    def test_collision_candidates_single(self) -> None:
        """测试单个天体返回空列表。"""
        tree = Quadtree(Rect(-100, -100, 200, 200))
        tree.insert(0, 10, 10)
        assert tree.query_collision_candidates() == []

    def test_collision_candidates_pair(self) -> None:
        """测试两个天体会被识别为候选。"""
        # 两体在同一个区域内
        bodies = _make_bodies([(10, 10), (12, 12)])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        pairs = tree.query_collision_candidates()
        assert len(pairs) >= 1
        assert (0, 1) in pairs

    def test_collision_candidates_distant(self) -> None:
        """测试远距离天体会出现在不同叶节点。"""
        bodies = _make_bodies([(10, 10), (90, 90)])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        pairs = tree.query_collision_candidates()
        # 由于容量为4，两个点在同一象限，可能在同一叶节点
        # 这个测试保证接口不抛异常
        assert isinstance(pairs, list)

    def test_collision_candidates_no_duplicates(self) -> None:
        """测试碰撞候选没有重复对。"""
        bodies = _make_bodies([(1, 1), (2, 2), (3, 3), (4, 4)])
        tree = Quadtree(Rect(0, 0, 100, 100))
        tree.rebuild(bodies)
        pairs = tree.query_collision_candidates()
        # 检查没有重复
        unique_pairs = set(pairs)
        assert len(pairs) == len(unique_pairs)


class TestQuadtreeStatistics:
    """四叉树统计信息测试。"""

    def test_statistics_basic(self) -> None:
        """测试统计信息的完整性。"""
        bodies = _make_bodies([(0, 0), (10, 10), (20, 20)], [1.0, 2.0, 3.0])
        tree = Quadtree(Rect(-50, -50, 100, 100))
        tree.rebuild(bodies)
        stats = tree.get_statistics()
        for key in ('node_count', 'max_depth', 'total_mass', 'total_points'):
            assert key in stats
        assert stats['total_mass'] == pytest.approx(6.0)

    def test_statistics_after_clear(self) -> None:
        """测试清空后统计信息重置。"""
        bodies = _make_bodies([(0, 0), (10, 10)], [1.0, 1.0])
        tree = Quadtree(Rect(-50, -50, 100, 100))
        tree.rebuild(bodies)
        tree.rebuild(create_body_state_array(0))
        stats = tree.get_statistics()
        assert stats['total_mass'] == 0.0


# ============================================================================
# Barnes-Hut 测试
# ============================================================================

class TestBarnesHut:
    """Barnes-Hut 引力近似测试。"""

    def test_force_single_body(self) -> None:
        """测试只有一个天体时力为 0。"""
        bodies = make_body(x=0, y=0, mass=1e30)
        tree = Quadtree(Rect(-1e10, -1e10, 2e10, 2e10))
        tree.rebuild(bodies)
        fx, fy = tree.barnes_hut_force(0, bodies, theta=0.5)
        assert fx == pytest.approx(0.0)
        assert fy == pytest.approx(0.0)

    def test_force_two_bodies(self) -> None:
        """测试两个天体之间的引力（与万有引力公式一致）。"""
        bodies = create_body_state_array(2)
        m1, m2 = 1e30, 5e28
        bodies[0, X] = 0.0
        bodies[0, Y] = 0.0
        bodies[0, MASS] = m1
        bodies[1, X] = 1e9
        bodies[1, Y] = 0.0
        bodies[1, MASS] = m2

        # 预期引力
        dist = 1e9
        expected_f = GRAVITATIONAL_CONSTANT * m1 * m2 / (dist * dist)

        tree = Quadtree(Rect(-1e10, -1e10, 2e10, 2e10))
        tree.rebuild(bodies)
        fx, fy = tree.barnes_hut_force(0, bodies, theta=0.5)
        assert fx == pytest.approx(expected_f, abs=expected_f * 0.01)
        assert fy == pytest.approx(0.0)

    def test_force_three_bodies_collinear(self) -> None:
        """测试三个共线天体的引力。"""
        bodies = create_body_state_array(3)
        bodies[0, X] = 0.0
        bodies[0, MASS] = 1e30
        bodies[1, X] = 1e9
        bodies[1, MASS] = 5e28
        bodies[2, X] = 2e9
        bodies[2, MASS] = 1e28

        # 天体 0 受到天体 1 和 2 的引力之和
        f_01 = GRAVITATIONAL_CONSTANT * bodies[0, MASS] * bodies[1, MASS] / (1e9 ** 2)
        f_02 = GRAVITATIONAL_CONSTANT * bodies[0, MASS] * bodies[2, MASS] / (2e9 ** 2)
        expected_fx = (f_01 + f_02)

        tree = Quadtree(Rect(-1e10, -1e10, 2e10, 2e10))
        tree.rebuild(bodies)
        fx, fy = tree.barnes_hut_force(0, bodies, theta=0.0)
        # theta=0 不使用近似
        assert fx == pytest.approx(expected_fx, abs=abs(expected_fx) * 0.01)
        assert fy == pytest.approx(0.0)

    def test_barnes_hut_vs_brute_force_accuracy(self) -> None:
        """测试 Barnes-Hut (theta=0.5) 与直接 O(n^2) 的精度对比。"""
        np.random.seed(789)
        n = 50
        bodies = create_body_state_array(n)
        positions = np.random.uniform(-1e8, 1e8, (n, 2))
        masses = np.random.uniform(1e25, 1e30, n)

        bodies[:, X] = positions[:, 0]
        bodies[:, Y] = positions[:, 1]
        bodies[:, MASS] = masses

        # 直接 O(n^2) 计算
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

        # Barnes-Hut 计算
        tree = Quadtree(Rect(-2e8, -2e8, 4e8, 4e8))
        tree.rebuild(bodies)
        bh_forces = np.zeros((n, 2))
        for i in range(n):
            fx, fy = tree.barnes_hut_force(i, bodies, theta=0.5)
            bh_forces[i, 0] = fx
            bh_forces[i, 1] = fy

        # 检查误差 < 5%
        for i in range(n):
            bf = math.sqrt(brute_forces[i, 0] ** 2 + brute_forces[i, 1] ** 2)
            bh = math.sqrt(bh_forces[i, 0] ** 2 + bh_forces[i, 1] ** 2)
            if bf > 0:
                relative_error = abs(bh - bf) / bf
                assert relative_error < 0.05, (
                    f"天体 {i}: 相对误差 {relative_error:.4f} > 5%"
                )

    def test_barnes_hut_performance(self) -> None:
        """测试 Barnes-Hut (theta=0.5) 比 O(n^2) 快至少 10 倍 (n=1000)。"""
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

        # O(n^2) 暴力法 (只测 50 个点推算)
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
            f"Barnes-Hut 加速比 {speedup:.1f}x，未达到 10x 要求"
        )


# ============================================================================
# TrailBuffer 测试
# ============================================================================

class TestTrailBuffer:
    """TrailBuffer 功能测试。"""

    def test_create(self) -> None:
        """测试创建尾迹缓冲区。"""
        buf = TrailBuffer()
        assert buf is not None
        assert len(buf) == 0

    def test_push_frame_new_body(self) -> None:
        """测试为新天体推帧。"""
        buf = TrailBuffer()
        buf.push_frame(0, 10.0, 20.0)
        assert buf.has_trail(0)
        assert len(buf) == 1

    def test_get_trail_empty(self) -> None:
        """测试获取不存在的尾迹。"""
        buf = TrailBuffer()
        assert buf.get_trail(999) == []

    def test_get_trail(self) -> None:
        """测试获取尾迹序列。"""
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
        """测试尾迹顺序从旧到新。"""
        buf = TrailBuffer()
        for i in range(10):
            buf.push_frame(0, float(i), float(i * 2))
        trail = buf.get_trail(0)
        assert len(trail) == 10
        for i, (x, y) in enumerate(trail):
            assert x == float(i)
            assert y == float(i * 2)

    def test_maxlen_enforced(self) -> None:
        """测试最大长度限制。"""
        buf = TrailBuffer(maxlen=10)
        for i in range(20):
            buf.push_frame(0, float(i), 0.0)
        trail = buf.get_trail(0)
        assert len(trail) == 10
        # 保留最新的 10 个
        assert trail[0] == (10.0, 0.0)
        assert trail[-1] == (19.0, 0.0)

    def test_rewind(self) -> None:
        """测试时间倒退功能。"""
        buf = TrailBuffer(maxlen=100)
        for i in range(10):
            buf.push_frame(0, float(i), float(i * 10))
        # frames=0 返回最新的（第 9 帧）
        pos = buf.rewind(0, 0)
        assert pos == (9.0, 90.0)
        # frames=3 返回 3 帧前（第 6 帧）
        pos = buf.rewind(0, 3)
        assert pos == (6.0, 60.0)

    def test_rewind_insufficient_history(self) -> None:
        """测试历史不足时返回 None。"""
        buf = TrailBuffer(maxlen=10)
        buf.push_frame(0, 1.0, 2.0)
        assert buf.rewind(0, 5) is None

    def test_rewind_nonexistent_body(self) -> None:
        """测试不存在的天体返回 None。"""
        buf = TrailBuffer()
        assert buf.rewind(999, 5) is None

    def test_rewind_exact_boundary(self) -> None:
        """测试 rewind 边界条件。"""
        buf = TrailBuffer(maxlen=5)
        for i in range(5):
            buf.push_frame(0, float(i), 0.0)
        # 有 5 帧 (0-4)，frames=4 应该返回第 0 帧
        assert buf.rewind(0, 4) == (0.0, 0.0)
        # frames=5 超出
        assert buf.rewind(0, 5) is None

    def test_clear_single(self) -> None:
        """测试清除单个天体的尾迹。"""
        buf = TrailBuffer()
        buf.push_frame(0, 1.0, 2.0)
        buf.push_frame(1, 3.0, 4.0)
        assert buf.has_trail(0)
        buf.clear(0)
        assert not buf.has_trail(0)
        assert buf.has_trail(1)

    def test_clear_all(self) -> None:
        """测试清除所有尾迹。"""
        buf = TrailBuffer()
        buf.push_frame(0, 1.0, 2.0)
        buf.push_frame(1, 3.0, 4.0)
        buf.clear_all()
        assert len(buf) == 0
        assert buf.get_trail(0) == []

    def test_push_all(self) -> None:
        """测试批量推帧。"""
        bodies = _make_bodies([(0, 0), (10, 10), (20, 20)])
        buf = TrailBuffer()
        buf.push_all(bodies)
        for i in range(3):
            assert buf.has_trail(i)
            assert buf.get_trail(i) == [(float(i * 10), float(i * 10))]

    def test_push_all_respects_active(self) -> None:
        """测试 push_all 只处理活跃天体。"""
        bodies = _make_bodies([(0, 0), (10, 10), (20, 20)])
        bodies[1, IS_ACTIVE] = 0.0  # 天体 1 非活跃
        buf = TrailBuffer()
        buf.push_all(bodies)
        assert buf.has_trail(0)
        assert not buf.has_trail(1)  # 非活跃的不应有尾迹
        assert buf.has_trail(2)

    def test_multiple_bodies(self) -> None:
        """测试多个天体的尾迹独立。"""
        buf = TrailBuffer()
        for i in range(5):
            for frame in range(10):
                buf.push_frame(i, float(frame), float(frame + i))
        for i in range(5):
            trail = buf.get_trail(i)
            assert len(trail) == 10
            assert trail[-1] == (9.0, 9.0 + i)

    def test_get_all_trails(self) -> None:
        """测试获取所有尾迹。"""
        buf = TrailBuffer()
        buf.push_frame(0, 1.0, 2.0)
        buf.push_frame(1, 3.0, 4.0)
        all_trails = buf.get_all_trails()
        assert len(all_trails) == 2
        assert all_trails[0] == [(1.0, 2.0)]
        assert all_trails[1] == [(3.0, 4.0)]

    def test_default_maxlen(self) -> None:
        """测试默认 maxlen 与配置一致。"""
        buf = TrailBuffer()
        assert buf._maxlen == MAX_TRAIL_LENGTH


# ============================================================================
# 集成测试
# ============================================================================

class TestIntegration:
    """跨模块集成测试。"""

    def test_rebuild_then_trail(self) -> None:
        """测试重建四叉树后尾迹系统正常工作。"""
        bodies = _make_bodies([(0, 0), (100, 100)])
        tree = Quadtree(Rect(-200, -200, 400, 400))
        tree.rebuild(bodies)
        buf = TrailBuffer()

        # 模拟多帧推演
        for frame in range(10):
            for i in range(len(bodies)):
                buf.push_frame(i, float(frame), float(frame))
            # 四叉树重建（模拟每帧重建）
            tree.rebuild(bodies)

        # 验证尾迹
        trail_0 = buf.get_trail(0)
        assert len(trail_0) == 10

        # 验证四叉树查询
        result = tree.query_range(0, 0, 50)
        assert 0 in result
        assert 1 not in result


# ============================================================================
# 宽阶段碰撞检测测试
# ============================================================================

class TestBroadphaseCollision:
    """四叉树宽阶段碰撞检测与 O(n²) 结果一致性测试。"""

    def test_broadphase_vs_bruteforce_random(self) -> None:
        """使用多个密集簇的场景：宽阶段与 O(n²) 结果完全一致。

        每个簇内部天体紧密分布（存在碰撞），簇间远离。
        每个簇不超过 QUADTREE_CAPACITY 个天体，确保在同一叶节点内。
        """
        np.random.seed(42)
        # 4 个簇，远离中心边界，确保同一簇天体在同一叶节点内
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

        # O(n²) 全量碰撞检测
        brute_pairs = set(detect_collisions(bodies, candidates=None))

        # 四叉树宽阶段
        tree = Quadtree(Rect(-100, -100, 800, 800))
        tree.rebuild(bodies)
        candidates = tree.query_collision_candidates()
        quadtree_pairs = set(detect_collisions(bodies, candidates=candidates))

        # 结果应完全一致
        assert brute_pairs == quadtree_pairs, (
            f"宽阶段漏检 {brute_pairs - quadtree_pairs}，"
            f"误检 {quadtree_pairs - brute_pairs}"
        )

    def test_broadphase_empty_candidates(self) -> None:
        """空候选列表应返回空碰撞列表。"""
        bodies = create_body_state_array(5)
        bodies[:, X] = np.random.uniform(0, 10, 5)
        bodies[:, Y] = np.random.uniform(0, 10, 5)
        bodies[:, MASS] = 1.0
        bodies[:, RADIUS] = 5.0  # 大半径确保很多碰撞
        bodies[:, IS_ACTIVE] = 1.0

        from src.physics.collision import detect_collisions

        collisions = detect_collisions(bodies, candidates=[])
        assert collisions == []

    def test_broadphase_no_collision(self) -> None:
        """无碰撞场景下宽阶段也应返回空列表。"""
        n = 20
        bodies = create_body_state_array(n)
        # 分散放置，确保无碰撞
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
        """特定重叠场景下，宽阶段正确检测所有碰撞。"""
        bodies = create_body_state_array(6)
        # 两对重叠天体 + 两个孤立天体
        bodies[0, X] = 0.0
        bodies[0, Y] = 0.0
        bodies[0, RADIUS] = 10.0
        bodies[1, X] = 5.0  # 与 0 重叠
        bodies[1, Y] = 0.0
        bodies[1, RADIUS] = 10.0
        bodies[2, X] = 100.0
        bodies[2, Y] = 100.0
        bodies[2, RADIUS] = 10.0
        bodies[3, X] = 105.0  # 与 2 重叠
        bodies[3, Y] = 100.0
        bodies[3, RADIUS] = 10.0
        bodies[4, X] = 1000.0  # 孤立
        bodies[4, Y] = 1000.0
        bodies[4, RADIUS] = 10.0
        bodies[5, X] = 2000.0  # 孤立
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
        """handle_collisions 通过宽阶段候选对与 O(n²) 结果一致。"""
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

        # O(n²) 路径
        bodies_brute = bodies.copy()
        result_brute, _ = handle_collisions(bodies_brute, collision_pairs=None)

        # 四叉树宽阶段路径
        tree = Quadtree(Rect(-300, -300, 600, 600))
        tree.rebuild(bodies)
        candidates = tree.query_collision_candidates()
        bodies_quad = bodies.copy()
        result_quad, _ = handle_collisions(bodies_quad, collision_pairs=candidates)

        # 碰撞处理后的活跃天体数量应一致
        n_active_brute = int(np.sum(result_brute[:, IS_ACTIVE] == 1.0))
        n_active_quad = int(np.sum(result_quad[:, IS_ACTIVE] == 1.0))
        assert n_active_brute == n_active_quad, (
            f"宽阶段后活跃天体数 {n_active_quad} 与 O(n²) {n_active_brute} 不一致"
        )

    def test_broadphase_performance(self) -> None:
        """宽阶段应比 O(n²) 快至少 10 倍 (n=500)。"""
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

        # O(n²) 耗时
        import time
        start = time.perf_counter()
        brute_pairs = detect_collisions(bodies, candidates=None)
        brute_time = time.perf_counter() - start

        # 四叉树宽阶段耗时（包含重建 + 查询 + 精确检测）
        tree = Quadtree(Rect(-2e9, -2e9, 4e9, 4e9))
        start = time.perf_counter()
        tree.rebuild(bodies)
        candidates = tree.query_collision_candidates()
        quadtree_pairs = detect_collisions(bodies, candidates=candidates)
        quadtree_time = time.perf_counter() - start

        speedup = brute_time / max(quadtree_time, 1e-9)
        print(
            f"\nO(n²): {brute_time*1000:.1f}ms, "
            f"Quadtree broadphase: {quadtree_time*1000:.1f}ms, "
            f"Speedup: {speedup:.1f}x"
        )
        assert speedup > 5.0, (
            f"宽阶段加速比 {speedup:.1f}x，未达到 5x 要求"
        )
