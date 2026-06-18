"""PhysicsEngine main class.

Implements the ``IPhysicsEngine`` interface (defined in ``src.core.interfaces``).
Combines forces, integrators, and collision modules to provide a complete N-body physics simulation.

Core workflow:
    1. ``update(bodies, dt)``: Multi-substep physics update
       - Each substep: compute total force -> integrate (default RK4) -> next substep
       - After all substeps: detect and resolve collisions
    2. ``predict_trajectory(probe, bodies, steps, dt)``: RK4 prediction
    3. ``compute_forces(bodies)``: gravity + Coulomb force
    4. ``handle_collisions(bodies)``: collision detection and response

Usage::

    from src.physics.engine import PhysicsEngine

    engine = PhysicsEngine()
    updated_bodies = engine.update(bodies, dt)
    trajectory = engine.predict_trajectory(probe, bodies, 120, dt)
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from src.config import (
    COULOMB_CONSTANT,
    GRAVITATIONAL_CONSTANT,
    QUADTREE_COLLISION_THRESHOLD,
    SOFTENING,
    SUBSTEPS,
)
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
    """N-body physics engine.

    Manages gravitational/Coulomb force calculations, numerical integration, and collision response.
    Supports substeps (SUBSTEPS) for improved stability, defaults to RK4 integrator.

    Attributes:
        g: gravitational constant
        k: Coulomb constant
        softening: softening parameter to prevent force divergence at close distances
        substeps: number of physics substeps per frame
        use_quadtree: whether to use quadtree acceleration (reserved for future use)
    """

    def __init__(
        self,
        g: float = GRAVITATIONAL_CONSTANT,
        k: float = COULOMB_CONSTANT,
        softening: float = SOFTENING,
        substeps: int = SUBSTEPS,
        use_quadtree: bool = False,
        quadtree_threshold: int = QUADTREE_COLLISION_THRESHOLD,
    ) -> None:
        """Initialize the physics engine.

        Args:
            g: gravitational constant, default 6.67430e-11
            k: Coulomb constant, default 8.98755e9
            softening: softening parameter (m), default 1.0
            substeps: number of substeps per frame, default 4
            use_quadtree: whether to enable quadtree acceleration, default no
            quadtree_threshold: active body count threshold for enabling quadtree broadphase
        """
        self.g: float = g
        self.k: float = k
        self.softening: float = softening
        self.substeps: int = substeps
        self.use_quadtree: bool = use_quadtree
        self.quadtree_threshold: int = quadtree_threshold
        self._quadtree: Optional[object] = None

        # Cache acceleration from the previous substep for Velocity Verlet
        self._last_acc: Optional[np.ndarray] = None

    def _acceleration_fn(
        self,
        pos: np.ndarray,
        bodies: np.ndarray,
    ) -> np.ndarray:
        """Compute acceleration (for full system update).

        Compute acceleration a = F / m for each body based on pos.
        Static bodies have their acceleration set to zero.

        Args:
            pos: shape (N, 2) position array, same number of rows as bodies
            bodies: shape (N, NUM_FIELDS) body state array

        Returns:
            shape (N, 2) acceleration array (m/s^2)
        """
        # Update all body positions with pos before computing forces
        bodies_snapshot = bodies.copy()
        bodies_snapshot[:, X] = pos[:, 0]
        bodies_snapshot[:, Y] = pos[:, 1]

        forces = compute_total_forces(
            bodies_snapshot, self.g, self.k, self.softening
        )

        masses = bodies_snapshot[:, MASS]
        # Avoid division by zero
        inv_mass = np.where(masses > 0, 1.0 / masses, 0.0)
        acc = forces * inv_mass[:, np.newaxis]  # (N, 2)

        # Zero out acceleration for static bodies
        static_mask = bodies_snapshot[:, IS_STATIC] == 1.0
        acc[static_mask] = 0.0

        return acc

    def _probe_acceleration_fn(
        self,
        pos: np.ndarray,
        sim_bodies: np.ndarray,
    ) -> np.ndarray:
        """Compute probe acceleration (for trajectory prediction).

        Only update the probe's position; other body positions remain unchanged.
        Returns probe acceleration with shape (1, 2).

        Args:
            pos: shape (1, 2) probe position
            sim_bodies: shape (N, NUM_FIELDS) combined array (idx 0 is the probe)

        Returns:
            shape (1, 2) probe acceleration array (m/s^2)
        """
        bodies_snapshot = sim_bodies.copy()
        # Only update the probe's position
        bodies_snapshot[0, X] = pos[0, 0]
        bodies_snapshot[0, Y] = pos[0, 1]

        forces = compute_total_forces(
            bodies_snapshot, self.g, self.k, self.softening
        )

        # Only return the probe's acceleration
        probe_mass = bodies_snapshot[0, MASS]
        if probe_mass > 0:
            probe_acc = forces[0:1] / probe_mass  # (1, 2)
        else:
            probe_acc = np.zeros((1, 2), dtype=np.float64)

        return probe_acc

    def compute_forces(self, bodies: np.ndarray) -> np.ndarray:
        """Compute the total force on all bodies.

        Args:
            bodies: shape (N, NUM_FIELDS) body state array

        Returns:
            shape (N, 2) total force array (N)
        """
        return compute_total_forces(bodies, self.g, self.k, self.softening)

    def update(self, bodies: np.ndarray, dt: float) -> np.ndarray:
        """Update all body states by one time step.

        Split dt into self.substeps substeps, each substep executes:
            1. Compute total forces
            2. RK4 integration to update position and velocity
        After all substeps, detect and resolve collisions, remove inactive bodies.

        Args:
            bodies: shape (N, NUM_FIELDS) body state array
            dt: time step (seconds)

        Returns:
            Updated body state array (row count may decrease due to collision merging)
        """
        bodies = bodies.copy()
        dt_sub = dt / self.substeps

        # Save initial positions and indices of bodies with IS_STATIC==1
        static_mask = bodies[:, IS_STATIC] == 1.0
        static_indices = np.where(static_mask)[0]
        if len(static_indices) > 0:
            saved_positions = bodies[np.ix_(static_indices, [X, Y])].copy()  # (N_static, 2)

        for _ in range(self.substeps):
            # Extract positions and velocities of all bodies
            pos = bodies[:, [X, Y]].copy()      # (N, 2)
            vel = bodies[:, [VX, VY]].copy()    # (N, 2)

            # RK4 integration step
            pos_new, vel_new, _ = rk4_step(
                pos, vel, self._acceleration_fn, bodies, dt_sub
            )

            # Update positions and velocities
            bodies[:, X] = pos_new[:, 0]
            bodies[:, Y] = pos_new[:, 1]
            bodies[:, VX] = vel_new[:, 0]
            bodies[:, VY] = vel_new[:, 1]

        # Restore static bodies' positions and zero out velocities (keep stars perfectly still)
        if len(static_indices) > 0:
            bodies[static_indices, X] = saved_positions[:, 0]
            bodies[static_indices, Y] = saved_positions[:, 1]
            bodies[static_indices, VX] = 0.0
            bodies[static_indices, VY] = 0.0

        # Collision broadphase (quadtree acceleration)
        collision_candidates = None
        if self.use_quadtree:
            n_active = int(np.sum(bodies[:, IS_ACTIVE] == 1.0))
            if n_active >= self.quadtree_threshold:
                if self._quadtree is None:
                    from src.quadtree.quadtree import Quadtree
                    from src.core.interfaces import Rect

                    self._quadtree = Quadtree(Rect(0, 0, 1, 1))
                self._quadtree.rebuild(bodies)
                collision_candidates = self._quadtree.query_collision_candidates()

        # Resolve collisions
        bodies, _ = resolve_collisions(bodies, collision_pairs=collision_candidates)

        # Remove inactive bodies
        bodies = self._remove_inactive(bodies)

        return bodies

    def predict_trajectory(
        self,
        probe: np.ndarray,
        bodies: np.ndarray,
        steps: int,
        dt: float,
    ) -> np.ndarray:
        """Predict the future trajectory of a probe.

        Use RK4 for prediction without modifying the real state.
        Stop prediction when the probe collides with a body or goes out of bounds.

        Args:
            probe: shape (1, NUM_FIELDS) probe state
            bodies: shape (N, NUM_FIELDS) body state array
            steps: number of prediction steps
            dt: time interval per step (seconds)

        Returns:
            shape (M, 2) predicted trajectory coordinate array (M <= steps)
        """
        trajectory: List[np.ndarray] = []
        probe_state = probe.copy()
        pos = probe_state[:, [X, Y]].copy()      # (1, 2)
        vel = probe_state[:, [VX, VY]].copy()    # (1, 2)

        # Do not modify original bodies during prediction, but the probe needs to interact with them
        # Add the probe to the body array as the 0th active body
        sim_bodies = np.vstack([probe_state, bodies])

        for _ in range(steps):
            pos, vel, _ = rk4_step(
                pos, vel, self._probe_acceleration_fn, sim_bodies, dt
            )

            # Update the probe's position in sim_bodies (for the next force calculation)
            sim_bodies[0, X] = pos[0, 0]
            sim_bodies[0, Y] = pos[0, 1]
            sim_bodies[0, VX] = vel[0, 0]
            sim_bodies[0, VY] = vel[0, 1]

            trajectory.append(pos[0].copy())

            # Collision detection: stop if the probe collides with any body
            probe_radius = probe_state[0, 6]  # RADIUS
            probe_pos = pos[0]
            for b_idx in range(1, sim_bodies.shape[0]):
                if sim_bodies[b_idx, IS_ACTIVE] == 0.0:
                    continue
                delta = probe_pos - sim_bodies[b_idx, [X, Y]]
                dist = np.sqrt(np.dot(delta, delta))
                body_radius = sim_bodies[b_idx, 6]  # RADIUS
                if dist < probe_radius + body_radius:
                    # Stop prediction
                    return np.array(trajectory)

        return np.array(trajectory)

    def predict_relative_trajectory(
        self,
        bodies: np.ndarray,
        probe_body_id: int,
        reference_body_id: int,
        steps: int,
        dt: float,
    ) -> np.ndarray:
        """Predict probe display coordinates in a moving reference frame.

        The copied full system is integrated at every prediction step, so the
        reference body's future position comes from the same N-body dynamics as
        the probe instead of a constant-velocity estimate.
        """
        if (
            probe_body_id < 0
            or reference_body_id < 0
            or probe_body_id >= bodies.shape[0]
            or reference_body_id >= bodies.shape[0]
            or steps <= 0
            or dt <= 0.0
        ):
            return np.empty((0, 2), dtype=np.float64)

        sim_bodies = bodies.copy()
        reference_current_pos = sim_bodies[reference_body_id, [X, Y]].copy()
        static_indices = np.where(sim_bodies[:, IS_STATIC] == 1.0)[0]
        saved_static_positions = sim_bodies[np.ix_(static_indices, [X, Y])].copy()

        pos = sim_bodies[:, [X, Y]].copy()
        vel = sim_bodies[:, [VX, VY]].copy()
        trajectory: List[np.ndarray] = []

        for _ in range(steps):
            pos, vel, _ = rk4_step(
                pos, vel, self._acceleration_fn, sim_bodies, dt
            )

            if len(static_indices) > 0:
                pos[static_indices] = saved_static_positions
                vel[static_indices] = 0.0

            sim_bodies[:, X] = pos[:, 0]
            sim_bodies[:, Y] = pos[:, 1]
            sim_bodies[:, VX] = vel[:, 0]
            sim_bodies[:, VY] = vel[:, 1]

            probe_future_pos = pos[probe_body_id].copy()
            reference_future_pos = pos[reference_body_id].copy()
            trajectory.append(
                reference_current_pos + (probe_future_pos - reference_future_pos)
            )

            probe_radius = float(sim_bodies[probe_body_id, RADIUS])
            for body_id in range(sim_bodies.shape[0]):
                if body_id == probe_body_id:
                    continue
                if sim_bodies[body_id, IS_ACTIVE] == 0.0:
                    continue
                delta = probe_future_pos - sim_bodies[body_id, [X, Y]]
                dist = float(np.sqrt(np.dot(delta, delta)))
                body_radius = float(sim_bodies[body_id, RADIUS])
                if dist < probe_radius + body_radius:
                    return np.array(trajectory)

        return np.array(trajectory)

    def handle_collisions(self, bodies: np.ndarray) -> np.ndarray:
        """Detect and resolve collisions.

        Args:
            bodies: shape (N, NUM_FIELDS) body state array

        Returns:
            Body state array after collision resolution
        """
        bodies, _ = resolve_collisions(bodies)
        return bodies

    def _remove_inactive(self, bodies: np.ndarray) -> np.ndarray:
        """Remove bodies with IS_ACTIVE == 0.

        Use boolean indexing to filter out active bodies.

        Args:
            bodies: shape (N, NUM_FIELDS) body state array

        Returns:
            Array containing only active bodies
        """
        active_mask = bodies[:, IS_ACTIVE] == 1.0
        return bodies[active_mask]

    def set_integrator(self, integrator: str) -> None:
        """Switch integrator (reserved interface).

        Currently only supports 'rk4'. Future support for 'euler' and 'velocity_verlet'.

        Args:
            integrator: integrator name ('rk4', 'euler', 'velocity_verlet')

        Raises:
            ValueError: unsupported integrator name
        """
        valid = {"rk4", "euler", "velocity_verlet"}
        if integrator not in valid:
            raise ValueError(
                f"Unsupported integrator '{integrator}', options: {valid}"
            )
        self._integrator = integrator

    # ------------------------------------------------------------------
    # Test query API (read-only, does not modify state)
    # ------------------------------------------------------------------

    def get_body_count(self, bodies: np.ndarray) -> int:
        """Return the number of active bodies.

        Args:
            bodies: shape (N, NUM_FIELDS) body state array

        Returns:
            Number of active bodies
        """
        active = bodies[bodies[:, IS_ACTIVE] == 1.0]
        return int(active.shape[0])

    def get_body_state(self, bodies: np.ndarray, body_id: int) -> Dict[str, object]:
        """Return the full state dictionary of the specified body.

        Args:
            bodies: shape (N, NUM_FIELDS) body state array
            body_id: row index of the body

        Returns:
            Dictionary containing x, y, vx, vy, mass, charge, radius, body_type, is_static, is_active
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
        """Compute total mechanical energy of the system (kinetic + gravitational potential), for verifying energy conservation.

        Args:
            bodies: shape (N, NUM_FIELDS) body state array

        Returns:
            Total mechanical energy (J)
        """
        active = bodies[bodies[:, IS_ACTIVE] == 1.0]
        n = active.shape[0]
        if n == 0:
            return 0.0

        # Kinetic energy
        v_sq = active[:, VX] ** 2 + active[:, VY] ** 2
        ke = 0.5 * float(np.sum(active[:, MASS] * v_sq))

        # Gravitational potential energy
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
        """Compute total momentum of the system (px, py), for verifying momentum conservation.

        Args:
            bodies: shape (N, NUM_FIELDS) body state array

        Returns:
            (px, py) total momentum (kg m/s)
        """
        active = bodies[bodies[:, IS_ACTIVE] == 1.0]
        if active.shape[0] == 0:
            return (0.0, 0.0)
        px = float(np.sum(active[:, MASS] * active[:, VX]))
        py = float(np.sum(active[:, MASS] * active[:, VY]))
        return (px, py)
