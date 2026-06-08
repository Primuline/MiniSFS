"""MiniSFS core types and interfaces.

Provides shared data type definitions and abstract interface specifications
used by all modules in the project.

Usage example::

    from src.core.types import (
        BodyField, X, Y, VX, VY, MASS, CHARGE, RADIUS,
        BODY_TYPE, IS_STATIC, IS_ACTIVE,
        NUM_FIELDS, create_body_state_array, make_body,
    )

    from src.core.interfaces import (
        IPhysicsEngine, IQuadtree, ITrailBuffer,
        IRenderer, ICamera, IGameManager, IInputHandler,
        Rect,
    )
"""

from src.core.types import (
    BodyField,
    NUM_FIELDS,
    WorldPoint,
    ScreenPoint,
    Velocity,
    Force,
    create_body_state_array,
    make_body,
    # Convenience column constants
    X,
    Y,
    VX,
    VY,
    MASS,
    CHARGE,
    RADIUS,
    BODY_TYPE,
    IS_STATIC,
    IS_ACTIVE,
    BODY_TYPE_STAR,
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_CHARGED,
)

from src.core.interfaces import (
    IPhysicsEngine,
    IQuadtree,
    ITrailBuffer,
    IRenderer,
    ICamera,
    IGameManager,
    IInputHandler,
    Rect,
)

__all__ = [
    # Type constants
    "BodyField",
    "NUM_FIELDS",
    "X", "Y", "VX", "VY",
    "MASS", "CHARGE", "RADIUS",
    "BODY_TYPE", "IS_STATIC", "IS_ACTIVE",
    "BODY_TYPE_STAR", "BODY_TYPE_PLANET",
    "BODY_TYPE_PROBE", "BODY_TYPE_CHARGED",
    # Type aliases
    "WorldPoint", "ScreenPoint", "Velocity", "Force",
    # Factory functions
    "create_body_state_array", "make_body",
    # Interfaces
    "IPhysicsEngine", "IQuadtree", "ITrailBuffer",
    "IRenderer", "ICamera", "IGameManager", "IInputHandler",
    # Data structures
    "Rect",
]
