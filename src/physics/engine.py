"""PhysicsEngine 主类。

实现 ``IPhysicsEngine`` 接口（定义在 ``src.core.interfaces``）。
组合 forces、integrators 和 collision 模块提供完整的多体物理模拟。

核心流程:
    1. ``update(bodies, dt)``: 多子步物理更新
       - 每子步: 计算合力 -> 积分（默认 RK4） -> 下一子步
       - 所有子步完成后: 检测并处理碰撞
    2. ``predict_trajectory(probe, bodies, steps, dt)``: RK4 推演
    3. ``compute_forces(bodies)``: 引力 + 库仑力
    4. ``handle_collisions(bodies)``: 碰撞检测与响应

用法::

    from src.physics.engine import PhysicsEngine

    engine = PhysicsEngine()
    updated_bodies = engine.update(bodies, dt)
    trajectory = engine.predict_trajectory(probe, bodies, 120, dt)
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from src.config import COULOMB_CONSTANT, GRAVITATIONAL_CONSTANT, SOFTENING, SUBSTEPS
from src.core.interfaces import IPhysicsEngine
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
    NUM_FIELDS,
)
from src.physics.collision import handle_collisions as resolve_collisions
from src.physics.forces import compute_total_forces
from src.physics.integrators import rk4_step


class PhysicsEngine(IPhysicsEngine):
    """多体物理引擎。

    管理引力/库仑力计算、数值积分和碰撞响应。
    支持子步（SUBSTEPS）提高稳定性，默认使用 RK4 积分器。

    Attributes:
        g: 万有引力常数
        k: 库仑常数
        softening: 软化参数，防止距离过近时受力发散
        substeps: 每帧物理子步数
        use_quadtree: 是否使用四叉树加速（预留，后续启用）
    """

    def __init__(
        self,
        g: float = GRAVITATIONAL_CONSTANT,
        k: float = COULOMB_CONSTANT,
        softening: float = SOFTENING,
        substeps: int = SUBSTEPS,
        use_quadtree: bool = False,
    ) -> None:
        """初始化物理引擎。

        Args:
            g: 万有引力常数，默认 6.67430e-11
            k: 库仑常数，默认 8.98755e9
            softening: 软化参数 (m)，默认 1.0
            substeps: 每帧子步数，默认 4
            use_quadtree: 是否启用四叉树 Barnes-Hut 加速，默认否
        """
        self.g: float = g
        self.k: float = k
        self.softening: float = softening
        self.substeps: int = substeps
        self.use_quadtree: bool = use_quadtree

        # 用于 Velocity Verlet 缓存上一子步的加速度
        self._last_acc: Optional[np.ndarray] = None

    def _acceleration_fn(
        self,
        pos: np.ndarray,
        bodies: np.ndarray,
    ) -> np.ndarray:
        """计算加速度（用于完整系统更新）。

        根据 pos 计算每个天体的加速度 a = F / m。
        静态天体加速度置为零。

        Args:
            pos: shape (N, 2) 的位置数组，与 bodies 行数相同
            bodies: shape (N, NUM_FIELDS) 的天体状态数组

        Returns:
            shape (N, 2) 的加速度数组 (m/s^2)
        """
        # 用 pos 更新所有天体的位置后计算受力
        bodies_snapshot = bodies.copy()
        bodies_snapshot[:, X] = pos[:, 0]
        bodies_snapshot[:, Y] = pos[:, 1]

        forces = compute_total_forces(
            bodies_snapshot, self.g, self.k, self.softening
        )

        masses = bodies_snapshot[:, MASS]
        # 避免除零
        inv_mass = np.where(masses > 0, 1.0 / masses, 0.0)
        acc = forces * inv_mass[:, np.newaxis]  # (N, 2)

        # 静态天体加速度置零
        static_mask = bodies_snapshot[:, IS_STATIC] == 1.0
        acc[static_mask] = 0.0

        return acc

    def _probe_acceleration_fn(
        self,
        pos: np.ndarray,
        sim_bodies: np.ndarray,
    ) -> np.ndarray:
        """计算探测器加速度（用于轨迹预测）。

        只更新探测器的位置，其他天体的位置不变。
        返回 shape (1, 2) 的探测器加速度。

        Args:
            pos: shape (1, 2) 的探测器位置
            sim_bodies: shape (N, NUM_FIELDS) 的组合数组（idx 0 为探测器）

        Returns:
            shape (1, 2) 的探测器加速度数组 (m/s^2)
        """
        bodies_snapshot = sim_bodies.copy()
        # 只更新探测器的位置
        bodies_snapshot[0, X] = pos[0, 0]
        bodies_snapshot[0, Y] = pos[0, 1]

        forces = compute_total_forces(
            bodies_snapshot, self.g, self.k, self.softening
        )

        # 只返回探测器的加速度
        probe_mass = bodies_snapshot[0, MASS]
        if probe_mass > 0:
            probe_acc = forces[0:1] / probe_mass  # (1, 2)
        else:
            probe_acc = np.zeros((1, 2), dtype=np.float64)

        return probe_acc

    def compute_forces(self, bodies: np.ndarray) -> np.ndarray:
        """计算所有天体受到的合力。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组

        Returns:
            shape (N, 2) 的合力数组 (N)
        """
        return compute_total_forces(bodies, self.g, self.k, self.softening)

    def update(self, bodies: np.ndarray, dt: float) -> np.ndarray:
        """更新所有天体状态一个时间步。

        将 dt 拆分为 self.substeps 个子步，每子步执行:
            1. 计算合力
            2. RK4 积分更新位置和速度
        所有子步完成后，检测并处理碰撞，移除失效天体。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
            dt: 时间步长 (秒)

        Returns:
            更新后的天体状态数组（行数可能因碰撞合并而减少）
        """
        bodies = bodies.copy()
        dt_sub = dt / self.substeps

        for _ in range(self.substeps):
            # 提取活跃天体的位置和速度
            pos = bodies[:, [X, Y]].copy()      # (N, 2)
            vel = bodies[:, [VX, VY]].copy()    # (N, 2)

            # RK4 积分一步
            pos_new, vel_new, _ = rk4_step(
                pos, vel, self._acceleration_fn, bodies, dt_sub
            )

            # 更新位置和速度
            bodies[:, X] = pos_new[:, 0]
            bodies[:, Y] = pos_new[:, 1]
            bodies[:, VX] = vel_new[:, 0]
            bodies[:, VY] = vel_new[:, 1]

        # 处理碰撞
        bodies, _ = resolve_collisions(bodies)

        # 移除不活跃的天体
        bodies = self._remove_inactive(bodies)

        return bodies

    def predict_trajectory(
        self,
        probe: np.ndarray,
        bodies: np.ndarray,
        steps: int,
        dt: float,
    ) -> np.ndarray:
        """预测探测器未来轨迹。

        使用 RK4 进行推演，不修改真实状态。
        当探测器与天体碰撞或超出边界时停止预测。

        Args:
            probe: shape (1, NUM_FIELDS) 的探测器状态
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
            steps: 预测步数
            dt: 每步时间间隔 (秒)

        Returns:
            shape (M, 2) 的预测轨迹坐标数组 (M <= steps)
        """
        trajectory: List[np.ndarray] = []
        probe_state = probe.copy()
        pos = probe_state[:, [X, Y]].copy()      # (1, 2)
        vel = probe_state[:, [VX, VY]].copy()    # (1, 2)

        # 预测时不修改原始天体，但需要与天体交互受力
        # 将探测器添加到天体数组中作为第 0 个活跃天体
        sim_bodies = np.vstack([probe_state, bodies])

        for _ in range(steps):
            pos, vel, _ = rk4_step(
                pos, vel, self._probe_acceleration_fn, sim_bodies, dt
            )

            # 更新 sim_bodies 中的探测器位置（方便下一次 force 计算）
            sim_bodies[0, X] = pos[0, 0]
            sim_bodies[0, Y] = pos[0, 1]
            sim_bodies[0, VX] = vel[0, 0]
            sim_bodies[0, VY] = vel[0, 1]

            trajectory.append(pos[0].copy())

            # 碰撞检测: 探测器与任何天体相撞则停止
            probe_radius = probe_state[0, 6]  # RADIUS
            probe_pos = pos[0]
            for b_idx in range(1, sim_bodies.shape[0]):
                if sim_bodies[b_idx, IS_ACTIVE] == 0.0:
                    continue
                delta = probe_pos - sim_bodies[b_idx, [X, Y]]
                dist = np.sqrt(np.dot(delta, delta))
                body_radius = sim_bodies[b_idx, 6]  # RADIUS
                if dist < probe_radius + body_radius:
                    # 停止预测
                    return np.array(trajectory)

        return np.array(trajectory)

    def handle_collisions(self, bodies: np.ndarray) -> np.ndarray:
        """检测并处理碰撞。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组

        Returns:
            处理碰撞后的天体状态数组
        """
        bodies, _ = resolve_collisions(bodies)
        return bodies

    def _remove_inactive(self, bodies: np.ndarray) -> np.ndarray:
        """移除 IS_ACTIVE == 0 的天体。

        使用布尔索引筛选出活跃天体。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组

        Returns:
            仅包含活跃天体的数组
        """
        active_mask = bodies[:, IS_ACTIVE] == 1.0
        return bodies[active_mask]

    def set_integrator(self, integrator: str) -> None:
        """切换积分器（预留接口）。

        目前只支持 'rk4'。未来可扩展为 'euler' 和 'velocity_verlet'。

        Args:
            integrator: 积分器名称 ('rk4', 'euler', 'velocity_verlet')

        Raises:
            ValueError: 不支持的积分器名称
        """
        valid = {"rk4", "euler", "velocity_verlet"}
        if integrator not in valid:
            raise ValueError(
                f"不支持的积分器 '{integrator}'，可选: {valid}"
            )
        self._integrator = integrator

    # ------------------------------------------------------------------
    # 测试用查询 API（只读，不修改状态）
    # ------------------------------------------------------------------

    def get_body_count(self, bodies: np.ndarray) -> int:
        """返回活跃天体数量。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组

        Returns:
            活跃天体数量
        """
        active = bodies[bodies[:, IS_ACTIVE] == 1.0]
        return int(active.shape[0])

    def get_body_state(self, bodies: np.ndarray, body_id: int) -> Dict[str, object]:
        """返回指定天体的完整状态字典。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
            body_id: 天体的行索引

        Returns:
            包含 x, y, vx, vy, mass, charge, radius, body_type, is_static, is_active 的字典
        """
        body = bodies[body_id]
        return {
            'x': float(body[X]),
            'y': float(body[Y]),
            'vx': float(body[VX]),
            'vy': float(body[VY]),
            'mass': float(body[MASS]),
            'charge': float(body[CHARGE]),
            'radius': float(body[RADIUS]),
            'body_type': int(body[BODY_TYPE]),
            'is_static': bool(body[IS_STATIC]),
            'is_active': bool(body[IS_ACTIVE]),
        }

    def get_total_energy(self, bodies: np.ndarray) -> float:
        """计算系统总机械能（动能 + 引力势能），用于验证能量守恒。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组

        Returns:
            总机械能 (J)
        """
        active = bodies[bodies[:, IS_ACTIVE] == 1.0]
        n = active.shape[0]
        if n == 0:
            return 0.0

        # 动能
        v_sq = active[:, VX] ** 2 + active[:, VY] ** 2
        ke = 0.5 * float(np.sum(active[:, MASS] * v_sq))

        # 引力势能
        pe = 0.0
        positions = active[:, [X, Y]]
        masses = active[:, MASS]
        for i in range(n):
            for j in range(i + 1, n):
                delta = positions[i] - positions[j]
                dist = float(np.sqrt(np.dot(delta, delta)))
                if dist > 1e-12:
                    pe -= self.g * float(masses[i]) * float(masses[j]) / dist

        return ke + pe

    def get_total_momentum(self, bodies: np.ndarray) -> Tuple[float, float]:
        """计算系统总动量 (px, py)，用于验证动量守恒。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组

        Returns:
            (px, py) 总动量 (kg m/s)
        """
        active = bodies[bodies[:, IS_ACTIVE] == 1.0]
        if active.shape[0] == 0:
            return (0.0, 0.0)
        px = float(np.sum(active[:, MASS] * active[:, VX]))
        py = float(np.sum(active[:, MASS] * active[:, VY]))
        return (px, py)
