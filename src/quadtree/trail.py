"""尾迹缓冲区实现。

使用 collections.deque 为每个天体维护固定长度的历史轨迹。
提供时间倒退 (rewind)、尾迹获取 (get_trail) 等功能。

Typical usage::

    buffer = TrailBuffer(maxlen=300)
    buffer.push_frame(body_id, x, y)      # 每帧追加
    buffer.push_all(bodies)                # 批量追加
    trail = buffer.get_trail(body_id)      # 获取尾迹
    pos = buffer.rewind(body_id, frames=60)  # 倒退 60 帧
    buffer.clear(body_id)                  # 清除单个
    buffer.clear_all()                     # 清除所有
"""

from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.config import MAX_TRAIL_LENGTH
from src.core.interfaces import ITrailBuffer
from src.core.types import X, Y, IS_ACTIVE


class TrailBuffer(ITrailBuffer):
    """尾迹缓冲区，维护每个天体的历史坐标轨迹。

    使用 ``collections.deque`` 作为底层存储，固定最大长度。
    支持每帧追加、时间倒退和尾迹序列获取。

    Attributes:
        maxlen: 每个天体最大轨迹点数
    """

    def __init__(self, maxlen: int = MAX_TRAIL_LENGTH) -> None:
        """初始化尾迹缓冲区。

        Args:
            maxlen: 每个天体最大轨迹点数 (默认 MAX_TRAIL_LENGTH)
        """
        self._maxlen = maxlen
        self._trails: Dict[int, deque] = {}

    # ------------------------------------------------------------------
    # ITrailBuffer 接口方法
    # ------------------------------------------------------------------

    def push_frame(self, body_id: int, x: float, y: float) -> None:
        """追加一帧坐标到指定天体的尾迹中。

        如果该天体还没有尾迹，自动创建一个新的 deque。
        如果该 body_id 的前一帧到当前位置出现大幅度跳跃
        （> 1e12 m，表明数组压缩后 body_id 已对应不同天体），
        自动清空旧尾迹重新开始记录。

        Args:
            body_id: 天体 ID
            x: 当前帧 x 坐标
            y: 当前帧 y 坐标
        """
        if body_id not in self._trails:
            self._trails[body_id] = deque(maxlen=self._maxlen)
        else:
            dq = self._trails[body_id]
            if dq:
                lx, ly = dq[-1]
                # 1e12m ≈ 10 个轨道半径，远超一帧内的正常位移
                if (x - lx) ** 2 + (y - ly) ** 2 > 1e24:
                    dq.clear()
        self._trails[body_id].append((float(x), float(y)))

    def push_all(self, bodies: np.ndarray) -> None:
        """为所有活跃天体的当前位置追加尾迹帧。

        追加完成后，清理已不存在的天体的残留尾迹，避免
        天体被移除后旧尾迹出现在新放置的天体上。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
        """
        active_set = set(int(idx) for idx in np.where(bodies[:, IS_ACTIVE] == 1.0)[0])
        for body_id in active_set:
            self.push_frame(body_id, float(bodies[body_id, X]), float(bodies[body_id, Y]))
        # 清理残留尾迹（已被移除的天体）
        stale = [bid for bid in self._trails if bid not in active_set]
        for bid in stale:
            del self._trails[bid]

    def get_trail(self, body_id: int) -> List[Tuple[float, float]]:
        """获取指定天体的尾迹坐标列表 (从旧到新)。

        Args:
            body_id: 天体 ID

        Returns:
            坐标列表 [(x1, y1), (x2, y2), ...]，无尾迹时返回空列表
        """
        if body_id not in self._trails:
            return []
        return list(self._trails[body_id])

    def rewind(self, body_id: int, frames: int) -> Optional[Tuple[float, float]]:
        """返回指定天体 frames 帧前的坐标。

        读取 deque 的历史条目，frames=0 返回最新帧。
        如果历史不足 frames 帧，返回 None。

        Args:
            body_id: 天体 ID
            frames: 回退帧数 (>= 0)

        Returns:
            (x, y) 坐标，若历史不足则返回 None
        """
        if body_id not in self._trails:
            return None
        dq = self._trails[body_id]
        if len(dq) <= frames:
            return None
        # deque 支持索引访问 (Python 3.5+)
        # 正向索引 0 = 最旧, -1 = 最新
        # 要从最新的往后退 frames，需要从尾部算
        return dq[-(frames + 1)]

    def clear(self, body_id: int) -> None:
        """清除指定天体的尾迹。

        如果天体不存在，什么也不做。

        Args:
            body_id: 天体 ID
        """
        self._trails.pop(body_id, None)

    def clear_all(self) -> None:
        """清除所有天体的尾迹。"""
        self._trails.clear()

    # ------------------------------------------------------------------
    # 扩展方法
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """返回当前跟踪的天体数量。"""
        return len(self._trails)

    def get_all_trails(self) -> Dict[int, List[Tuple[float, float]]]:
        """获取所有天体的尾迹数据。

        Returns:
            {body_id: [(x, y), ...]} 字典
        """
        return {bid: list(dq) for bid, dq in self._trails.items()}

    def has_trail(self, body_id: int) -> bool:
        """检查指定天体是否有尾迹数据。

        Args:
            body_id: 天体 ID

        Returns:
            存在尾迹返回 True
        """
        return body_id in self._trails and len(self._trails[body_id]) > 0
