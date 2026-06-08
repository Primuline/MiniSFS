"""碰撞检测与响应模块。

支持两种碰撞处理策略:
    - 弹性碰撞: 质量加权速度交换，适用于同等级质量的天体
    - 合并碰撞: 小质量天体被大质量天体吸收，适用于大质量差场景

碰撞事件返回给调用方，供渲染器做特效（闪光、碎裂）。

用法::

    from src.physics.collision import detect_collisions, resolve_elastic, resolve_merge
"""

from typing import Dict, List, Tuple

import numpy as np

from src.core.types import (
    IS_ACTIVE,
    IS_STATIC,
    MASS,
    RADIUS,
    VX,
    VY,
    X,
    Y,
)

# 碰撞事件描述
# 格式: {"type": "elastic"|"merge", "id_a": int, "id_b": int,
#        "pos_x": float, "pos_y": float, "vx_a": float, "vy_a": float, ...}
CollisionEvent = Dict[str, float | int | str]


def detect_collisions(bodies: np.ndarray) -> List[Tuple[int, int]]:
    """检测所有碰撞对。

    使用 O(n^2) 的碰撞检测，对于每个活跃天体对检查其球心距离
    是否小于两半径之和。

    Args:
        bodies: shape (N, NUM_FIELDS) 的天体状态数组

    Returns:
        碰撞对列表，每项为 (id_a, id_b)，其中 id_a < id_b 避免重复
    """
    n = bodies.shape[0]
    collisions: List[Tuple[int, int]] = []

    if n < 2:
        return collisions

    positions = bodies[:, [X, Y]]
    radii = bodies[:, RADIUS]
    active = bodies[:, IS_ACTIVE] == 1.0
    static = bodies[:, IS_STATIC] == 1.0

    # 只考虑活跃天体
    active_indices = np.where(active)[0]
    if len(active_indices) < 2:
        return collisions

    for i_idx, i in enumerate(active_indices):
        # 只检查 i 之后的 pair (避免重复)
        for j in active_indices[i_idx + 1:]:
            # 如果两者都是静态，跳过
            if static[i] and static[j]:
                continue

            delta = positions[i] - positions[j]
            dist = np.sqrt(np.dot(delta, delta))
            min_dist = radii[i] + radii[j]

            if dist < min_dist:
                collisions.append((i, j))

    return collisions


def _is_star(body: np.ndarray) -> bool:
    """判断天体是否为恒星（大质量，通常不可被合并）。"""
    return body[7] == 0.0  # BODY_TYPE 列


def resolve_elastic(
    bodies: np.ndarray,
    collision_list: List[Tuple[int, int]],
) -> Tuple[np.ndarray, List[CollisionEvent]]:
    """弹性碰撞处理。

    使用一维弹性碰撞公式沿碰撞法线方向交换速度分量:
        v1_new = ((m1 - m2)*v1 + 2*m2*v2) / (m1 + m2)
        v2_new = ((m2 - m1)*v2 + 2*m1*v1) / (m1 + m2)

    Args:
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        collision_list: detect_collisions 返回的碰撞对列表

    Returns:
        (bodies, events) 元组: 更新后的天体状态和碰撞事件列表
    """
    events: List[CollisionEvent] = []

    for i, j in collision_list:
        if bodies[i, IS_ACTIVE] == 0.0 or bodies[j, IS_ACTIVE] == 0.0:
            continue
        if bodies[i, IS_STATIC] == 1.0 and bodies[j, IS_STATIC] == 1.0:
            continue

        # 质量
        m1 = bodies[i, MASS]
        m2 = bodies[j, MASS]

        # 位置差向量 (碰撞法线)
        dx = bodies[j, X] - bodies[i, X]
        dy = bodies[j, Y] - bodies[i, Y]
        dist = np.sqrt(dx * dx + dy * dy)
        if dist < 1e-12:
            continue
        nx = dx / dist
        ny = dy / dist

        # 将速度投影到法线方向
        v1n = bodies[i, VX] * nx + bodies[i, VY] * ny
        v2n = bodies[j, VX] * nx + bodies[j, VY] * ny

        total_mass = m1 + m2

        # 弹性碰撞后法线方向速度
        v1n_new = ((m1 - m2) * v1n + 2.0 * m2 * v2n) / total_mass
        v2n_new = ((m2 - m1) * v2n + 2.0 * m1 * v1n) / total_mass

        # 更新速度 (法线分量变化)
        dv1 = (v1n_new - v1n)
        dv2 = (v2n_new - v2n)
        bodies[i, VX] += dv1 * nx
        bodies[i, VY] += dv1 * ny
        bodies[j, VX] += dv2 * nx
        bodies[j, VY] += dv2 * ny

        # 轻微分离以防止粘滞
        overlap = (bodies[i, RADIUS] + bodies[j, RADIUS]) - dist
        if overlap > 0:
            # 按质量比例推开
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
    """合并碰撞处理。

    小质量天体被大质量天体吸收。合并后保留大天体的质量和位置，
    速度按动量守恒加权平均。小天体被标记为 IS_ACTIVE = 0。
    恒星不会被其他天体合并。

    Args:
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        collision_list: detect_collisions 返回的碰撞对列表

    Returns:
        (bodies, events) 元组: 更新后的天体状态和碰撞事件列表
    """
    events: List[CollisionEvent] = []

    for i, j in collision_list:
        if bodies[i, IS_ACTIVE] == 0.0 or bodies[j, IS_ACTIVE] == 0.0:
            continue
        if bodies[i, IS_STATIC] == 1.0 and bodies[j, IS_STATIC] == 1.0:
            continue

        m1 = bodies[i, MASS]
        m2 = bodies[j, MASS]

        # 恒星不能被合并（除非撞上另一个恒星）
        is_star_i = _is_star(bodies[i:i+1])
        is_star_j = _is_star(bodies[j:j+1])

        if is_star_i and is_star_j:
            # 两个恒星相撞: 采用弹性碰撞
            continue
        if is_star_i:
            # 小质量天体 j 被恒星 i 吸收
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

        # 动量守恒更新速度
        total_momentum_x = (bodies[i, MASS] * bodies[i, VX]
                            + bodies[j, MASS] * bodies[j, VX])
        total_momentum_y = (bodies[i, MASS] * bodies[i, VY]
                            + bodies[j, MASS] * bodies[j, VY])
        new_mass = bodies[i, MASS] + bodies[j, MASS]

        # 吸收者获得合并后的属性
        bodies[absorber, VX] = total_momentum_x / new_mass
        bodies[absorber, VY] = total_momentum_y / new_mass
        bodies[absorber, MASS] = new_mass
        # 新半径: 体积相加的等效半径
        old_radius = bodies[absorber, RADIUS]
        new_radius = (old_radius ** 3 + bodies[absorbed, RADIUS] ** 3) ** (1.0 / 3.0)
        bodies[absorber, RADIUS] = new_radius

        # 被吸收者标记为不存活
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
) -> Tuple[np.ndarray, List[CollisionEvent]]:
    """碰撞检测与自动响应。

    根据质量比自动选择碰撞处理策略:
        - 质量比 > merge_threshold: 合并碰撞
        - 质量比 <= merge_threshold: 弹性碰撞

    Args:
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        merge_threshold: 质量比阈值，超过此值时采用合并而非弹性碰撞

    Returns:
        (bodies, events) 元组: 更新后的天体状态和碰撞事件列表
    """
    collision_list = detect_collisions(bodies)
    if not collision_list:
        return bodies, []

    # 分离弹性碰撞和合并碰撞
    elastic_pairs: List[Tuple[int, int]] = []
    merge_pairs: List[Tuple[int, int]] = []

    for i, j in collision_list:
        m1 = bodies[i, MASS]
        m2 = bodies[j, MASS]
        if m1 <= 0 or m2 <= 0:
            continue
        max_mass = max(m1, m2)
        min_mass = min(m1, m2)
        ratio = max_mass / min_mass

        if ratio > merge_threshold:
            merge_pairs.append((i, j))
        else:
            elastic_pairs.append((i, j))

    bodies, events_elastic = resolve_elastic(bodies, elastic_pairs)
    bodies, events_merge = resolve_merge(bodies, merge_pairs)

    return bodies, events_elastic + events_merge
