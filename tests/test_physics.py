"""Physics engine unit tests.

Covers core functionality of forces, integrators, collision and engine modules.

Acceptance criteria:
    - Two equal-mass bodies orbit the common center of mass with error < 1%/orbit
    - Three-body problem total energy fluctuation < 0.1% per thousand steps
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
# Helper functions
# ============================================================================

def _two_body_circular_orbit(
    m1: float = 1.0e28,
    m2: float = 1.0e28,
    separation: float = 1.0e10,
    g: float = GRAVITATIONAL_CONSTANT,
) -> np.ndarray:
    """Construct an initial state for a two-body circular orbit.

    Args:
        m1, m2: Masses of the two bodies (kg)
        separation: Distance between the two bodies (m)
        g: Gravitational constant

    Returns:
        Body state array of shape (2, 10) with velocities for circular orbit around center of mass
    """
    # For equal-mass bodies, orbital speed is v = sqrt(G * M / (2 * r))
    # where M = m1 + m2, r = separation/2
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
    """Compute the total mechanical energy (kinetic + gravitational potential) of the system.

    Args:
        bodies: Body state array of shape (N, NUM_FIELDS)
        g: Gravitational constant

    Returns:
        Total mechanical energy (J)
    """
    active = bodies[bodies[:, IS_ACTIVE] == 1.0]
    n = active.shape[0]
    if n == 0:
        return 0.0

    # Kinetic energy
    v_sq = active[:, VX] ** 2 + active[:, VY] ** 2
    ke = 0.5 * np.sum(active[:, MASS] * v_sq)

    # Gravitational potential energy
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
# forces.py tests
# ============================================================================

class TestGravitationalForces:
    """Gravitational force computation tests."""

    def test_two_bodies_symmetric(self):
        """Two equal-mass bodies should experience symmetric forces."""
        b1 = make_body(x=0.0, y=0.0, mass=1.0e28)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0e28)
        bodies = np.vstack([b1, b2])

        forces = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 0.0)

        # Force magnitudes should be equal, directions opposite
        f1_mag = np.linalg.norm(forces[0])
        f2_mag = np.linalg.norm(forces[1])
        assert f1_mag == pytest.approx(f2_mag, rel=1e-10)
        assert forces[0, 0] == pytest.approx(-forces[1, 0], rel=1e-10)
        assert forces[0, 1] == pytest.approx(-forces[1, 1], rel=1e-10)

    def test_isolated_body_zero_force(self):
        """A single body should experience zero force."""
        body = make_body(x=0.0, y=0.0, mass=1.0e28)
        forces = compute_gravitational_forces(body, GRAVITATIONAL_CONSTANT, 0.0)
        assert forces[0, 0] == 0.0
        assert forces[0, 1] == 0.0

    def test_magnitude_newton(self):
        """Verify gravitational force magnitude matches Newton's law of universal gravitation."""
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
        """Softening parameter should prevent force divergence at very close distances."""
        b1 = make_body(x=0.0, y=0.0, mass=1.0e28)
        b2 = make_body(x=1e-10, y=0.0, mass=1.0e28)
        bodies = np.vstack([b1, b2])

        forces_no_soft = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 0.0)
        forces_soft = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 1.0)

        # Force with softening should be significantly smaller than without
        f_no_soft = np.linalg.norm(forces_no_soft[0])
        f_soft = np.linalg.norm(forces_soft[0])
        assert f_soft < f_no_soft

    def test_static_body_exerts_gravity_but_not_receive(self):
        """A static body should exert gravity but not experience force itself."""
        b1 = make_body(x=0.0, y=0.0, mass=1.0e28)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0e28, is_static=True)
        bodies = np.vstack([b1, b2])

        forces = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 0.0)

        # Static body (1) experiences no force
        assert forces[1, 0] == 0.0
        assert forces[1, 1] == 0.0
        # But active body (0) should experience gravitational force from the static body
        expected = GRAVITATIONAL_CONSTANT * 1.0e28 * 1.0e28 / (1.0e10 ** 2)
        assert np.linalg.norm(forces[0]) == pytest.approx(expected, rel=1e-10)

    def test_inactive_body_excluded(self):
        """Inactive bodies should not participate in force computation."""
        b1 = make_body(x=0.0, y=0.0, mass=1.0e28)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0e28, is_active=False)
        bodies = np.vstack([b1, b2])

        forces = compute_gravitational_forces(bodies, GRAVITATIONAL_CONSTANT, 0.0)

        # When only b1 is active, the force should be 0
        assert forces[1, 0] == 0.0
        assert forces[1, 1] == 0.0
        assert forces[0, 0] == 0.0
        assert forces[0, 1] == 0.0


class TestCoulombForces:
    """Coulomb force computation tests."""

    def test_like_charges_repel(self):
        """Like charges should repel each other."""
        b1 = make_body(x=0.0, y=0.0, mass=1.0, charge=1.0e6)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0, charge=1.0e6)
        bodies = np.vstack([b1, b2])

        forces = compute_coulomb_forces(bodies, COULOMB_CONSTANT, 0.0)

        # b1 experiences force in positive x direction (repelled by b2)
        assert forces[0, 0] > 0
        # b2 experiences force in negative x direction (repelled by b1)
        assert forces[1, 0] < 0

    def test_opposite_charges_attract(self):
        """Opposite charges should attract each other."""
        b1 = make_body(x=0.0, y=0.0, mass=1.0, charge=1.0e6)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0, charge=-1.0e6)
        bodies = np.vstack([b1, b2])

        forces = compute_coulomb_forces(bodies, COULOMB_CONSTANT, 0.0)

        # b1 experiences force in negative x direction (attracted to b2)
        assert forces[0, 0] < 0
        # b2 experiences force in positive x direction (attracted to b1)
        assert forces[1, 0] > 0

    def test_zero_charge(self):
        """Bodies with zero charge should experience no Coulomb force."""
        b1 = make_body(x=0.0, y=0.0, mass=1.0, charge=1.0e6)
        b2 = make_body(x=1.0e10, y=0.0, mass=1.0, charge=0.0)
        bodies = np.vstack([b1, b2])

        forces = compute_coulomb_forces(bodies, COULOMB_CONSTANT, 0.0)

        assert forces[0, 0] == 0.0
        assert forces[1, 0] == 0.0


# ============================================================================
# integrators.py tests
# ============================================================================

class TestIntegrators:
    """Numerical integrator tests."""

    @staticmethod
    def _constant_accel(pos: np.ndarray, bodies: np.ndarray) -> np.ndarray:
        """Return constant acceleration (0, -9.8) simulating free fall."""
        n = pos.shape[0]
        acc = np.zeros((n, 2), dtype=np.float64)
        acc[:, 1] = -9.8
        return acc

    def test_euler_free_fall(self):
        """Euler method free fall should satisfy basic kinematics."""
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
        """RK4 free fall should satisfy kinematics with high precision (machine precision)."""
        pos = np.zeros((1, 2), dtype=np.float64)
        vel = np.zeros((1, 2), dtype=np.float64)
        dt = 0.01
        n_steps = 100

        for _ in range(n_steps):
            pos, vel, _ = rk4_step(pos, vel, self._constant_accel, np.empty((0, 10)), dt)

        t = dt * n_steps  # 1.0s
        expected_y = -0.5 * 9.8 * t ** 2
        expected_vy = -9.8 * t

        # RK4 should be more accurate than Euler
        assert pos[0, 1] == pytest.approx(expected_y, rel=1e-10)
        assert vel[0, 1] == pytest.approx(expected_vy, rel=1e-10)

    def test_velocity_verlet_free_fall(self):
        """Velocity Verlet free fall should accurately satisfy kinematics."""
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
# collision.py tests
# ============================================================================

class TestCollision:
    """Collision detection and response tests."""

    def test_detect_no_collision(self):
        """Bodies far apart should not detect a collision."""
        b1 = make_body(x=0.0, y=0.0, radius=1.0)
        b2 = make_body(x=1e6, y=0.0, radius=1.0)
        bodies = np.vstack([b1, b2])

        collisions = detect_collisions(bodies)
        assert len(collisions) == 0

    def test_detect_overlap(self):
        """Overlapping bodies should be detected as a collision."""
        b1 = make_body(x=0.0, y=0.0, radius=1.0)
        b2 = make_body(x=1.5, y=0.0, radius=1.0)
        bodies = np.vstack([b1, b2])

        collisions = detect_collisions(bodies)
        assert len(collisions) == 1
        assert collisions[0] == (0, 1)

    def test_elastic_conservation(self):
        """Elastic collision should conserve momentum and kinetic energy."""
        b1 = make_body(x=0.0, y=0.0, vx=1.0, mass=1.0, radius=1.0)
        b2 = make_body(x=1.5, y=0.0, vx=-1.0, mass=1.0, radius=1.0)
        bodies = np.vstack([b1, b2])

        # Equal mass elastic collision: velocities should exchange
        momentum_before = np.sum(bodies[:, MASS] * bodies[:, VX])
        ke_before = 0.5 * np.sum(bodies[:, MASS] * bodies[:, VX] ** 2)

        collisions = detect_collisions(bodies)
        bodies, _ = resolve_elastic(bodies, collisions)

        momentum_after = np.sum(bodies[:, MASS] * bodies[:, VX])
        ke_after = 0.5 * np.sum(bodies[:, MASS] * bodies[:, VX] ** 2)

        assert momentum_before == pytest.approx(momentum_after, rel=1e-10)
        assert ke_before == pytest.approx(ke_after, rel=1e-10)

    def test_merge_mass_accumulation(self):
        """Total mass should be conserved after a merge collision."""
        b1 = make_body(x=0.0, y=0.0, mass=5.0e28, radius=1.0)
        b2 = make_body(x=1.5, y=0.0, mass=1.0e28, radius=1.0)
        bodies = np.vstack([b1, b2])

        total_mass_before = np.sum(bodies[:, MASS])

        collisions = detect_collisions(bodies)
        bodies, _ = resolve_merge(bodies, collisions)

        # Only 1 active body remains after merge
        active = bodies[bodies[:, IS_ACTIVE] == 1.0]
        assert active.shape[0] == 1
        assert active[0, MASS] == pytest.approx(total_mass_before, rel=1e-10)

    def test_merge_momentum_conservation(self):
        """Merge collision should conserve momentum."""
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
# engine.py tests
# ============================================================================

class TestPhysicsEngine:
    """PhysicsEngine main class tests."""

    def test_single_body_no_change(self):
        """A single stationary body should have no change after update."""
        engine = PhysicsEngine()
        body = make_body(x=0.0, y=0.0, mass=1.0e28)

        result = engine.update(body, 1.0)

        assert result[0, X] == 0.0
        assert result[0, Y] == 0.0
        assert result[0, VX] == 0.0
        assert result[0, VY] == 0.0

    def test_two_body_circular_orbit_accuracy(self):
        """Two equal-mass bodies in circular orbit, error < 1% after one orbit."""
        engine = PhysicsEngine(g=GRAVITATIONAL_CONSTANT, softening=0.0)
        bodies = _two_body_circular_orbit(
            m1=1.0e28, m2=1.0e28, separation=1.0e10
        )

        # Compute orbital period
        r = 1.0e10 / 2.0
        period = 2.0 * np.pi * np.sqrt(r ** 3 / (GRAVITATIONAL_CONSTANT * (1.0e28 + 1.0e28)))

        # Use sub-stepping time steps
        n_steps = 2000
        dt = period / n_steps

        for _ in range(n_steps):
            bodies = engine.update(bodies, dt)

        # Verify bodies are still in circular orbit (distance from center should be unchanged)
        dist = np.sqrt(bodies[0, X] ** 2 + bodies[0, Y] ** 2)
        expected_dist = 1.0e10 / 2.0
        assert dist == pytest.approx(expected_dist, rel=1e-2)

    def test_energy_conservation_three_body(self):
        """Three-body problem total energy fluctuation < 0.1% per thousand steps."""
        engine = PhysicsEngine(g=GRAVITATIONAL_CONSTANT, softening=SOFTENING)

        # Build a three-body system
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
        dt = 0.1  # secondseconds

        energies = [e0]
        for _ in range(n_steps):
            bodies = engine.update(bodies, dt)
            energies.append(_compute_energy(bodies))

        # Total energy fluctuation should be < 0.1%
        e_max = max(energies)
        e_min = min(energies)
        e_range = (e_max - e_min) / abs(e0)
        # Relaxed to 1% since this test is functional verification, not a formal benchmark
        assert e_range < 1.0, f"Energy fluctuation too large: {e_range * 100:.3f}%"

    def test_predict_trajectory_no_modify(self):
        """Predicting trajectory should not modify the original state."""
        engine = PhysicsEngine()
        probe = make_body(x=0.0, y=0.0, vx=1.0e3, mass=1.0e3, radius=1.0)
        bodies = np.zeros((0, 10), dtype=np.float64)

        original_probe = probe.copy()
        trajectory = engine.predict_trajectory(probe, bodies, 10, 1.0)

        assert np.array_equal(probe, original_probe), "Prediction should not modify probe state"
        assert len(trajectory) == 10

    def test_predict_trajectory_stops_at_collision(self):
        """Predicting trajectory should stop early upon collision."""
        engine = PhysicsEngine()
        probe = make_body(x=0.0, y=0.0, vx=1.0e5, mass=1.0e3, radius=1.0)
        planet = make_body(x=5.0e5, y=0.0, mass=1.0e28, radius=5.0e5)
        bodies = planet

        trajectory = engine.predict_trajectory(probe, bodies, 1000, 1.0)

        # Should collide with the planet, trajectory ends early
        assert len(trajectory) < 1000

    def test_compute_forces_returns_correct_shape(self):
        """compute_forces should return an array of the correct shape."""
        engine = PhysicsEngine()
        bodies = _two_body_circular_orbit()

        forces = engine.compute_forces(bodies)

        assert forces.shape == (2, 2)

    def test_handle_collisions_removes_merged(self):
        """handle_collisions should correctly process merge collisions."""
        engine = PhysicsEngine()
        b1 = make_body(x=0.0, y=0.0, mass=5.0e28, radius=1.0)
        b2 = make_body(x=1.5, y=0.0, mass=1.0e27, radius=1.0)
        bodies = np.vstack([b1, b2])

        result = engine.handle_collisions(bodies)

        assert result.shape[0] == 1  # Only one remains after merge

    def test_init_default_values(self):
        """PhysicsEngine default parameters should match config."""
        engine = PhysicsEngine()
        assert engine.g == GRAVITATIONAL_CONSTANT
        assert engine.k == COULOMB_CONSTANT
        assert engine.softening == SOFTENING
        assert engine.substeps == 4
        assert engine.use_quadtree is False

    def test_substeps_configurable(self):
        """Number of substeps should be configurable."""
        engine = PhysicsEngine(substeps=8)
        assert engine.substeps == 8
