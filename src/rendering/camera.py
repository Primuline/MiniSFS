"""Camera system: manages viewport transformation and world/screen coordinate conversion.

Implements the ``ICamera`` interface (defined in ``src.core.interfaces``).

Supports:
    - Bidirectional world/screen coordinate conversion
    - Mouse drag panning
    - Scroll wheel zoom (centered on mouse position)
    - Double-click celestial body follow
    - R key reset view
"""

from typing import Dict, Tuple

import numpy as np

from src.config import (
    CAMERA_FOLLOW_LERP,
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
    """2D camera that manages viewport transformations.

    Maps world coordinates (meters) to screen coordinates (pixels).
    Zoom is centered on a screen point; panning does not affect zoom.

    Attributes:
        center_x: World x-coordinate corresponding to screen center (m)
        center_y: World y-coordinate corresponding to screen center (m)
        zoom: Zoom factor (1.0 = default scale)
        world_scale: World units per pixel (m/pixel), from config
    """

    def __init__(
        self,
        width: int = WINDOW_WIDTH,
        height: int = WINDOW_HEIGHT,
        world_scale: float = WORLD_SCALE,
    ) -> None:
        """Initialize the camera.

        Args:
            width: Screen width (pixels)
            height: Screen height (pixels)
            world_scale: World-to-pixel conversion ratio (m/pixel)
        """
        self.width: int = width
        self.height: int = height
        self.world_scale: float = world_scale

        # World coordinate corresponding to screen center
        self.center_x: float = 0.0
        self.center_y: float = 0.0

        # Zoom factor
        self._zoom: float = 1.0

        # Record initial state for reset
        self._initial_center_x: float = 0.0
        self._initial_center_y: float = 0.0
        self._initial_zoom: float = 1.0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def zoom(self) -> float:
        """Get the current zoom factor."""
        return self._zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        """Set the zoom factor, automatically clamped to valid range."""
        self._zoom = max(CAMERA_ZOOM_MIN, min(CAMERA_ZOOM_MAX, value))

    # ------------------------------------------------------------------
    # ICamera Interface Methods
    # ------------------------------------------------------------------

    def world_to_screen(
        self, world_x: float, world_y: float
    ) -> Tuple[int, int]:
        """Convert world coordinates to screen pixel coordinates.

        Args:
            world_x: World x-coordinate (m)
            world_y: World y-coordinate (m)

        Returns:
            (screen_x, screen_y) pixel coordinates
        """
        sx = (world_x - self.center_x) / self.world_scale * self._zoom + self.width / 2
        sy = (world_y - self.center_y) / self.world_scale * self._zoom + self.height / 2
        return int(round(sx)), int(round(sy))

    def screen_to_world(
        self, screen_x: int, screen_y: int
    ) -> Tuple[float, float]:
        """Convert screen pixel coordinates to world coordinates.

        Args:
            screen_x: Screen x-coordinate (pixels)
            screen_y: Screen y-coordinate (pixels)

        Returns:
            (world_x, world_y) world coordinates (m)
        """
        wx = (screen_x - self.width / 2) / self._zoom * self.world_scale + self.center_x
        wy = (screen_y - self.height / 2) / self._zoom * self.world_scale + self.center_y
        return wx, wy

    def pan(self, dx: float, dy: float) -> None:
        """Pan the camera.

        Convert screen pixel offset to world coordinate offset.

        Args:
            dx: X-direction offset (pixels, positive right)
            dy: Y-direction offset (pixels, positive down)
        """
        world_dx = dx * self.world_scale / self._zoom
        world_dy = dy * self.world_scale / self._zoom
        self.center_x += world_dx
        self.center_y += world_dy

    def zoom_at(self, factor: float, screen_center_x: int, screen_center_y: int) -> None:
        """Zoom centered on a screen point.

        Keep the world coordinate at the given screen point unchanged.

        Args:
            factor: Zoom factor (>1 zoom in, <1 zoom out)
            screen_center_x: Zoom center x (pixels)
            screen_center_y: Zoom center y (pixels)
        """
        # Record the world coordinate at this screen point before zoom
        world_x, world_y = self.screen_to_world(screen_center_x, screen_center_y)

        # Update zoom
        new_zoom = self._zoom * factor
        new_zoom = max(CAMERA_ZOOM_MIN, min(CAMERA_ZOOM_MAX, new_zoom))

        # Adjust center so this world coordinate still maps to the same screen position
        self.center_x = world_x - (screen_center_x - self.width / 2) / new_zoom * self.world_scale  # fmt: skip
        self.center_y = world_y - (screen_center_y - self.height / 2) / new_zoom * self.world_scale  # fmt: skip
        self._zoom = new_zoom

    def follow(self, world_x: float, world_y: float) -> None:
        """Camera follows the specified world coordinate (centers on it).

        Args:
            world_x: Target x-coordinate (m)
            world_y: Target y-coordinate (m)
        """
        self.center_x = world_x
        self.center_y = world_y

    def update_follow(self, target_x: float, target_y: float,
                      vel_x: float = 0.0, vel_y: float = 0.0,
                      dt: float = 0.0,
                      lerp_factor: float | None = None) -> None:
        """Smoothly follow target position (velocity feedforward + lerp interpolation).

        Uses velocity feedforward to predict the target's next-frame position, then lerps
        toward the prediction, significantly reducing steady-state offset under constant-
        velocity motion.

        Args:
            target_x: Target world x-coordinate (m)
            target_y: Target world y-coordinate (m)
            vel_x: Target x-velocity (m/s), used for feedforward prediction
            vel_y: Target y-velocity (m/s)
            dt: Per-frame physics simulation time (s), i.e., total time target moves this frame
            lerp_factor: Interpolation factor (0~1), defaults to CAMERA_FOLLOW_LERP
        """
        if lerp_factor is None:
            lerp_factor = CAMERA_FOLLOW_LERP
        # Velocity feedforward: predict target position at end of frame
        px = target_x + vel_x * dt
        py = target_y + vel_y * dt
        self.center_x += (px - self.center_x) * lerp_factor
        self.center_y += (py - self.center_y) * lerp_factor

    def reset(self) -> None:
        """Reset the camera to initial position and zoom."""
        self.center_x = self._initial_center_x
        self.center_y = self._initial_center_y
        self._zoom = self._initial_zoom

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def get_screen_rect_world(self) -> Tuple[float, float, float, float]:
        """Get the world-coordinate rectangle corresponding to the current screen view.

        Returns:
            (left, top, right, bottom) world coordinates (m)
        """
        left, top = self.screen_to_world(0, 0)
        right, bottom = self.screen_to_world(self.width, self.height)
        return left, top, right, bottom

    def world_distance_to_screen(self, world_dist: float) -> float:
        """Convert world distance to screen pixel distance.

        Args:
            world_dist: World distance (m)

        Returns:
            Pixel distance
        """
        return world_dist / self.world_scale * self._zoom

    def get_state(self) -> Dict[str, float]:
        """Return the current camera state.

        Returns:
            {'center_x': float, 'center_y': float, 'zoom': float} dictionary
        """
        return {
            'center_x': self.center_x,
            'center_y': self.center_y,
            'zoom': self._zoom,
        }

    def is_visible(self, world_x: float, world_y: float, margin: float = 0.0) -> bool:
        """Check if a world coordinate is within the current view (with margin).

        Args:
            world_x: World x-coordinate (m)
            world_y: World y-coordinate (m)
            margin: Margin (pixels), for early drawing or deferred culling

        Returns:
            True if visible
        """
        sx, sy = self.world_to_screen(world_x, world_y)
        return (
            -margin <= sx <= self.width + margin
            and -margin <= sy <= self.height + margin
        )
