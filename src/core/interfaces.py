"""MiniSFS 模块接口抽象定义。

所有核心模块通过此文件定义的抽象基类 (ABC) 进行交互。

接口设计原则:
    - **物理引擎不依赖 Pygame** — PhysicsEngine 的输入输出均为 NumPy 数组
    - **渲染器只读物理状态** — Renderer 接收 bodies 数组但不修改
    - **四叉树是纯数据结构** — Quadtree 不关心天体类型，只做空间划分
    - **可测试性** — 所有接口可在无 GUI 环境下实例化和测试
"""

from abc import ABC, abstractmethod
from typing import Dict, List, NamedTuple, Optional, Tuple

import numpy as np

from src.core.types import WorldPoint


class Rect(NamedTuple):
    """二维轴对齐矩形。

    Attributes:
        x: 矩形左上角 x 坐标
        y: 矩形左上角 y 坐标
        w: 矩形宽度
        h: 矩形高度
    """
    x: float
    y: float
    w: float
    h: float


# ============================================================================
# 物理引擎接口
# ============================================================================


class IPhysicsEngine(ABC):
    """物理引擎接口。

    负责多体引力/库仑力计算、数值积分、碰撞检测与响应。
    """

    @abstractmethod
    def update(self, bodies: np.ndarray, dt: float) -> np.ndarray:
        """更新所有天体状态一个时间步。

        内部流程:
            1. 计算所有天体之间的受力
            2. 用数值积分器更新速度和位置
            3. 检测并处理碰撞
            4. 移除 IS_ACTIVE == 0 的天体

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
            dt: 时间步长 (秒)

        Returns:
            更新后的天体状态数组 (可能移除或合并了天体，行数可能变化)
        """

    @abstractmethod
    def compute_forces(self, bodies: np.ndarray) -> np.ndarray:
        """计算所有天体受到的合力。

        返回 shape (N, 2) 的力数组，每行对应 (fx, fy)。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组

        Returns:
            shape (N, 2) 的合力数组 (N)
        """

    @abstractmethod
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
            bodies: shape (N, NUM_FIELDS) 的静态天体状态
            steps: 预测步数
            dt: 每步时间间隔 (秒)

        Returns:
            shape (M, 2) 的预测轨迹坐标数组 (M <= steps, 因碰撞会提前终止)
        """

    @abstractmethod
    def handle_collisions(self, bodies: np.ndarray) -> np.ndarray:
        """检测并处理碰撞。

        支持弹性碰撞 (质量加权速度交换) 和合并碰撞 (小质量天体被吸收)。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组

        Returns:
            处理碰撞后的天体状态数组
        """


# ============================================================================
# 四叉树接口
# ============================================================================


class IQuadtree(ABC):
    """四叉树接口。

    用于空间划分加速引力计算和碰撞检测。
    """

    @abstractmethod
    def insert(self, body_id: int, x: float, y: float) -> bool:
        """插入天体 ID 到四叉树。

        Args:
            body_id: 天体在 bodies 数组中的行索引
            x: 天体 x 坐标
            y: 天体 y 坐标

        Returns:
            插入成功返回 True，超出边界返回 False
        """

    @abstractmethod
    def rebuild(self, bodies: np.ndarray) -> None:
        """清空并重建四叉树。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
        """

    @abstractmethod
    def query_range(
        self, x: float, y: float, radius: float
    ) -> List[int]:
        """范围查询: 返回指定圆形区域内的天体 ID 列表。

        Args:
            x: 圆心 x 坐标
            y: 圆心 y 坐标
            radius: 圆形半径

        Returns:
            区域内的天体 ID 列表
        """

    @abstractmethod
    def query_nearest(
        self, x: float, y: float
    ) -> Optional[int]:
        """最近邻查询: 返回离指定坐标最近的天体 ID。

        Args:
            x: 查询点 x 坐标
            y: 查询点 y 坐标

        Returns:
            最近的天体 ID，无天体时返回 None
        """

    @abstractmethod
    def barnes_hut_force(
        self, body_id: int, bodies: np.ndarray, theta: float
    ) -> Tuple[float, float]:
        """使用 Barnes-Hut 近似计算指定天体受到的总引力。

        对于远距离节点，用节点质心代替子树中所有天体的分别计算。
        判断条件: s / d < theta (s=节点边长, d=到质心距离)

        Args:
            body_id: 目标天体的 ID
            bodies: 所有天体的状态数组
            theta: Barnes-Hut 阈值 (通常 0.5)

        Returns:
            (fx, fy) 合力向量 (N)
        """


# ============================================================================
# 尾迹缓冲区接口
# ============================================================================


class ITrailBuffer(ABC):
    """尾迹缓冲区接口。

    使用 collections.deque 为每个天体维护固定长度的历史轨迹。
    """

    @abstractmethod
    def push_frame(self, body_id: int, x: float, y: float) -> None:
        """追加一帧的坐标到指定天体的尾迹中。

        Args:
            body_id: 天体 ID
            x: 当前帧 x 坐标
            y: 当前帧 y 坐标
        """

    @abstractmethod
    def push_all(self, bodies: np.ndarray) -> None:
        """为所有活跃天体的当前位置追加尾迹帧。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
        """

    @abstractmethod
    def get_trail(self, body_id: int) -> List[Tuple[float, float]]:
        """获取指定天体的尾迹坐标列表 (从旧到新)。

        Args:
            body_id: 天体 ID

        Returns:
            坐标列表 [(x1,y1), (x2,y2), ...]，空列表表示无尾迹
        """

    @abstractmethod
    def rewind(self, body_id: int, frames: int) -> Optional[Tuple[float, float]]:
        """返回指定天体 frames 帧前的坐标。

        Args:
            body_id: 天体 ID
            frames: 回退帧数

        Returns:
            (x, y) 坐标，若历史不足则返回 None
        """

    @abstractmethod
    def clear(self, body_id: int) -> None:
        """清除指定天体的尾迹。

        Args:
            body_id: 天体 ID
        """

    @abstractmethod
    def clear_all(self) -> None:
        """清除所有天体的尾迹。"""


# ============================================================================
# 渲染器接口
# ============================================================================


class IRenderer(ABC):
    """渲染器接口。

    接收物理状态数组，绘制到 Pygame 窗口。
    渲染器**不修改**物理状态。
    """

    @abstractmethod
    def render(
        self,
        bodies: np.ndarray,
        trails: Dict[int, List[Tuple[float, float]]],
        camera: "ICamera",
    ) -> None:
        """渲染一帧画面。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
            trails: 尾迹数据 {body_id: [(x1,y1), (x2,y2), ...]}
            camera: 相机对象，用于世界坐标到屏幕坐标的转换
        """

    @abstractmethod
    def render_background(self) -> None:
        """渲染静态背景 (星云、网格等)。"""

    @abstractmethod
    def render_hud(self, game_state: str, score: Optional[Dict[str, float]]) -> None:
        """渲染 HUD 信息。

        Args:
            game_state: 当前游戏状态
            score: 评分数据 (可选)
        """

    @abstractmethod
    def render_predicted_trajectory(
        self, trajectory: np.ndarray, camera: "ICamera"
    ) -> None:
        """渲染预测轨迹 (虚线/半透明)。

        Args:
            trajectory: shape (M, 2) 的预测轨迹坐标
            camera: 相机对象
        """

    @abstractmethod
    def render_target_zone(
        self, x: float, y: float, radius: float, camera: "ICamera"
    ) -> None:
        """渲染目标区域 (脉冲动画)。

        Args:
            x, y: 目标中心世界坐标
            radius: 目标区域半径 (米)
            camera: 相机对象
        """


# ============================================================================
# 相机接口
# ============================================================================


class ICamera(ABC):
    """相机接口。

    管理视口变换: 世界坐标 <-> 屏幕坐标。
    """

    @abstractmethod
    def world_to_screen(
        self, world_x: float, world_y: float
    ) -> Tuple[int, int]:
        """世界坐标 转 屏幕像素坐标。

        Args:
            world_x: 世界 x 坐标 (m)
            world_y: 世界 y 坐标 (m)

        Returns:
            (screen_x, screen_y) 像素坐标
        """

    @abstractmethod
    def screen_to_world(
        self, screen_x: int, screen_y: int
    ) -> Tuple[float, float]:
        """屏幕像素坐标 转 世界坐标。

        Args:
            screen_x: 屏幕 x 坐标 (像素)
            screen_y: 屏幕 y 坐标 (像素)

        Returns:
            (world_x, world_y) 世界坐标 (m)
        """

    @abstractmethod
    def pan(self, dx: float, dy: float) -> None:
        """平移相机。

        Args:
            dx: x 方向偏移量 (像素)
            dy: y 方向偏移量 (像素)
        """

    @abstractmethod
    def zoom(self, factor: float, screen_center_x: int, screen_center_y: int) -> None:
        """以屏幕某点为中心缩放。

        Args:
            factor: 缩放倍数 (>1 放大, <1 缩小)
            screen_center_x: 缩放中心 x (像素)
            screen_center_y: 缩放中心 y (像素)
        """

    @abstractmethod
    def follow(self, world_x: float, world_y: float) -> None:
        """相机跟随指定世界坐标 (居中)。

        Args:
            world_x: 目标 x 坐标 (m)
            world_y: 目标 y 坐标 (m)
        """

    @abstractmethod
    def reset(self) -> None:
        """重置相机到初始位置和缩放。"""


# ============================================================================
# 游戏逻辑接口
# ============================================================================


class IGameManager(ABC):
    """游戏管理器接口。

    管理游戏状态机 (MENU -> PLAYING -> PAUSED / WIN / LOSE)、
    关卡加载、条件判定和评分。
    """

    @abstractmethod
    def load_level(self, level_id: str) -> np.ndarray:
        """加载关卡，返回该关卡的天体初始状态数组。

        Args:
            level_id: 关卡标识符 (如 "1-1", "1-2")

        Returns:
            shape (N, NUM_FIELDS) 的初始天体状态数组

        Raises:
            FileNotFoundError: 关卡文件不存在时
        """

    @abstractmethod
    def check_win_condition(
        self, probe_pos: Tuple[float, float]
    ) -> bool:
        """检查探测器是否到达目标区域。

        Args:
            probe_pos: 探测器当前世界坐标 (x, y)

        Returns:
            到达目标返回 True
        """

    @abstractmethod
    def check_lose_condition(
        self, probe: np.ndarray, bodies: np.ndarray, bounds: Rect
    ) -> bool:
        """检查是否满足失败条件。

        Args:
            probe: 探测器状态数组
            bodies: 所有天体状态数组
            bounds: 世界边界 (飞出即失败)

        Returns:
            失败返回 True
        """

    @abstractmethod
    def get_score(self) -> Dict[str, float]:
        """获取当前评分。

        Returns:
            {'stars': 3, 'time': 45.2, 'fuel': 0.7, 'total': 0.85}
            stars 为 1-3 整数，其余为浮点数
        """

    @abstractmethod
    def set_state(self, new_state: str) -> None:
        """设置游戏状态。

        Args:
            new_state: 新状态 (MENU / PLAYING / PAUSED / WIN / LOSE)
        """

    @abstractmethod
    def get_state(self) -> str:
        """获取当前游戏状态。"""


# ============================================================================
# 输入处理器接口
# ============================================================================


class IInputHandler(ABC):
    """输入处理器接口。

    将 Pygame 事件转换为游戏操作，与渲染逻辑分离。
    """

    @abstractmethod
    def process_events(self) -> List[str]:
        """处理所有待处理的 Pygame 事件。

        Returns:
            操作命令字符串列表, 如 ['SELECT:3', 'PAN_LEFT', 'ZOOM_IN', 'PAUSE']
        """

    @abstractmethod
    def get_mouse_world_pos(self, camera: ICamera) -> WorldPoint:
        """获取鼠标当前所在的世界坐标。

        Args:
            camera: 相机对象

        Returns:
            (x, y) 世界坐标
        """
