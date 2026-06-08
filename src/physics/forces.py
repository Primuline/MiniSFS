"""天体受力计算模块。

提供牛顿万有引力和库仑力的向量化（O(n^2)）计算。
未来可搭配四叉树的 Barnes-Hut 加速实现 O(n log n) 近似计算。

还提供单星轨迹预测函数用于放置速度设定时的轨迹预览。

用法::

    from src.physics.forces import compute_gravitational_forces, compute_coulomb_forces

    # 计算所有活跃天体的引力合力
    grav_forces = compute_gravitational_forces(bodies, G, softening)
    # 计算库仑力合力
    coul_forces = compute_coulomb_forces(bodies, K, softening)
    # 合并
    total_forces = grav_forces + coul_forces
"""

import math
from typing import Dict, Optional, Tuple

import numpy as np

from src.config import ESCAPE_RATIO, MAX_TRAJECTORY_STEPS
from src.core.types import (
    BODY_TYPE,
    CHARGE,
    IS_ACTIVE,
    IS_STATIC,
    MASS,
    RADIUS,
    X,
    Y,
)


def compute_gravitational_forces(
    bodies: np.ndarray,
    g: float,
    softening: float,
) -> np.ndarray:
    """计算所有天体受到的总万有引力。

    使用向量化 O(n^2) 全量计算。返回 shape (N, 2) 的力数组。
    静态天体不受力（不计算其加速度），但会对其他天体产生引力。
    不活跃天体既不产生引力也不受力。

    Args:
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        g: 万有引力常数（如 6.67430e-11）
        softening: 软化参数 (m)，防止 r -> 0 时受力发散

    Returns:
        shape (N, 2) 的合力数组 (fx, fy)，单位 N
    """
    n = bodies.shape[0]
    forces = np.zeros((n, 2), dtype=np.float64)

    if n < 2:
        return forces

    # 提取位置和质量
    positions = bodies[:, [X, Y]]       # shape (N, 2)
    masses = bodies[:, MASS]            # shape (N,)
    is_active = bodies[:, IS_ACTIVE] == 1.0
    is_static = bodies[:, IS_STATIC] == 1.0

    # 不活跃天体不产生引力（质量视为 0）
    effective_masses = masses.copy()
    effective_masses[~is_active] = 0.0

    # 计算所有 pair 的位移向量: positions[i] - positions[j]
    # 利用广播: (N,1,2) - (1,N,2) -> (N,N,2)
    delta = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]  # (N, N, 2)

    # 距离平方 +  softening^2 (避免除零)
    r_squared = np.sum(delta ** 2, axis=-1) + softening ** 2          # (N, N)
    r = np.sqrt(r_squared)                                             # (N, N)

    # 引力大小: F = G * m_i * m_j / r^2
    # 注意这里 F_ij = G * m_i * m_j / r^2, 作用方向从 j 指向 i
    force_magnitude = g * effective_masses[np.newaxis, :] * effective_masses[:, np.newaxis] / r_squared  # (N, N)

    # 力向量: -(F_mag / r) * delta  (负号使方向从 i 指向 j，即引力)
    # delta[i,j] = pos_i - pos_j 指向从 j 到 i，但引力需要从 i 指向 j
    # shape (N, N, 2): delta 每个分量乘上 -force_magnitude / r
    inv_r = np.where(r > 0, 1.0 / r, 0.0)
    force_vectors = -delta * (force_magnitude * inv_r)[:, :, np.newaxis]  # (N, N, 2)

    # 对 j 求和得到每个天体 i 的合力
    forces[:, :] = np.sum(force_vectors, axis=1)  # (N, 2)

    # 静态和不活跃天体不受力
    no_force_mask = ~is_active | is_static
    forces[no_force_mask] = 0.0

    return forces


def compute_coulomb_forces(
    bodies: np.ndarray,
    k: float,
    softening: float,
) -> np.ndarray:
    """计算所有天体受到的总库仑力。

    使用向量化 O(n^2) 全量计算。返回 shape (N, 2) 的力数组。
    正负电荷相互吸引，同号电荷相互排斥。
    静态天体不受力但对其余天体产生库仑力。
    不活跃天体既不产生库仑力也不受力。

    Args:
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        k: 库仑常数（如 8.98755e9）
        softening: 软化参数 (m)

    Returns:
        shape (N, 2) 的合力数组 (fx, fy)，单位 N
    """
    n = bodies.shape[0]
    forces = np.zeros((n, 2), dtype=np.float64)

    if n < 2:
        return forces

    positions = bodies[:, [X, Y]]       # shape (N, 2)
    charges = bodies[:, CHARGE]         # shape (N,)
    is_active = bodies[:, IS_ACTIVE] == 1.0
    is_static = bodies[:, IS_STATIC] == 1.0

    # 不活跃天体的电荷视为 0
    effective_charges = charges.copy()
    effective_charges[~is_active] = 0.0

    delta = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]  # (N, N, 2)
    r_squared = np.sum(delta ** 2, axis=-1) + softening ** 2          # (N, N)
    r = np.sqrt(r_squared)                                             # (N, N)

    # 库仑力: F = k * q_i * q_j / r^2 (正为排斥，负为吸引)
    force_magnitude = k * effective_charges[np.newaxis, :] * effective_charges[:, np.newaxis] / r_squared  # (N, N)

    inv_r = np.where(r > 0, 1.0 / r, 0.0)
    force_vectors = delta * (force_magnitude * inv_r)[:, :, np.newaxis]  # (N, N, 2)

    forces[:, :] = np.sum(force_vectors, axis=1)  # (N, 2)

    # 静态和不活跃天体不受力
    no_force_mask = ~is_active | is_static
    forces[no_force_mask] = 0.0

    return forces


def compute_total_forces(
    bodies: np.ndarray,
    g: float,
    k: float,
    softening: float,
) -> np.ndarray:
    """计算所有天体受到的总合力（引力 + 库仑力）。

    Args:
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        g: 万有引力常数
        k: 库仑常数
        softening: 软化参数 (m)

    Returns:
        shape (N, 2) 的合力数组 (fx, fy)
    """
    grav = compute_gravitational_forces(bodies, g, softening)
    coul = compute_coulomb_forces(bodies, k, softening)
    return grav + coul


# ============================================================================
# 轨迹预览函数
# ============================================================================


def find_nearest_star(
    pos: np.ndarray,
    bodies: np.ndarray,
) -> Optional[Tuple[int, np.ndarray, float, float]]:
    """在 bodies 中查找距离给定位置最近的活跃恒星。

    Args:
        pos: shape (2,) 的查询坐标 (m)
        bodies: shape (N, NUM_FIELDS) 的天体状态数组

    Returns:
        (index, star_pos, star_mass, star_radius) 的元组，
        若未找到恒星则返回 None。

        - index: 恒星在 bodies 中的行索引
        - star_pos: shape (2,) 的恒星位置数组 (m)
        - star_mass: 恒星质量 (kg)
        - star_radius: 恒星半径 (m)
    """
    best_idx: Optional[int] = None
    best_dist_sq: float = float("inf")

    for i in range(bodies.shape[0]):
        if int(bodies[i, BODY_TYPE]) != 0:  # BODY_TYPE_STAR == 0
            continue
        if bodies[i, IS_ACTIVE] == 0.0:
            continue
        dx = float(bodies[i, X] - pos[0])
        dy = float(bodies[i, Y] - pos[1])
        dist_sq = dx * dx + dy * dy
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_idx = i

    if best_idx is None:
        return None

    idx = best_idx
    star_pos = bodies[idx, [X, Y]].copy()  # shape (2,)
    star_mass = float(bodies[idx, MASS])
    star_radius = float(bodies[idx, RADIUS])
    return (idx, star_pos, star_mass, star_radius)


def predict_single_star_trajectory(
    pos: np.ndarray,
    vel: np.ndarray,
    star_pos: np.ndarray,
    star_mass: float,
    star_radius: float,
    body_radius: float,
    g: float,
    softening: float,
    steps: int = 2000,
    dt: float = 5000.0,
) -> Dict[str, object]:
    """预测单一天体在单一引力源下的运动轨迹。

    使用 Euler 数值积分计算二体问题轨迹。
    引力源视为固定不动，仅计算待放置天体受到的引力。
    终止条件（按优先级）：碰撞 > 逃逸 > 绕圈完成 > 最大步数。

    Args:
        pos: shape (2,) 的预览位置世界坐标 (m)
        vel: shape (2,) 的设定速度向量 (m/s)
        star_pos: shape (2,) 的引力源位置 (m)
        star_mass: 引力源质量 (kg)
        star_radius: 引力源半径 (m)
        body_radius: 放置天体的半径 (m)
        g: 万有引力常数
        softening: 软化参数 (m)
        steps: 最大积分步数（安全上限）
        dt: 每步时间间隔 (秒)

    Returns:
        包含以下键的字典:
            - "trajectory": shape (N, 2) 的轨迹世界坐标数组（原始密度）
            - "collided": 是否与恒星碰撞
            - "escaped": 是否逃逸
            - "orbited": 是否绕引力源完成一圈
    """
    pos_cur = pos.copy().astype(np.float64)
    vel_cur = vel.copy().astype(np.float64)
    star_pos_f64 = star_pos.astype(np.float64)

    # 初始距离用于逃逸检测
    initial_delta = pos_cur - star_pos_f64
    initial_dist = float(np.linalg.norm(initial_delta))
    escape_threshold: float = ESCAPE_RATIO * max(initial_dist, 1.0)
    collision_radius: float = star_radius + body_radius

    trajectory: list = [pos_cur.copy()]
    collided: bool = False
    escaped: bool = False
    orbited: bool = False

    # 角度累计检测
    total_angle: float = 0.0
    prev_angle: float = math.atan2(
        pos_cur[1] - star_pos_f64[1],
        pos_cur[0] - star_pos_f64[0],
    )

    max_steps = min(steps, MAX_TRAJECTORY_STEPS)

    for _ in range(max_steps):
        r_vec = pos_cur - star_pos_f64
        dist = float(np.linalg.norm(r_vec)) + softening

        # 1. 碰撞检测（最高优先级）
        if dist < collision_radius:
            collided = True
            # 回退插值到星体表面：从上一已知安全位置沿方向插值到 surface
            if len(trajectory) >= 2:
                last_safe = trajectory[-1]
                r_safe = last_safe - star_pos_f64
                d_safe = float(np.linalg.norm(r_safe))
                cur_raw = dist - softening  # 去掉 softening
                if d_safe > cur_raw:
                    # 在安全位置与穿透位置之间线性插值到碰撞半径
                    t = (d_safe - collision_radius) / (d_safe - cur_raw)
                    t = max(0.0, min(t, 1.0))
                    hit_pt = last_safe + (pos_cur - last_safe) * t
                    trajectory.append(hit_pt)
                    trajectory.append(surface_pt)
            else:
                trajectory.append(pos_cur.copy())
            break

        # 2. 逃逸检测
        if dist > escape_threshold:
            escaped = True
            trajectory.append(pos_cur.copy())
            break

        # 3. 角度变化检测
        current_angle = math.atan2(r_vec[1], r_vec[0])
        delta_angle = current_angle - prev_angle
        # 归一化到 [-pi, pi]
        while delta_angle > math.pi:
            delta_angle -= 2.0 * math.pi
        while delta_angle < -math.pi:
            delta_angle += 2.0 * math.pi
        total_angle += abs(delta_angle)
        prev_angle = current_angle

        # 绕完一圈
        if total_angle >= 2.0 * math.pi:
            orbited = True
            trajectory.append(pos_cur.copy())
            break

        # 4. 积分一步（Euler 法）
        acc = -g * star_mass * r_vec / (dist ** 3)
        vel_cur += acc * dt
        pos_cur += vel_cur * dt
        trajectory.append(pos_cur.copy())

    return {
        "trajectory": np.array(trajectory, dtype=np.float64),
        "collided": collided,
        "escaped": escaped,
        "orbited": orbited,
    }
