"""四叉树空间划分实现。

提供空间划分加速引力计算和碰撞检测。
每帧重建 (clear + insert all)，支持圆形范围查询、最近邻查询、碰撞候选查询。

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
    """四叉树节点，存储边界、子节点指针、质心统计与点列表。

    叶子节点存储实际点列表；内部节点在分裂后清空点列表并创建四个子节点。
    每个节点维护子树总质量 (mass) 和质心 (cx, cy)，供 Barnes-Hut 近似使用。

    Attributes:
        boundary: 节点覆盖的轴对齐矩形区域
        capacity: 分裂阈值（点数超过此值则分裂）
        points: 叶节点内的点列表，每项为 (body_id, x, y, mass)
        nw, ne, sw, se: 四个子节点（仅当 divided=True 时有效）
        divided: 是否已分裂为子节点
        mass: 子树总质量
        cx: 子树质心 x 坐标
        cy: 子树质心 y 坐标
    """

    __slots__ = (
        'boundary', 'capacity', 'points',
        'nw', 'ne', 'sw', 'se', 'divided',
        'mass', 'cx', 'cy',
    )

    def __init__(self, boundary: Rect, capacity: int) -> None:
        """初始化四叉树节点。

        Args:
            boundary: 节点覆盖的矩形区域
            capacity: 分裂阈值
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
        """向节点或其子节点插入一个点。

        Args:
            body_id: 天体在 bodies 数组中的行索引
            x: x 坐标
            y: y 坐标
            mass: 天体质量

        Returns:
            插入成功返回 True，超出节点边界返回 False
        """
        bx, by, bw, bh = self.boundary
        if not (bx <= x <= bx + bw and by <= y <= by + bh):
            return False

        # 更新节点质心统计
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
        """将本节点分裂为四个子节点，并将已有节点重新分配。"""
        x, y, w, h = self.boundary
        hw = w * 0.5
        hh = h * 0.5

        self.nw = QuadtreeNode(Rect(x, y, hw, hh), self.capacity)
        self.ne = QuadtreeNode(Rect(x + hw, y, hw, hh), self.capacity)
        self.sw = QuadtreeNode(Rect(x, y + hh, hw, hh), self.capacity)
        self.se = QuadtreeNode(Rect(x + hw, y + hh, hw, hh), self.capacity)
        self.divided = True

        # 重新分配已有节点到子节点
        existing_points = self.points
        self.points = []
        for pid, px, py, pmass in existing_points:
            self._insert_to_child(pid, px, py, pmass)

    def _insert_to_child(self, body_id: int, x: float, y: float, mass: float) -> bool:
        """将点插入到合适的子节点。"""
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
        """递归查询圆形区域内的 body_id，追加到 result。

        Args:
            cx: 圆心 x
            cy: 圆心 y
            radius: 圆半径
            result: 输出列表
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
        """递归查找距离 (x, y) 最近的天体 ID。

        Args:
            x: 查询点 x 坐标
            y: 查询点 y 坐标

        Returns:
            最近的天体 ID，无天体时返回 None
        """
        best_id: Optional[int] = None
        best_dist_sq: float = float('inf')

        def _search(node: QuadtreeNode) -> None:
            nonlocal best_id, best_dist_sq

            if node.mass == 0.0:
                return

            # 计算查询点到节点边界的最小距离，用于剪枝
            bx, by, bw, bh = node.boundary
            dx = max(bx - x, 0.0, x - (bx + bw))
            dy = max(by - y, 0.0, y - (by + bh))
            min_dist_sq = dx * dx + dy * dy
            if min_dist_sq >= best_dist_sq:
                return

            if node.divided:
                # 按到子节点中心的距离排序，先搜索更近的
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
        """收集共享同一叶节点的天体对（碰撞候选）。

        Args:
            pairs: 输出集合，每项为 (min_id, max_id)
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
# Quadtree 主类
# ============================================================================


class Quadtree(IQuadtree):
    """四叉树实现，实现 IQuadtree 接口。

    支持动态插入、全量重建、圆形范围查询、最近邻查询和 Barnes-Hut 引力近似。

    Args:
        boundary: 根节点覆盖的矩形区域
        capacity: 每个节点最大容量 (默认 QUADTREE_CAPACITY)
    """

    def __init__(self, boundary: Rect, capacity: int = QUADTREE_CAPACITY) -> None:
        self._capacity = capacity
        self._root = QuadtreeNode(boundary, capacity)

    # ------------------------------------------------------------------
    # IQuadtree 接口方法
    # ------------------------------------------------------------------

    def insert(self, body_id: int, x: float, y: float) -> bool:
        """插入天体到四叉树。

        Note:
            注意此方法使用 mass=0 插入，将不影响质心计算。
            建议通过 rebuild() 批量插入以正确统计质量。

        Args:
            body_id: 天体在 bodies 数组中的行索引
            x: x 坐标
            y: y 坐标

        Returns:
            插入成功返回 True，超出边界返回 False
        """
        return self._root.insert(body_id, x, y, 1.0)

    def rebuild(self, bodies: np.ndarray) -> None:
        """清空并重建四叉树。

        根据所有活跃天体的位置自动计算边界矩形（正方形，10% 边距）。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
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
        size *= 1.1  # 10% 边距
        center_x = (min_x + max_x) * 0.5
        center_y = (min_y + max_y) * 0.5

        boundary = Rect(center_x - size * 0.5, center_y - size * 0.5, size, size)
        self._root = QuadtreeNode(boundary, self._capacity)

        for i in range(n_active):
            body_id = int(active_indices[i])
            self._root.insert(body_id, float(xs[i]), float(ys[i]), float(masses[i]))

    def query_range(self, x: float, y: float, radius: float) -> List[int]:
        """范围查询：返回指定圆形区域内的天体 ID 列表。

        Args:
            x: 圆心 x 坐标
            y: 圆心 y 坐标
            radius: 圆形半径

        Returns:
            区域内的天体 ID 列表
        """
        result: List[int] = []
        self._root.query_range(x, y, radius, result)
        return result

    def query_nearest(self, x: float, y: float) -> Optional[int]:
        """最近邻查询：返回离指定坐标最近的天体 ID。

        Args:
            x: 查询点 x 坐标
            y: 查询点 y 坐标

        Returns:
            最近的天体 ID，无天体时返回 None
        """
        return self._root.query_nearest(x, y)

    def barnes_hut_force(
        self, body_id: int, bodies: np.ndarray, theta: float
    ) -> Tuple[float, float]:
        """使用 Barnes-Hut 近似计算指定天体受到的总引力。

        将计算委托给 barnes_hut.compute_force 函数。

        Args:
            body_id: 目标天体的 ID
            bodies: 所有天体的状态数组
            theta: Barnes-Hut 阈值 (通常 0.5)

        Returns:
            (fx, fy) 合力向量 (N)
        """
        from src.quadtree.barnes_hut import compute_force
        return compute_force(self._root, body_id, bodies, theta)

    # ------------------------------------------------------------------
    # 扩展方法（非接口）
    # ------------------------------------------------------------------

    def query_collision_candidates(self) -> List[Tuple[int, int]]:
        """返回共享同一叶节点的天体对，作为碰撞检测的候选。

        这是碰撞检测宽阶段 (broad phase) 的一部分：
        将树上共叶节点的天体对返回，后续进行精确碰撞检测。

        Returns:
            (id1, id2) 列表，保证 id1 < id2
        """
        pairs: set = set()
        self._root.collect_pairs(pairs)
        return list(pairs)

    def get_statistics(self) -> dict:
        """返回四叉树统计信息。

        Returns:
            包含节点数、总质量和深度等信息的字典
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
# 内部工具函数
# ============================================================================


def _circle_intersects_rect(
    cx: float, cy: float, r: float, rect: Rect
) -> bool:
    """检测圆形是否与轴对齐矩形相交。

    找到矩形上离圆心最近的点，检测距离是否 <= r。

    Args:
        cx: 圆心 x
        cy: 圆心 y
        r: 圆半径
        rect: 矩形

    Returns:
        相交返回 True
    """
    closest_x = max(rect.x, min(cx, rect.x + rect.w))
    closest_y = max(rect.y, min(cy, rect.y + rect.h))
    dx = cx - closest_x
    dy = cy - closest_y
    return dx * dx + dy * dy <= r * r


def _point_dist_sq(x1: float, y1: float, x2: float, y2: float) -> float:
    """返回两点之间的平方距离。"""
    dx = x1 - x2
    dy = y1 - y2
    return dx * dx + dy * dy
