"""尾迹缓冲区实现。

使用 collections.deque 为每个天体维护固定长度的历史轨迹。
提供时间倒退 (rewind)、尾迹获取 (get_trail)、淡出 (fade-out) 等功能。

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
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from src.config import MAX_TRAIL_LENGTH
from src.core.interfaces import ITrailBuffer
from src.core.types import X, Y, IS_ACTIVE

# 淡出帧数：天体消失后尾迹持续显示的帧数
FADE_FRAMES: int = 60


class TrailBuffer(ITrailBuffer):
    """尾迹缓冲区，维护每个天体的历史坐标轨迹。

    使用 ``collections.deque`` 作为底层存储，固定最大长度。
    支持每帧追加、时间倒退、尾迹序列获取和淡出效果。

    当天体消失（碰撞合并或被删除）时，尾迹不会立刻消失，
    而是通过 ``_fade_counters`` 计数，在 FADE_FRAMES 帧内逐渐淡出。

    Attributes:
        maxlen: 每个天体最大轨迹点数
        fade_frames: 淡出持续帧数
    """

    def __init__(
        self,
        maxlen: int = MAX_TRAIL_LENGTH,
        fade_frames: int = FADE_FRAMES,
    ) -> None:
        """初始化尾迹缓冲区。

        Args:
            maxlen: 每个天体最大轨迹点数 (默认 MAX_TRAIL_LENGTH)
            fade_frames: 淡出持续帧数 (默认 FADE_FRAMES)
        """
        self._maxlen = maxlen
        self._fade_frames: int = fade_frames
        self._trails: Dict[int, deque] = {}
        self._fade_counters: Dict[int, int] = {}

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
                # 检测 body_id 复用：正常位移 < 1e10m，数组压缩导致的跳跃 > 1e11m
                if (x - lx) ** 2 + (y - ly) ** 2 > 1e20:
                    dq.clear()
        self._trails[body_id].append((float(x), float(y)))

    def push_all(self, bodies: np.ndarray, exclude: Optional[set] = None) -> None:
        """为所有活跃天体的当前位置追加尾迹帧。

        追加完成后，对已消失天体的尾迹启动淡出计数器。
        计数器达到 FADE_FRAMES 时才删除尾迹数据。

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
            exclude: 可选，要排除的天体 ID 集合（如被抓取拖拽的天体）
        """
        if exclude is None:
            exclude = set()
        active_set = set(int(idx) for idx in np.where(bodies[:, IS_ACTIVE] == 1.0)[0])
        for body_id in active_set:
            if body_id in exclude:
                continue
            self.push_frame(body_id, float(bodies[body_id, X]), float(bodies[body_id, Y]))
        # 残留尾迹处理：已消失的天体不删除，启动淡出计数器
        stale = [bid for bid in self._trails if bid not in active_set]
        for bid in stale:
            self._fade_counters[bid] = self._fade_counters.get(bid, 0) + 1
            if self._fade_counters[bid] >= self._fade_frames:
                del self._trails[bid]
                del self._fade_counters[bid]

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
        """清除指定天体的尾迹和淡出计数器。

        如果天体不存在，什么也不做。

        Args:
            body_id: 天体 ID
        """
        self._trails.pop(body_id, None)
        self._fade_counters.pop(body_id, None)

    def clear_all(self) -> None:
        """清除所有天体的尾迹和淡出计数器。"""
        self._trails.clear()
        self._fade_counters.clear()

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

    def get_fade_factor(self, body_id: int) -> float:
        """获取指定天体的尾迹淡出系数。

        存活的天体返回 1.0（不淡出）。
        正在淡出的天体返回 (FADE_FRAMES - counter) / FADE_FRAMES。
        无尾迹的天体返回 1.0。

        Args:
            body_id: 天体 ID

        Returns:
            淡出系数 (0.0 ~ 1.0)，1.0 = 完全可见，0.0 = 完全透明
        """
        if body_id not in self._fade_counters or body_id not in self._trails:
            return 1.0
        counter = self._fade_counters[body_id]
        return max(0.0, 1.0 - counter / self._fade_frames)

    def get_fade_factors(self) -> Dict[int, float]:
        """获取所有天体的尾迹淡出系数。

        Returns:
            {body_id: fade_factor} 字典，存活天体的系数为 1.0
        """
        result: Dict[int, float] = {}
        for bid in self._trails:
            result[bid] = self.get_fade_factor(bid)
        return result
