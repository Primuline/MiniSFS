"""MiniSFS 核心数据类型定义。

所有模块共享的天体状态数组 (BodyState) 格式定义在此。
数组是一个 ``np.ndarray``，shape 为 ``(N, NUM_FIELDS)``，dtype 为 ``np.float64``。

各列的索引由 ``BodyField`` 命名元组定义，通过名称访问而不是硬编码数字。
"""

from typing import NamedTuple, Tuple

import numpy as np

# ============================================================================
# BodyState 数组字段索引定义
# ============================================================================


class BodyField(NamedTuple):
    """BodyState NumPy 数组的列索引与字段名称映射。

    使用方式::

        bodies[0, BodyField.X]       # 第一个天体的 x 坐标
        bodies[:, BodyField.VX:BodyField.VY+1]  # 所有天体的速度向量
    """

    # --- 位置 (Position) ---
    X: int = 0      # x 坐标 (m)
    Y: int = 1      # y 坐标 (m)

    # --- 速度 (Velocity) ---
    VX: int = 2     # x 方向速度 (m/s)
    VY: int = 3     # y 方向速度 (m/s)

    # --- 物理属性 (Physical Properties) ---
    MASS: int = 4       # 质量 (kg)
    CHARGE: int = 5     # 电荷 (C)
    RADIUS: int = 6     # 半径 (m)

    # --- 元数据 (Metadata) ---
    BODY_TYPE: int = 7   # 天体类型 (0=恒星, 1=行星, 2=探测器, 3=带电粒子)
    IS_STATIC: int = 8   # 是否静态 (0=动态, 1=静态, 静态天体不参与物理更新)
    IS_ACTIVE: int = 9   # 是否存活 (0=待移除, 1=存活)


# 天体状态数组的字段总数
NUM_FIELDS: int = 10

# 创建单例供快速访问 (使用模块级常量避免重复构造)
_FIELD = BodyField()

# 方便导入
X: int = _FIELD.X
Y: int = _FIELD.Y
VX: int = _FIELD.VX
VY: int = _FIELD.VY
MASS: int = _FIELD.MASS
CHARGE: int = _FIELD.CHARGE
RADIUS: int = _FIELD.RADIUS
BODY_TYPE: int = _FIELD.BODY_TYPE
IS_STATIC: int = _FIELD.IS_STATIC
IS_ACTIVE: int = _FIELD.IS_ACTIVE


# ============================================================================
# 天体类型枚举 (与 config.py 保持一致)
# ============================================================================

# 使用 int 常量而非 Enum 以兼容 NumPy 数组操作
BODY_TYPE_STAR: int = 0      # 恒星 — 大质量发光
BODY_TYPE_PLANET: int = 1    # 行星 — 普通天体 (无电荷)
BODY_TYPE_PROBE: int = 2     # 探测器 — 受玩家控制
BODY_TYPE_CHARGED: int = 3   # 带电粒子 — 受引力和库仑力影响


# ============================================================================
# 辅助类型别名
# ============================================================================

# 世界坐标 (x, y), 单位: m
WorldPoint = Tuple[float, float]

# 屏幕坐标 (x, y), 单位: 像素
ScreenPoint = Tuple[int, int]

# 速度向量 (vx, vy), 单位: m/s
Velocity = Tuple[float, float]

# 力向量 (fx, fy), 单位: N
Force = Tuple[float, float]


# ============================================================================
# 工厂函数
# ============================================================================


def create_body_state_array(n: int) -> np.ndarray:
    """创建一个 N 行 NUM_FIELDS 列的天体状态数组，初始化为零。

    Args:
        n: 天体数量

    Returns:
        shape (n, NUM_FIELDS) 的 float64 数组，所有天体默认存活且非静态
    """
    bodies = np.zeros((n, NUM_FIELDS), dtype=np.float64)
    bodies[:, IS_ACTIVE] = 1.0   # 默认存活
    bodies[:, IS_STATIC] = 0.0   # 默认动态
    return bodies


def make_body(
    x: float = 0.0,
    y: float = 0.0,
    vx: float = 0.0,
    vy: float = 0.0,
    mass: float = 1.0e28,
    charge: float = 0.0,
    radius: float = 8.0,
    body_type: int = BODY_TYPE_PLANET,
    is_static: bool = False,
    is_active: bool = True,
) -> np.ndarray:
    """创建一个单天体状态数组 (shape (1, NUM_FIELDS))。

    Args:
        x, y: 初始位置 (m)
        vx, vy: 初始速度 (m/s)
        mass: 质量 (kg)
        charge: 电荷 (C)
        radius: 半径 (m)
        body_type: 天体类型编号
        is_static: 是否静态
        is_active: 是否存活

    Returns:
        shape (1, NUM_FIELDS) 的 float64 数组
    """
    body = np.zeros((1, NUM_FIELDS), dtype=np.float64)
    body[0, X] = x
    body[0, Y] = y
    body[0, VX] = vx
    body[0, VY] = vy
    body[0, MASS] = mass
    body[0, CHARGE] = charge
    body[0, RADIUS] = radius
    body[0, BODY_TYPE] = float(body_type)
    body[0, IS_STATIC] = 1.0 if is_static else 0.0
    body[0, IS_ACTIVE] = 1.0 if is_active else 0.0
    return body
