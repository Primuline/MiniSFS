"""数值积分器模块。

提供三种积分器用于天体运动方程的数值积分:
    - RK4（Runge-Kutta 4 阶）: 主积分器，高精度，推荐用于轨迹预测
    - Euler（显式欧拉）: 快速且简单，但精度低且能量不守恒
    - Velocity Verlet: 能量守恒好，适合长时间稳定模拟

所有积分器接收相同的接口:
    f(state, bodies) -> acceleration: 计算加速度的函数
    state: shape (N, 2) 的位置/速度数组 (pos, vel)
    bodies: shape (N, NUM_FIELDS) 的天体状态

用法::

    from src.physics.integrators import rk4_step, euler_step, velocity_verlet_step
"""

from typing import Callable, Tuple

import numpy as np

# 加速度函数类型: (pos: (N,2), bodies: (N, F)) -> acc: (N,2)
AccelFunc = Callable[[np.ndarray, np.ndarray], np.ndarray]


def euler_step(
    pos: np.ndarray,
    vel: np.ndarray,
    accel_fn: AccelFunc,
    bodies: np.ndarray,
    dt: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """显式欧拉积分一步。

    Euler 方法使用当前加速度更新速度，再使用新速度更新位置:
        v_new = v + a * dt
        x_new = x + v_new * dt

    Args:
        pos: shape (N, 2) 的位置数组 (m)
        vel: shape (N, 2) 的速度数组 (m/s)
        accel_fn: 计算加速度的函数 accel_fn(pos, bodies) -> (N, 2)
        bodies: shape (N, NUM_FIELDS) 的天体状态数组 (用于质量计算)
        dt: 时间步长 (s)

    Returns:
        (pos_new, vel_new, acc_new) 三元组:
            pos_new: shape (N, 2) 更新后的位置
            vel_new: shape (N, 2) 更新后的速度
            acc_new: shape (N, 2) 新位置的加速度（供 Velocity Verlet 用）
    """
    acc = accel_fn(pos, bodies)
    vel_new = vel + acc * dt
    pos_new = pos + vel_new * dt
    return pos_new, vel_new, acc


def rk4_step(
    pos: np.ndarray,
    vel: np.ndarray,
    accel_fn: AccelFunc,
    bodies: np.ndarray,
    dt: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """4 阶 Runge-Kutta 积分一步。

    RK4 是推荐的默认积分器，精度高，适用于精确模拟和轨迹预测。
    对于 N 体问题，每步需要 4 次加速度计算。

    Args:
        pos: shape (N, 2) 的位置数组 (m)
        vel: shape (N, 2) 的速度数组 (m/s)
        accel_fn: 计算加速度的函数 accel_fn(pos, bodies) -> (N, 2)
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        dt: 时间步长 (s)

    Returns:
        (pos_new, vel_new, acc_new) 三元组
    """
    # k1
    a1 = accel_fn(pos, bodies)                     # (N, 2)

    # k2
    k2_pos = pos + vel * (dt / 2.0)
    k2_vel = vel + a1 * (dt / 2.0)
    a2 = accel_fn(k2_pos, bodies)

    # k3
    k3_pos = pos + k2_vel * (dt / 2.0)
    k3_vel = vel + a2 * (dt / 2.0)
    a3 = accel_fn(k3_pos, bodies)

    # k4
    k4_pos = pos + k3_vel * dt
    k4_vel = vel + a3 * dt
    a4 = accel_fn(k4_pos, bodies)

    # 加权平均
    vel_new = vel + (dt / 6.0) * (a1 + 2.0 * a2 + 2.0 * a3 + a4)
    pos_new = pos + (dt / 6.0) * (vel + 2.0 * k2_vel + 2.0 * k3_vel + k4_vel)

    # 计算新位置的加速度（供 Velocity Verlet 或外部使用）
    acc_new = accel_fn(pos_new, bodies)

    return pos_new, vel_new, acc_new


def velocity_verlet_step(
    pos: np.ndarray,
    vel: np.ndarray,
    acc: np.ndarray,
    accel_fn: AccelFunc,
    bodies: np.ndarray,
    dt: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Velocity Verlet 积分一步。

    速度 Verlet 是辛积分器，长时间模拟时能量守恒优于 RK4。
    需要前一时刻的加速度作为输入。

    Args:
        pos: shape (N, 2) 的位置数组 (m)
        vel: shape (N, 2) 的速度数组 (m/s)
        acc: shape (N, 2) 当前加速度 (m/s^2)，来自上一时间步
        accel_fn: 计算加速度的函数 accel_fn(pos, bodies) -> (N, 2)
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        dt: 时间步长 (s)

    Returns:
        (pos_new, vel_new, acc_new) 三元组
    """
    # 半步位置更新
    pos_new = pos + vel * dt + 0.5 * acc * dt ** 2

    # 计算新位置的加速度
    acc_new = accel_fn(pos_new, bodies)

    # 速度更新: 使用新旧加速度的平均值
    vel_new = vel + 0.5 * (acc + acc_new) * dt

    return pos_new, vel_new, acc_new
