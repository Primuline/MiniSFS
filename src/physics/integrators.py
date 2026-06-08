"""Numerical integrator module.

Provides three integrators for numerical integration of celestial motion equations:
    - RK4 (Runge-Kutta 4th order): Main integrator, high precision, recommended for trajectory prediction
    - Euler (Explicit Euler): Fast and simple, but low precision and energy is not conserved
    - Velocity Verlet: Good energy conservation, suitable for long-term stable simulation

All integrators accept the same interface:
    f(state, bodies) -> acceleration: Function to compute acceleration
    state: shape (N, 2) position/velocity array (pos, vel)
    bodies: shape (N, NUM_FIELDS) celestial body state

Usage::

    from src.physics.integrators import rk4_step, euler_step, velocity_verlet_step
"""

from typing import Callable, Tuple

import numpy as np

# Acceleration function type: (pos: (N,2), bodies: (N, F)) -> acc: (N,2)
AccelFunc = Callable[[np.ndarray, np.ndarray], np.ndarray]


def euler_step(
    pos: np.ndarray,
    vel: np.ndarray,
    accel_fn: AccelFunc,
    bodies: np.ndarray,
    dt: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Explicit Euler integration for one step.

    Euler method updates velocity using current acceleration, then updates position using the new velocity:
        v_new = v + a * dt
        x_new = x + v_new * dt

    Args:
        pos: shape (N, 2) position array (m)
        vel: shape (N, 2) velocity array (m/s)
        accel_fn: Acceleration function accel_fn(pos, bodies) -> (N, 2)
        bodies: shape (N, NUM_FIELDS) celestial body state array (used for mass calculation)
        dt: Time step (s)

    Returns:
        (pos_new, vel_new, acc_new) tuple:
            pos_new: shape (N, 2) updated position
            vel_new: shape (N, 2) updated velocity
            acc_new: shape (N, 2) acceleration at new position (used by Velocity Verlet)
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
    """4th order Runge-Kutta integration for one step.

    RK4 is the recommended default integrator with high precision, suitable for accurate simulation and trajectory prediction.
    For the N-body problem, it requires 4 acceleration evaluations per step.

    Args:
        pos: shape (N, 2) position array (m)
        vel: shape (N, 2) velocity array (m/s)
        accel_fn: Acceleration function accel_fn(pos, bodies) -> (N, 2)
        bodies: shape (N, NUM_FIELDS) celestial body state array
        dt: Time step (s)

    Returns:
        (pos_new, vel_new, acc_new) tuple
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

    # Weighted average
    vel_new = vel + (dt / 6.0) * (a1 + 2.0 * a2 + 2.0 * a3 + a4)
    pos_new = pos + (dt / 6.0) * (vel + 2.0 * k2_vel + 2.0 * k3_vel + k4_vel)

    # Compute acceleration at the new position (for Velocity Verlet or external use)
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
    """Velocity Verlet integration for one step.

    Velocity Verlet is a symplectic integrator with better energy conservation than RK4 for long-term simulation.
    Requires the acceleration from the previous time step as input.

    Args:
        pos: shape (N, 2) position array (m)
        vel: shape (N, 2) velocity array (m/s)
        acc: shape (N, 2) current acceleration (m/s^2), from the previous time step
        accel_fn: Acceleration function accel_fn(pos, bodies) -> (N, 2)
        bodies: shape (N, NUM_FIELDS) celestial body state array
        dt: Time step (s)

    Returns:
        (pos_new, vel_new, acc_new) tuple
    """
    # Half-step position update
    pos_new = pos + vel * dt + 0.5 * acc * dt ** 2

    # Compute acceleration at the new position
    acc_new = accel_fn(pos_new, bodies)

    # Velocity update: average of old and new acceleration
    vel_new = vel + 0.5 * (acc + acc_new) * dt

    return pos_new, vel_new, acc_new
