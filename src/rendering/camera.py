"""相机系统：管理视口变换与世界坐标<->屏幕坐标的转换。

实现 ``ICamera`` 接口（定义在 ``src.core.interfaces``）。

支持：
    - 世界坐标 <-> 屏幕坐标双向转换
    - 鼠标拖拽平移
    - 滚轮缩放（以鼠标位置为中心）
    - 双击天体跟随
    - R 键重置视角
"""

from typing import Tuple

import numpy as np

from src.config import (
    CAMERA_PAN_SPEED,
    CAMERA_ZOOM_MAX,
    CAMERA_ZOOM_MIN,
    CAMERA_ZOOM_SPEED,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    WORLD_SCALE,
)
from src.core.interfaces import ICamera


class Camera(ICamera):
    """2D 相机，管理视口变换。

    将世界坐标（米）映射到屏幕坐标（像素）。
    缩放以屏幕某点为中心进行，平移不影响缩放。

    Attributes:
        center_x: 屏幕中心对应的世界 x 坐标 (m)
        center_y: 屏幕中心对应的世界 y 坐标 (m)
        zoom: 缩放倍数 (1.0 = 默认比例)
        world_scale: 世界单位/像素比 (m/pixel)，来自 config
    """

    def __init__(
        self,
        width: int = WINDOW_WIDTH,
        height: int = WINDOW_HEIGHT,
        world_scale: float = WORLD_SCALE,
    ) -> None:
        """初始化相机。

        Args:
            width: 屏幕宽度（像素）
            height: 屏幕高度（像素）
            world_scale: 世界单位与像素的换算比例 (m/pixel)
        """
        self.width: int = width
        self.height: int = height
        self.world_scale: float = world_scale

        # 屏幕中心对应的世界坐标
        self.center_x: float = 0.0
        self.center_y: float = 0.0

        # 缩放倍数
        self._zoom: float = 1.0

        # 记录初始状态用于 reset
        self._initial_center_x: float = 0.0
        self._initial_center_y: float = 0.0
        self._initial_zoom: float = 1.0

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def zoom(self) -> float:
        """获取当前缩放倍数。"""
        return self._zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        """设置缩放倍数，自动钳制在有效范围内。"""
        self._zoom = max(CAMERA_ZOOM_MIN, min(CAMERA_ZOOM_MAX, value))

    # ------------------------------------------------------------------
    # ICamera 接口方法
    # ------------------------------------------------------------------

    def world_to_screen(
        self, world_x: float, world_y: float
    ) -> Tuple[int, int]:
        """世界坐标转屏幕像素坐标。

        Args:
            world_x: 世界 x 坐标 (m)
            world_y: 世界 y 坐标 (m)

        Returns:
            (screen_x, screen_y) 像素坐标
        """
        sx = (world_x - self.center_x) / self.world_scale * self._zoom + self.width / 2
        sy = (world_y - self.center_y) / self.world_scale * self._zoom + self.height / 2
        return int(round(sx)), int(round(sy))

    def screen_to_world(
        self, screen_x: int, screen_y: int
    ) -> Tuple[float, float]:
        """屏幕像素坐标转世界坐标。

        Args:
            screen_x: 屏幕 x 坐标（像素）
            screen_y: 屏幕 y 坐标（像素）

        Returns:
            (world_x, world_y) 世界坐标 (m)
        """
        wx = (screen_x - self.width / 2) / self._zoom * self.world_scale + self.center_x
        wy = (screen_y - self.height / 2) / self._zoom * self.world_scale + self.center_y
        return wx, wy

    def pan(self, dx: float, dy: float) -> None:
        """平移相机。

        将屏幕像素偏移量转换为世界坐标偏移量。

        Args:
            dx: x 方向偏移量 (像素，正值向右)
            dy: y 方向偏移量 (像素，正值向下)
        """
        world_dx = dx * self.world_scale / self._zoom
        world_dy = dy * self.world_scale / self._zoom
        self.center_x += world_dx
        self.center_y += world_dy

    def zoom(self, factor: float, screen_center_x: int, screen_center_y: int) -> None:
        """以屏幕某点为中心缩放。

        保持指定屏幕坐标对应的世界坐标不变。

        Args:
            factor: 缩放倍数 (>1 放大, <1 缩小)
            screen_center_x: 缩放中心 x (像素)
            screen_center_y: 缩放中心 y (像素)
        """
        # 记录缩放前该屏幕点对应的世界坐标
        world_x, world_y = self.screen_to_world(screen_center_x, screen_center_y)

        # 更新缩放
        new_zoom = self._zoom * factor
        new_zoom = max(CAMERA_ZOOM_MIN, min(CAMERA_ZOOM_MAX, new_zoom))

        # 调整 center 使得该世界坐标仍映射到相同的屏幕位置
        self.center_x = world_x - (screen_center_x - self.width / 2) / new_zoom * self.world_scale  # fmt: skip
        self.center_y = world_y - (screen_center_y - self.height / 2) / new_zoom * self.world_scale  # fmt: skip
        self._zoom = new_zoom

    def follow(self, world_x: float, world_y: float) -> None:
        """相机跟随指定世界坐标（居中）。

        Args:
            world_x: 目标 x 坐标 (m)
            world_y: 目标 y 坐标 (m)
        """
        self.center_x = world_x
        self.center_y = world_y

    def reset(self) -> None:
        """重置相机到初始位置和缩放。"""
        self.center_x = self._initial_center_x
        self.center_y = self._initial_center_y
        self._zoom = self._initial_zoom

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def get_screen_rect_world(self) -> Tuple[float, float, float, float]:
        """获取当前屏幕视野对应的世界坐标矩形。

        Returns:
            (left, top, right, bottom) 世界坐标 (m)
        """
        left, top = self.screen_to_world(0, 0)
        right, bottom = self.screen_to_world(self.width, self.height)
        return left, top, right, bottom

    def world_distance_to_screen(self, world_dist: float) -> float:
        """将世界距离转换为屏幕像素距离。

        Args:
            world_dist: 世界距离 (m)

        Returns:
            像素距离
        """
        return world_dist / self.world_scale * self._zoom

    def is_visible(self, world_x: float, world_y: float, margin: float = 0.0) -> bool:
        """判断世界坐标是否在当前视野内（含边距）。

        Args:
            world_x: 世界 x 坐标 (m)
            world_y: 世界 y 坐标 (m)
            margin: 边距（像素），用于提前绘制或延迟裁剪

        Returns:
            可见返回 True
        """
        sx, sy = self.world_to_screen(world_x, world_y)
        return (
            -margin <= sx <= self.width + margin
            and -margin <= sy <= self.height + margin
        )
