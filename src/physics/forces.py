"""天体受力计算模块。

提供牛顿万有引力和库仑力的向量化（O(n^2)）计算。
未来可搭配四叉树的 Barnes-Hut 加速实现 O(n log n) 近似计算。

用法::

    from src.physics.forces import compute_gravitational_forces, compute_coulomb_forces

    # 计算所有活跃天体的引力合力
    grav_forces = compute_gravitational_forces(bodies, G, softening)
    # 计算库仑力合力
    coul_forces = compute_coulomb_forces(bodies, K, softening)
    # 合并
    total_forces = grav_forces + coul_forces
"""

from typing import Tuple

import numpy as np

from src.core.types import CHARGE, IS_ACTIVE, IS_STATIC, MASS, X, Y


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
