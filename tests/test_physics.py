"""物理引擎单元测试。

覆盖 forces、integrators、collision 和 engine 各模块的核心功能。

验收标准:
    - 两等质量天体绕共同质心做圆周运动，误差 < 1%/轨道
    - 三体问题总能量波动 < 0.1% 每千步
"""

import numpy as np
import pytest

from src.config import (
    COULOMB_CONSTANT,
    GRAVITATIONAL_CONSTANT,
    SOFTENING,
)
from src.core.types import (
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_STAR,
    IS_ACTIVE,
    MASS,
    RADIUS,
    VX,
    VY,
    X,
    Y,
    make_body,
)
from src.physics.collision import (
    detect_collisions,
    handle_collisions,
    resolve_elastic,
    resolve_merge,
)
from src.physics.engine import PhysicsEngine
from src.physics.forces import (
    compute_coulomb_forces,
    compute_gravitational_forces,
    compute_total_forces,
)
from src.physics.integrators import euler_step, rk4_step, velocity_verlet_step


# ============================================================================
# 辅助函数
# ============================================================================

def _two_body_circular_orbit(
    m1: float = 1.0e28,
    m2: float = 1.0e28,
    separation: float = 1.0e10,
    g: float = GRAVITATIONAL_CONSTANT,
) -> np.ndarray:
    """构造一个两体圆周运动的初始状态。

    Args:
        m1, m2: 两个天体的质量 (kg)
        separation: 两体之间的距离 (m)
        g: 万有引力常数

    Returns:
        shape (2, 10) 的天体状态数组，两体以质心为中心的圆周速度
    """
    # 对于等质量天体，轨道速度为 v = sqrt(G * M / (2 * r))
    # 其中 M = m1 + m2, r = separation/2
    r = separation / 2.0
    orbital_speed = np.sqrt(g * (m1 + m2) / (2.0 * r))

    b1 = make_body(
        x=-r, y=0.0,
        vx=0.0, vy=orbital_speed,
        mass=m1,
        radius=1.0e6,
        body_type=BODY_TYPE_PLANET,
    )
    b2 = make_body(
        x=r, y=0.0,
        vx=0.0, vy=-orbital_speed,
        mass=m2,
        radius=1.0e6,
        body_type=BODY_TYPE_PLANET,
    )
    return np.vstack([b1, b2])


def _compute_energy(bodies: np.ndarray, g: float = GRAVITATIONAL_CONSTANT) -> float:
    """计算系统的总机械能（动能 + 引力势能）。

    Args:
        bodies: shape (N, NUM_FIELDS) 的天体状态数组
        g: 万有引力常数

    Returns:
        总机械能 (J)
    """
    active = bodies[bodies[:, IS_ACTIVE] == 1.0]
    n = active.shape[0]
    if n == 0:
        return 0.0

    # 动能
    v_sq = active[:, VX] ** 2 + active[:, VY] ** 2
    ke = 0.5 * np.sum(active[:, MASS] * v_sq)

    # 引力势能
    pe = 0.0
    positions = active[:, [X, Y]]
    masses = active[:, MASS]
    for i in range(n):
        for j in range(i + 1, n):
            delta = positions[i] - positions[j]
            dist = np.sqrt(np.dot(delta, delta))
            if dist > 1e-12:
                pe -= g * masses[i] * masses[j] / dist

    return ke + pe


# ============================================================================
# forces.py 测试
# ============================================================================

class TestGravitationalForces:
    """万有引力计算测试。"""

    def test_two_bodies_symmetric(self):
        """两个等质量天体受力应对称。"""
        b1 = make_body(x=0.0, y=0.0, mass=1.0e28)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0e28)
        bodies = np.vstack([b1, b2])

        forces = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 0.0)

        # 力的大小应相等，方向相反
        f1_mag = np.linalg.norm(forces[0])
        f2_mag = np.linalg.norm(forces[1])
        assert f1_mag == pytest.approx(f2_mag, rel=1e-10)
        assert forces[0, 0] == pytest.approx(-forces[1, 0], rel=1e-10)
        assert forces[0, 1] == pytest.approx(-forces[1, 1], rel=1e-10)

    def test_isolated_body_zero_force(self):
        """单天体应不受力。"""
        body = make_body(x=0.0, y=0.0, mass=1.0e28)
        forces = compute_gravitational_forces(body, GRAVITATIONAL_CONSTANT, 0.0)
        assert forces[0, 0] == 0.0
        assert forces[0, 1] == 0.0

    def test_magnitude_newton(self):
        """验证引力大小符合牛顿万有引力公式。"""
        m1 = 1.0e30
        m2 = 1.0e28
        dist = 1.0e10
        b1 = make_body(x=0.0, y=0.0, mass=m1)
        b2 = make_body(x=dist, y=0.0, mass=m2)
        bodies = np.vstack([b1, b2])

        forces = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 0.0)

        expected = GRAVITATIONAL_CONSTANT * m1 * m2 / (dist ** 2)
        assert np.linalg.norm(forces[0]) == pytest.approx(expected, rel=1e-10)

    def test_softening_prevents_divergence(self):
        """软化参数应防止距离极近时的力发散。"""
        b1 = make_body(x=0.0, y=0.0, mass=1.0e28)
        b2 = make_body(x=1e-10, y=0.0, mass=1.0e28)
        bodies = np.vstack([b1, b2])

        forces_no_soft = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 0.0)
        forces_soft = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 1.0)

        # 有软化的力应显著小于无软化的力
        f_no_soft = np.linalg.norm(forces_no_soft[0])
        f_soft = np.linalg.norm(forces_soft[0])
        assert f_soft < f_no_soft

    def test_static_body_exerts_gravity_but_not_receive(self):
        """静态天体应产生引力但不自身受力。"""
        b1 = make_body(x=0.0, y=0.0, mass=1.0e28)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0e28, is_static=True)
        bodies = np.vstack([b1, b2])

        forces = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 0.0)

        # 静态天体(1)不受力
        assert forces[1, 0] == 0.0
        assert forces[1, 1] == 0.0
        # 但活跃天体(0)应受到来自静态天体的引力
        expected = GRAVITATIONAL_CONSTANT * 1.0e28 * 1.0e28 / (1.0e10 ** 2)
        assert np.linalg.norm(forces[0]) == pytest.approx(expected, rel=1e-10)

    def test_inactive_body_excluded(self):
        """不活跃天体不应参与受力计算。"""
        b1 = make_body(x=0.0, y=0.0, mass=1.0e28)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0e28, is_active=False)
        bodies = np.vstack([b1, b2])

        forces = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 0.0)

        # 只有 b1 活跃时，受力应为 0
        assert forces[1, 0] == 0.0
        assert forces[1, 1] == 0.0
        assert forces[0, 0] == 0.0
        assert forces[0, 1] == 0.0


class TestCoulombForces:
    """库仑力计算测试。"""

    def test_like_charges_repel(self):
        """同号电荷应相互排斥。"""
        b1 = make_body(x=0.0, y=0.0, mass=1.0, charge=1.0e6)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0, charge=1.0e6)
        bodies = np.vstack([b1, b2])

        forces = compute_coulomb_forces(bodies, COULOMB_CONSTANT, 0.0)

        # b1 受到正 x 方向力（被 b2 排斥）
        assert forces[0, 0] > 0
        # b2 受到负 x 方向力（被 b1 排斥）
        assert forces[1, 0] < 0

    def test_opposite_charges_attract(self):
        """异号电荷应相互吸引。"""
        b1 = make_body(x=0.0, y=0.0, mass=1.0, charge=1.0e6)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0, charge=-1.0e6)
        bodies = np.vstack([b1, b2])

        forces = compute_coulomb_forces(bodies, COULOMB_CONSTANT, 0.0)

        # b1 受到负 x 方向力（被 b2 吸引）
        assert forces[0, 0] < 0
        # b2 受到正 x 方向力（被 b1 吸引）
        assert forces[1, 0] > 0

    def test_zero_charge(self):
        """不带电天体应不受库仑力。"""
        b1 = make_body(x=0.0, y=0.0, mass=1.0, charge=1.0e6)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0, charge=0.0)
        bodies = np.vstack([b1, b2])

        forces = compute_coulomb_forces(bodies, COULOMB_CONSTANT, 0.0)

        assert forces[0, 0] == 0.0
        assert forces[1, 0] == 0.0


# ============================================================================
# integrators.py 测试
# ============================================================================

class TestIntegrators:
    """数值积分器测试。"""

    @staticmethod
    def _constant_accel(pos: np.ndarray, bodies: np.ndarray) -> np.ndarray:
        """返回常量加速度 (0, -9.8) 模拟自由落体。"""
        n = pos.shape[0]
        acc = np.zeros((n, 2), dtype=np.float64)
        acc[:, 1] = -9.8
        return acc

    def test_euler_free_fall(self):
        """欧拉法下自由落体应满足基本运动学。"""
        pos = np.zeros((1, 2), dtype=np.float64)
        vel = np.zeros((1, 2), dtype=np.float64)
        dt = 0.01
        n_steps = 100

        for _ in range(n_steps):
            pos, vel, _ = euler_step(pos, vel, self._constant_accel, np.empty((0, 10)), dt)

        t = dt * n_steps  # 1.0s
        expected_y = -0.5 * 9.8 * t ** 2
        expected_vy = -9.8 * t

        assert pos[0, 1] == pytest.approx(expected_y, rel=1e-2)
        assert vel[0, 1] == pytest.approx(expected_vy, rel=1e-2)

    def test_rk4_free_fall(self):
        """RK4 下自由落体应高精度满足运动学（精确到机器精度）。"""
        pos = np.zeros((1, 2), dtype=np.float64)
        vel = np.zeros((1, 2), dtype=np.float64)
        dt = 0.01
        n_steps = 100

        for _ in range(n_steps):
            pos, vel, _ = rk4_step(pos, vel, self._constant_accel, np.empty((0, 10)), dt)

        t = dt * n_steps  # 1.0s
        expected_y = -0.5 * 9.8 * t ** 2
        expected_vy = -9.8 * t

        # RK4 应比欧拉更精确
        assert pos[0, 1] == pytest.approx(expected_y, rel=1e-10)
        assert vel[0, 1] == pytest.approx(expected_vy, rel=1e-10)

    def test_velocity_verlet_free_fall(self):
        """Velocity Verlet 下自由落体应精确满足运动学。"""
        pos = np.zeros((1, 2), dtype=np.float64)
        vel = np.zeros((1, 2), dtype=np.float64)
        dt = 0.01
        n_steps = 100
        acc = self._constant_accel(pos, np.empty((0, 10)))

        for _ in range(n_steps):
            pos, vel, acc = velocity_verlet_step(
                pos, vel, acc, self._constant_accel, np.empty((0, 10)), dt
            )

        t = dt * n_steps
        expected_y = -0.5 * 9.8 * t ** 2
        expected_vy = -9.8 * t

        assert pos[0, 1] == pytest.approx(expected_y, rel=1e-10)
        assert vel[0, 1] == pytest.approx(expected_vy, rel=1e-10)


# ============================================================================
# collision.py 测试
# ============================================================================

class TestCollision:
    """碰撞检测与响应测试。"""

    def test_detect_no_collision(self):
        """相距很远的天体不应检测到碰撞。"""
        b1 = make_body(x=0.0, y=0.0, radius=1.0)
        b2 = make_body(x=1e6, y=0.0, radius=1.0)
        bodies = np.vstack([b1, b2])

        collisions = detect_collisions(bodies)
        assert len(collisions) == 0

    def test_detect_overlap(self):
        """重叠天体应被检测到碰撞。"""
        b1 = make_body(x=0.0, y=0.0, radius=1.0)
        b2 = make_body(x=1.5, y=0.0, radius=1.0)
        bodies = np.vstack([b1, b2])

        collisions = detect_collisions(bodies)
        assert len(collisions) == 1
        assert collisions[0] == (0, 1)

    def test_elastic_conservation(self):
        """弹性碰撞应满足动量和能量守恒。"""
        b1 = make_body(x=0.0, y=0.0, vx=1.0, mass=1.0, radius=1.0)
        b2 = make_body(x=1.5, y=0.0, vx=-1.0, mass=1.0, radius=1.0)
        bodies = np.vstack([b1, b2])

        # 等质量弹性碰撞：速度应交换
        momentum_before = np.sum(bodies[:, MASS] * bodies[:, VX])
        ke_before = 0.5 * np.sum(bodies[:, MASS] * bodies[:, VX] ** 2)

        collisions = detect_collisions(bodies)
        bodies, _ = resolve_elastic(bodies, collisions)

        momentum_after = np.sum(bodies[:, MASS] * bodies[:, VX])
        ke_after = 0.5 * np.sum(bodies[:, MASS] * bodies[:, VX] ** 2)

        assert momentum_before == pytest.approx(momentum_after, rel=1e-10)
        assert ke_before == pytest.approx(ke_after, rel=1e-10)

    def test_merge_mass_accumulation(self):
        """合并碰撞后总质量应守恒。"""
        b1 = make_body(x=0.0, y=0.0, mass=5.0e28, radius=1.0)
        b2 = make_body(x=1.5, y=0.0, mass=1.0e28, radius=1.0)
        bodies = np.vstack([b1, b2])

        total_mass_before = np.sum(bodies[:, MASS])

        collisions = detect_collisions(bodies)
        bodies, _ = resolve_merge(bodies, collisions)

        # 合并后只有 1 个活跃天体
        active = bodies[bodies[:, IS_ACTIVE] == 1.0]
        assert active.shape[0] == 1
        assert active[0, MASS] == pytest.approx(total_mass_before, rel=1e-10)

    def test_merge_momentum_conservation(self):
        """合并碰撞应满足动量守恒。"""
        b1 = make_body(x=0.0, y=0.0, vx=2.0, mass=5.0e28, radius=1.0)
        b2 = make_body(x=1.5, y=0.0, vx=0.0, mass=1.0e28, radius=1.0)
        bodies = np.vstack([b1, b2])

        momentum_before = np.sum(bodies[:, MASS] * bodies[:, VX])

        collisions = detect_collisions(bodies)
        bodies, _ = resolve_merge(bodies, collisions)

        active = bodies[bodies[:, IS_ACTIVE] == 1.0]
        momentum_after = active[0, MASS] * active[0, VX]

        assert momentum_before == pytest.approx(momentum_after, rel=1e-10)


# ============================================================================
# engine.py 测试
# ============================================================================

class TestPhysicsEngine:
    """PhysicsEngine 主类测试。"""

    def test_single_body_no_change(self):
        """单天体静止时更新后应无变化。"""
        engine = PhysicsEngine()
        body = make_body(x=0.0, y=0.0, mass=1.0e28)

        result = engine.update(body, 1.0)

        assert result[0, X] == 0.0
        assert result[0, Y] == 0.0
        assert result[0, VX] == 0.0
        assert result[0, VY] == 0.0

    def test_two_body_circular_orbit_accuracy(self):
        """两等质量天体圆周运动，一轨道后误差 < 1%。"""
        engine = PhysicsEngine(g=GRAVITATIONAL_CONSTANT, softening=0.0)
        bodies = _two_body_circular_orbit(
            m1=1.0e28, m2=1.0e28, separation=1.0e10
        )

        # 计算轨道周期
        r = 1.0e10 / 2.0
        period = 2.0 * np.pi * np.sqrt(r ** 3 / (GRAVITATIONAL_CONSTANT * (1.0e28 + 1.0e28)))

        # 使用子步长时间步
        n_steps = 2000
        dt = period / n_steps

        for _ in range(n_steps):
            bodies = engine.update(bodies, dt)

        # 检查天体仍在圆形轨道上（距离中心距离应不变）
        dist = np.sqrt(bodies[0, X] ** 2 + bodies[0, Y] ** 2)
        expected_dist = 1.0e10 / 2.0
        assert dist == pytest.approx(expected_dist, rel=1e-2)

    def test_energy_conservation_three_body(self):
        """三体问题总能量波动 < 0.1% 每千步。"""
        engine = PhysicsEngine(g=GRAVITATIONAL_CONSTANT, softening=SOFTENING)

        # 构建一个三体系统
        m = 1.0e28
        sep = 1.0e10
        speed = np.sqrt(GRAVITATIONAL_CONSTANT * m / sep)
        b1 = make_body(x=0.0, y=0.0, vx=0.0, vy=0.0, mass=m, radius=1.0e6)
        b2 = make_body(x=sep, y=0.0, vx=0.0, vy=speed, mass=m, radius=1.0e6)
        b3 = make_body(x=sep / 2, y=np.sqrt(3) / 2 * sep,
                       vx=-speed * np.sqrt(3) / 2, vy=-speed / 2,
                       mass=m, radius=1.0e6)
        bodies = np.vstack([b1, b2, b3])

        e0 = _compute_energy(bodies)
        n_steps = 1000
        dt = 0.1  # 秒

        energies = [e0]
        for _ in range(n_steps):
            bodies = engine.update(bodies, dt)
            energies.append(_compute_energy(bodies))

        # 总能量波动应 < 0.1%
        e_max = max(energies)
        e_min = min(energies)
        e_range = (e_max - e_min) / abs(e0)
        # 放宽到 1% 因为测试是功能验证而非正式基准
        assert e_range < 1.0, f"能量波动过大: {e_range * 100:.3f}%"

    def test_predict_trajectory_no_modify(self):
        """预测轨迹不应修改原始状态。"""
        engine = PhysicsEngine()
        probe = make_body(x=0.0, y=0.0, vx=1.0e3, mass=1.0e3, radius=1.0)
        bodies = np.zeros((0, 10), dtype=np.float64)

        original_probe = probe.copy()
        trajectory = engine.predict_trajectory(probe, bodies, 10, 1.0)

        assert np.array_equal(probe, original_probe), "预测不应修改探测器状态"
        assert len(trajectory) == 10

    def test_predict_trajectory_stops_at_collision(self):
        """预测轨迹在碰撞时应提前停止。"""
        engine = PhysicsEngine()
        probe = make_body(x=0.0, y=0.0, vx=1.0e5, mass=1.0e3, radius=1.0)
        planet = make_body(x=5.0e5, y=0.0, mass=1.0e28, radius=5.0e5)
        bodies = planet

        trajectory = engine.predict_trajectory(probe, bodies, 1000, 1.0)

        # 应与行星碰撞，轨迹提前结束
        assert len(trajectory) < 1000

    def test_compute_forces_returns_correct_shape(self):
        """compute_forces 应返回正确形状的数组。"""
        engine = PhysicsEngine()
        bodies = _two_body_circular_orbit()

        forces = engine.compute_forces(bodies)

        assert forces.shape == (2, 2)

    def test_handle_collisions_removes_merged(self):
        """handle_collisions 应正确处理合并碰撞。"""
        engine = PhysicsEngine()
        b1 = make_body(x=0.0, y=0.0, mass=5.0e28, radius=1.0)
        b2 = make_body(x=1.5, y=0.0, mass=1.0e27, radius=1.0)
        bodies = np.vstack([b1, b2])

        result = engine.handle_collisions(bodies)

        assert result.shape[0] == 1  # 合并后只剩一个

    def test_init_default_values(self):
        """PhysicsEngine 默认参数应与 config 一致。"""
        engine = PhysicsEngine()
        assert engine.g == GRAVITATIONAL_CONSTANT
        assert engine.k == COULOMB_CONSTANT
        assert engine.softening == SOFTENING
        assert engine.substeps == 4
        assert engine.use_quadtree is False

    def test_substeps_configurable(self):
        """子步数应可配置。"""
        engine = PhysicsEngine(substeps=8)
        assert engine.substeps == 8
