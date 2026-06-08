"""Barnes-Hut 引力近似计算。

通过四叉树遍历，对满足 s/d < theta 条件的远距离节点使用质心近似，
避免 O(n^2) 的逐一计算，将复杂度降至 O(n log n)。

Typical usage::

    from src.quadtree.barnes_hut import compute_force
    fx, fy = compute_force(root_node, body_id, bodies, theta=0.5)
"""

import math
from typing import Tuple

import numpy as np

from src.config import GRAVITATIONAL_CONSTANT, SOFTENING
from src.core.types import MASS, X, Y

# 预计算软化距离平方
_SOFTENING_SQ = SOFTENING * SOFTENING


def compute_force(
    node: 'QuadtreeNode',
    target_id: int,
    bodies: np.ndarray,
    theta: float,
) -> Tuple[float, float]:
    """使用 Barnes-Hut 近似递归计算目标天体受到的总引力。

    遍历四叉树节点：
    - 如果节点是叶子节点，直接计算节点内所有天体对目标天体的引力。
    - 如果节点是内部节点且满足 s/d < theta (远场条件)，
      用节点质心和总质量近似计算引力，不再递归进入子节点。
    - 如果不满足近似条件，递归到四个子节点。

    Args:
        node: 当前四叉树节点（通常从根节点开始）
        target_id: 目标天体在 bodies 数组中的行索引
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        theta: Barnes-Hut 阈值 (s / d < theta 时使用质心近似)

    Returns:
        (fx, fy) 合力向量 (N)
    """
    tx = float(bodies[target_id, X])
    ty = float(bodies[target_id, Y])
    tm = float(bodies[target_id, MASS])

    if tm <= 0.0:
        return (0.0, 0.0)

    fx, fy = _walk(node, target_id, tx, ty, tm, bodies, theta)
    return (fx, fy)


# ======================================================================
# 内部递归函数
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
    """递归遍历四叉树计算引力。

    Args:
        node: 当前节点
        target_id: 目标天体 ID
        tx, ty: 目标天体坐标
        tm: 目标天体质量
        bodies: 天体状态数组
        theta: Barnes-Hut 阈值

    Returns:
        (fx, fy) 合力
    """
    if node.mass == 0.0 or (not node.divided and len(node.points) == 0):
        return (0.0, 0.0)

    # 计算节点边长和目标到质心的距离
    bx, by, bw, bh = node.boundary
    s = max(bw, bh)
    dx = node.cx - tx
    dy = node.cy - ty
    d = math.sqrt(dx * dx + dy * dy)

    if node.divided:
        # 内部节点：判断是否可以用质心近似
        if d > 0.0 and s / d < theta:
            # 远场条件满足，使用质心近似
            return _compute_force_to_mass(tm, node.mass, dx, dy, d)
        else:
            # 不满足近似条件，递归子节点
            fx, fy = 0.0, 0.0
            for child in (node.nw, node.ne, node.sw, node.se):
                if child is not None and child.mass > 0.0:
                    cfx, cfy = _walk(child, target_id, tx, ty, tm, bodies, theta)
                    fx += cfx
                    fy += cfy
            return (fx, fy)
    else:
        # 叶子节点：直接计算所有点的引力（四点合并为质心计算或逐一计算）
        # 如果叶子内有多个点且远场条件满足，仍可用节点质心
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
    """计算目标天体与节点质心之间的引力。

    Args:
        target_mass: 目标天体质量
        node_mass: 节点总质量
        dx: 目标到质心的 x 分量
        dy: 目标到质心的 y 分量
        d: 目标到质心的距离

    Returns:
        (fx, fy) 引力分量
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
