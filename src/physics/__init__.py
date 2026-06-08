"""MiniSFS 物理引擎模块。

提供多体模拟的核心组件:
    - ``forces``: 万有引力和库仑力的向量化计算
    - ``integrators``: 数值积分器（RK4, Euler, Velocity Verlet）
    - ``collision``: 碰撞检测与响应
    - ``engine``: PhysicsEngine 主类（实现 IPhysicsEngine 接口）

用法::

    from src.physics.engine import PhysicsEngine
    engine = PhysicsEngine()
    bodies = engine.update(bodies, dt)
"""

from src.physics.engine import PhysicsEngine

__all__ = [
    "PhysicsEngine",
]
