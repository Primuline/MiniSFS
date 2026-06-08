"""碰撞检测与响应模块。

支持三种碰撞处理策略:
    - 恒星 vs 行星: 恒星吸收行星（质量、电荷相加）
    - 行星 vs 行星: 合并为新天体（质心位置，动量守恒）
    - 探测器 vs 任何天体: 探测器被摧毁

碰撞事件返回给调用方，供渲染器做特效（闪光、碎裂）。

用法::

    from src.physics.collision import detect_collisions, handle_collisions
"""

from typing import Dict, List, Tuple

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
    """判断天体是否为恒星（大质量，通常不可被合并）。

    Args:
        body: 1D array of shape (NUM_FIELDS,) representing a single body.

    Returns:
        True if the body type is BODY_TYPE_STAR (0), False otherwise.
    """
    return body[BODY_TYPE] == 0.0


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
        is_star_i = _is_star(bodies[i])
        is_star_j = _is_star(bodies[j])

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
    """碰撞检测与自动响应（新版规则）。

    根据天体类型和碰撞规则处理碰撞:
        - 恒星 vs 行星: 质量相加（合并到恒星），电荷相加，删除行星
        - 行星 vs 行星: 质量相加，电荷相加，动量相加；位置设在二者质心；
          删除两个原实体，用第一个实体位置存放合并结果
        - 探测器 vs 任何天体: 只删除探测器（IS_ACTIVE=0）

    Args:
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        merge_threshold: 保留参数（不再使用），保持接口兼容

    Returns:
        (bodies, events) 元组: 更新后的天体状态和碰撞事件列表
    """
    collision_list = detect_collisions(bodies)
    if not collision_list:
        return bodies, []

    events: List[CollisionEvent] = []
    processed: set = set()  # 已参与碰撞的天体，避免重复处理

    for i, j in collision_list:
        # 跳过已经处理过的或已不活跃的天体
        if bodies[i, IS_ACTIVE] == 0.0 or bodies[j, IS_ACTIVE] == 0.0:
            continue
        if i in processed or j in processed:
            continue

        type_i = int(bodies[i, BODY_TYPE])
        type_j = int(bodies[j, BODY_TYPE])

        # ================================================================
        # 规则 1: 探测器 vs 任何天体 → 只删除探测器
        # ================================================================
        if type_i == BODY_TYPE_PROBE:
            bodies[i, IS_ACTIVE] = 0.0
            processed.add(i)
            events.append({
                "type": "probe_destroyed",
                "id_a": int(i),
                "id_b": int(j),
                "pos_x": float(bodies[i, X]),
                "pos_y": float(bodies[i, Y]),
            })
            continue

        if type_j == BODY_TYPE_PROBE:
            bodies[j, IS_ACTIVE] = 0.0
            processed.add(j)
            events.append({
                "type": "probe_destroyed",
                "id_a": int(j),
                "id_b": int(i),
                "pos_x": float(bodies[j, X]),
                "pos_y": float(bodies[j, Y]),
            })
            continue

        # ================================================================
        # 规则 2: 恒星 vs 行星 → 合并到恒星
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
        # 规则 3: 行星 vs 行星 → 合并（质心位置，动量守恒）
        # ================================================================
        if type_i == BODY_TYPE_PLANET and type_j == BODY_TYPE_PLANET:
            m1 = bodies[i, MASS]
            m2 = bodies[j, MASS]
            total_mass = m1 + m2

            # 质心位置
            cx = (bodies[i, X] * m1 + bodies[j, X] * m2) / total_mass
            cy = (bodies[i, Y] * m1 + bodies[j, Y] * m2) / total_mass

            # 动量守恒计算合并后速度
            total_vx = (bodies[i, VX] * m1 + bodies[j, VX] * m2) / total_mass
            total_vy = (bodies[i, VY] * m1 + bodies[j, VY] * m2) / total_mass

            # 合并到 i（复用 i）
            bodies[i, X] = cx
            bodies[i, Y] = cy
            bodies[i, VX] = total_vx
            bodies[i, VY] = total_vy
            bodies[i, MASS] = total_mass
            bodies[i, CHARGE] = bodies[i, CHARGE] + bodies[j, CHARGE]
            # 半径：体积相加后取立方根
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
        # 其他类型碰撞（未定义规则）：跳过（保留原有状态）
        # ================================================================

    return bodies, events
