"""MiniSFS 核心类型与接口。

提供项目中所有模块共享的数据类型定义和抽象接口规范。

使用示例::

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
    # 方便访问的列常量
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
    # 类型常量
    "BodyField",
    "NUM_FIELDS",
    "X", "Y", "VX", "VY",
    "MASS", "CHARGE", "RADIUS",
    "BODY_TYPE", "IS_STATIC", "IS_ACTIVE",
    "BODY_TYPE_STAR", "BODY_TYPE_PLANET",
    "BODY_TYPE_PROBE", "BODY_TYPE_CHARGED",
    # 类型别名
    "WorldPoint", "ScreenPoint", "Velocity", "Force",
    # 工厂函数
    "create_body_state_array", "make_body",
    # 接口
    "IPhysicsEngine", "IQuadtree", "ITrailBuffer",
    "IRenderer", "ICamera", "IGameManager", "IInputHandler",
    # 数据结构
    "Rect",
]
