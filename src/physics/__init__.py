"""MiniSFS physics engine package.

Provides core components for multi-body simulation:
    - ``forces``: Vectorized gravitational and Coulomb force computation.
    - ``integrators``: Numerical integrators (RK4, Euler, Velocity Verlet).
    - ``collision``: Collision detection and response.
    - ``engine``: PhysicsEngine main class (implements IPhysicsEngine interface).

Usage::

    from src.physics.engine import PhysicsEngine
    engine = PhysicsEngine()
    bodies = engine.update(bodies, dt)
"""

from src.physics.engine import PhysicsEngine

__all__ = [
    "PhysicsEngine",
]
