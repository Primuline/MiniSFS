"""MiniSFS 四叉树空间数据结构模块。

提供：
- 四叉树实现 (Quadtree) — 空间划分加速引力计算和碰撞检测
- Barnes-Hut 近似 (compute_force) — O(n log n) 引力加速
- 尾迹缓冲区 (TrailBuffer) — 基于 deque 的天体历史轨迹

依赖: NumPy, src.config, src.core
"""

from src.quadtree.quadtree import Quadtree, QuadtreeNode
from src.quadtree.barnes_hut import compute_force
from src.quadtree.trail import TrailBuffer

__all__ = [
    "Quadtree",
    "QuadtreeNode",
    "compute_force",
    "TrailBuffer",
]
