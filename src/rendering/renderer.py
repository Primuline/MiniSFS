"""Rendering pipeline: draws physics state to the Pygame window.

Implements the ``IRenderer`` interface (defined in ``src.core.interfaces``).
The renderer does **not** modify physics state — it only reads BodyState arrays and TrailBuffer.
"""

import math
from typing import Dict, List, Optional, Tuple
import numpy as np

import numpy as np
import pygame

from src.config import (
    BACKGROUND_COLOR,
    BODY_TYPE_CHARGED,
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_STAR,
    DEFAULT_RADIUS_CHARGED,
    DEFAULT_RADIUS_PLANET,
    DEFAULT_RADIUS_PROBE,
    DEFAULT_RADIUS_STAR,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from src.core.interfaces import ICamera, IRenderer
from src.core.types import (
    BODY_TYPE,
    CHARGE,
    IS_ACTIVE,
    IS_STATIC,
    MASS,
    RADIUS,
    VX,
    VY,
    X,
    Y,
)
from src.rendering.effects import (
    StarField,
    draw_body_labels,
    draw_grid,
    draw_placement_trajectory,
    draw_predicted_trajectory,
    draw_shortcuts_overlay,
    draw_target_zone,
    draw_trails,
)


class Renderer(IRenderer):
    """Pygame renderer.

    Responsible for drawing the body state array to the window.
    render() is called each frame for a full draw.

    Attributes:
        width: Window width (pixels)
        height: Window height (pixels)
        star_field: Starfield background
    """

    def __init__(
        self,
        width: int = WINDOW_WIDTH,
        height: int = WINDOW_HEIGHT,
    ) -> None:
        """Initialize the renderer.

        Args:
            width: Window width (pixels)
            height: Window height (pixels)
        """
        self.width: int = width
        self.height: int = height

        # Create main window
        self.screen: pygame.Surface = pygame.display.set_mode(
            (width, height), pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        pygame.display.set_caption("MiniSFS")

        # Star field background
        self.star_field: StarField = StarField(
            num_stars_far=200,
            num_stars_near=100,
            width=width,
            height=height,
        )

        # Cached surface for starfield background
        self._background_surface: Optional[pygame.Surface] = None
        self._background_dirty: bool = True

        # Selected body ID
        self.selected_body_id: Optional[int] = None

        # Box selection state
        self.box_select_start: Optional[Tuple[int, int]] = None
        self.box_select_end: Optional[Tuple[int, int]] = None
        self.selected_body_ids: set = set()

        # Overlay toggle state (controlled by handler/main)
        self.show_grid: bool = False
        self.show_labels: bool = False
        self.show_shortcuts: bool = False

        # Accumulated time
        self._time: float = 0.0

        # Glow effect cache
        self._glow_cache: Dict[float, pygame.Surface] = {}

        # Fonts
        self._font_small: pygame.font.Font = pygame.font.Font(None, 18)
        self._font_medium: pygame.font.Font = pygame.font.Font(None, 24)
        self._font_large: pygame.font.Font = pygame.font.Font(None, 36)

    # ------------------------------------------------------------------
    # IRenderer interface methods
    # ------------------------------------------------------------------

    def render(
        self,
        bodies: np.ndarray,
        trails: Dict[int, List[Tuple[float, float]]],
        camera: ICamera,
        fade_factors: Optional[Dict[int, float]] = None,
    ) -> None:
        """Render a single frame.

        Draw order: background -> trails -> bodies -> selection highlight -> HUD

        Args:
            bodies: Body state array of shape (N, NUM_FIELDS)
            trails: Trail data {body_id: [(x1,y1), ...]}
            camera: Camera object
            fade_factors: Trail fade-out coefficients {body_id: fade_factor (0~1)}, optional
        """
        self._time += 1.0 / 60.0  # Approximate frame time

        # Update background
        self.star_field.update(1.0 / 60.0)

        # Clear screen
        self.screen.fill(BACKGROUND_COLOR)

        # Render background
        self.render_background()

        # Calculate speed for each body (used for trail color)
        body_speeds: Dict[int, float] = {}
        for i in range(bodies.shape[0]):
            vx = float(bodies[i, VX])
            vy = float(bodies[i, VY])
            body_speeds[i] = math.sqrt(vx * vx + vy * vy)

        # Draw trails (behind bodies)
        draw_trails(self.screen, trails, body_speeds, camera, fade_factors)

        # Draw bodies
        self._draw_bodies(bodies, camera)

        # Selection highlight (single + multi)
        if self.selected_body_id is not None or len(self.selected_body_ids) > 0:
            self._draw_selection_highlight(bodies, camera)

        # Overlays (rendered after bodies, before HUD)
        if self.show_grid:
            draw_grid(self.screen, camera)
        if self.show_labels:
            draw_body_labels(self.screen, bodies, camera)

    def render_background(self) -> None:
        """Render static background (starfield, grid, etc.)."""
        self.star_field.render(self.screen)

    def render_hud(
        self,
        game_state: str,
        score: Optional[Dict[str, float]] = None,
    ) -> None:
        """Render HUD information.

        Args:
            game_state: Current game state
            score: Score data (optional)
        """
        # FPS is displayed in the window title, not drawn here
        if game_state == "PAUSED":
            pause_text = self._font_large.render("PAUSED", True, (255, 255, 100))
            text_rect = pause_text.get_rect(center=(self.width // 2, 50))
            # Semi-transparent background
            bg_surf = pygame.Surface((text_rect.width + 20, text_rect.height + 10), pygame.SRCALPHA)
            bg_surf.fill((0, 0, 0, 128))
            self.screen.blit(bg_surf, (text_rect.x - 10, text_rect.y - 5))
            self.screen.blit(pause_text, text_rect)

        # Bottom status bar
        state_colors = {
            "PLAYING": (100, 220, 100),
            "PAUSED": (255, 255, 100),
            "WIN": (100, 255, 200),
            "LOSE": (255, 100, 100),
            "MENU": (200, 200, 200),
        }
        color = state_colors.get(game_state, (200, 200, 200))
        state_text = self._font_small.render(f"State: {game_state}", True, color)
        self.screen.blit(state_text, (10, self.height - 25))

        # Shortcut hints
        hint = "Space:Pause  R:Reset  Esc:Menu"
        hint_text = self._font_small.render(hint, True, (150, 150, 150))
        hr = hint_text.get_rect(right=self.width - 10, bottom=self.height - 5)
        self.screen.blit(hint_text, hr)

        # Shortcuts overlay (topmost layer)
        if self.show_shortcuts:
            draw_shortcuts_overlay(self.screen)

    def render_predicted_trajectory(
        self, trajectory: np.ndarray, camera: ICamera
    ) -> None:
        """Render a predicted trajectory (dashed / semi-transparent).

        Args:
            trajectory: Predicted trajectory coordinates of shape (M, 2)
            camera: Camera object
        """
        draw_predicted_trajectory(self.screen, trajectory, camera)

    def render_placement_trajectory(
        self,
        result: Dict[str, object],
        camera: ICamera,
    ) -> None:
        """Render trajectory preview for placement velocity setup.

        Args:
            result: Dictionary returned by predict_single_star_trajectory
            camera: Camera object
        """
        draw_placement_trajectory(self.screen, result, camera)

    def render_target_zone(
        self, x: float, y: float, radius: float, camera: ICamera
    ) -> None:
        """Render a target zone (pulse animation).

        Args:
            x, y: Target center world coordinates
            radius: Target zone radius (meters)
            camera: Camera object
        """
        draw_target_zone(self.screen, x, y, radius, camera, self._time)

    # ------------------------------------------------------------------
    # Internal drawing methods
    # ------------------------------------------------------------------

    def _draw_bodies(self, bodies: np.ndarray, camera: ICamera) -> None:
        """Draw all active bodies.

        Args:
            bodies: Body state array
            camera: Camera object
        """
        for i in range(bodies.shape[0]):
            if bodies[i, IS_ACTIVE] == 0.0:
                continue

            body_type = int(bodies[i, BODY_TYPE])
            wx = float(bodies[i, X])
            wy = float(bodies[i, Y])
            if np.isnan(wx) or np.isnan(wy):
                continue  # Skip bodies with invalid positions
            radius = float(bodies[i, RADIUS])
            mass = float(bodies[i, MASS])
            vx = float(bodies[i, VX])
            vy = float(bodies[i, VY])
            charge = float(bodies[i, CHARGE])
            is_static = bodies[i, IS_STATIC] == 1.0

            sx, sy = camera.world_to_screen(wx, wy)
            screen_radius = max(1.0, camera.world_distance_to_screen(radius))

            if body_type == BODY_TYPE_STAR:
                self._draw_star(sx, sy, screen_radius, mass)
            elif body_type == BODY_TYPE_PLANET:
                self._draw_planet(sx, sy, screen_radius, mass, is_static)
            elif body_type == BODY_TYPE_PROBE:
                self._draw_probe(sx, sy, screen_radius, vx, vy)
            elif body_type == BODY_TYPE_CHARGED:
                self._draw_charged(sx, sy, screen_radius, charge)

    def _draw_star(self, sx: int, sy: int, radius: float, mass: float) -> None:
        """Draw a star: radial gradient glow effect.

        Args:
            sx, sy: Screen center coordinates
            radius: Screen radius (pixels)
            mass: Mass (used for color)
        """
        # Brightness varies with mass
        intensity = min(1.0, mass / 1e31)
        r = min(255, int(200 + 55 * intensity))
        g = min(255, int(150 + 50 * intensity))
        b = min(220, int(100 + 40 * intensity))

        # Outer glow layer (large radius semi-transparent, max 200px to prevent OOM)
        glow_radius = min(radius * 3.0, 200.0)
        glow_surf = self._get_glow_surface(glow_radius, (r, g, b, 40))
        self.screen.blit(glow_surf, (sx - glow_radius, sy - glow_radius))

        # Mid glow layer (max 150px)
        mid_radius = min(radius * 2.0, 150.0)
        mid_surf = self._get_glow_surface(mid_radius, (r, g, b, 80))
        self.screen.blit(mid_surf, (sx - mid_radius, sy - mid_radius))

        # Core (brightest)
        core_radius = radius
        pygame.draw.circle(self.screen, (r, g, b), (sx, sy), int(core_radius))
        pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), max(1, int(core_radius * 0.4)))

    def _draw_planet(self, sx: int, sy: int, radius: float, mass: float, is_static: bool) -> None:
        """Draw a planet: solid circle + shadow.

        Args:
            sx, sy: Screen center coordinates
            radius: Screen radius (pixels)
            mass: Mass (used for color)
            is_static: Whether the body is static
        """
        # Mass determines color
        intensity = min(1.0, mass / 1e29)
        base_color = (
            int(100 + 100 * intensity),
            int(80 + 120 * intensity),
            int(180 + 50 * intensity),
        )

        if is_static:
            # Static bodies are darker
            base_color = tuple(c // 2 for c in base_color)

        # Main body
        pygame.draw.circle(self.screen, base_color, (sx, sy), int(radius))

        # Shadow (bottom-right semicircle)
        shadow_radius = int(radius)
        if shadow_radius > 2:
            shadow_surf = pygame.Surface((shadow_radius * 2, shadow_radius * 2), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 0))
            pygame.draw.circle(
                shadow_surf, (0, 0, 0, 60),
                (shadow_radius, shadow_radius), shadow_radius,
            )
            # Keep only the bottom-right part
            clip_surf = pygame.Surface((shadow_radius, shadow_radius), pygame.SRCALPHA)
            clip_surf.fill((0, 0, 0, 0))
            clip_surf.blit(shadow_surf, (0, 0), (shadow_radius, shadow_radius, shadow_radius, shadow_radius))
            self.screen.blit(clip_surf, (sx, sy))

        # Highlight (small bright circle in top-left)
        if radius > 4:
            highlight_radius = max(1, int(radius * 0.3))
            pygame.draw.circle(
                self.screen, (255, 255, 255, 60),
                (sx - int(radius * 0.25), sy - int(radius * 0.25)),
                highlight_radius,
            )

    def _draw_probe(self, sx: int, sy: int, radius: float, vx: float, vy: float) -> None:
        """Draw a probe: small circle + velocity direction indicator.

        Args:
            sx, sy: Screen center coordinates
            radius: Screen radius (pixels)
            vx, vy: Velocity components
        """
        # Main body
        probe_color = (200, 220, 255)
        pygame.draw.circle(self.screen, probe_color, (sx, sy), max(1, int(radius)))

        # Velocity direction indicator line
        speed = math.sqrt(vx * vx + vy * vy)
        if speed > 0.1:
            dir_len = radius * 2.5
            dx = vx / speed * dir_len
            dy = vy / speed * dir_len
            end_x = int(sx + dx)
            end_y = int(sy + dy)
            pygame.draw.line(self.screen, (100, 200, 255), (sx, sy), (end_x, end_y), 1)

    def _draw_charged(self, sx: int, sy: int, radius: float, charge: float) -> None:
        """Draw a charged particle with +/- sign.

        Args:
            sx, sy: Screen center coordinates
            radius: Screen radius (pixels)
            charge: Charge amount
        """
        # Color: positive charge red, negative charge blue
        if charge > 0:
            color = (255, 80, 80)
            sign = "+"
        else:
            color = (80, 130, 255)
            sign = "-"

        pygame.draw.circle(self.screen, color, (sx, sy), max(1, int(radius)))
        pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), max(1, int(radius)), 1)

        # Sign character
        sign_text = self._font_small.render(sign, True, (255, 255, 255))
        tr = sign_text.get_rect(center=(sx, sy))
        self.screen.blit(sign_text, tr)

    def _draw_selection_highlight(self, bodies: np.ndarray, camera: ICamera) -> None:
        """Draw a highlight ring around selected bodies.

        Draws highlights for both single-body selection (selected_body_id) and multi-selection (selected_body_ids).

        Args:
            bodies: Body state array
            camera: Camera object
        """
        # Collect body IDs that need highlighting
        highlight_ids: set = set()
        if self.selected_body_id is not None:
            highlight_ids.add(self.selected_body_id)
        highlight_ids.update(self.selected_body_ids)

        for idx in list(highlight_ids):
            if idx >= bodies.shape[0] or bodies[idx, IS_ACTIVE] == 0.0:
                if idx == self.selected_body_id:
                    self.selected_body_id = None
                continue

            wx = float(bodies[idx, X])
            wy = float(bodies[idx, Y])
            radius = float(bodies[idx, RADIUS])
            sx, sy = camera.world_to_screen(wx, wy)
            screen_radius = camera.world_distance_to_screen(radius)

            # Pulsing highlight
            pulse = 0.8 + 0.2 * math.sin(self._time * 4)
            highlight_r = screen_radius * 1.5 * pulse
            alpha = int(100 + 80 * (0.5 + 0.5 * math.sin(self._time * 4)))

            # Use temporary surface for alpha support
            size = int(highlight_r * 2) + 10
            hl_surf = pygame.Surface((size, size), pygame.SRCALPHA)
            hl_surf.fill((0, 0, 0, 0))
            pygame.draw.circle(
                hl_surf, (0, 200, 255, alpha),
                (size // 2, size // 2),
                highlight_r, 2,
            )
            self.screen.blit(hl_surf, (sx - size // 2, sy - size // 2))

    def _get_glow_surface(self, radius: float, color: Tuple[int, int, int, int]) -> pygame.Surface:
        """Get a cached glow surface.

        Uses cached radial gradient circles to avoid recreating every frame.

        Args:
            radius: Glow radius (pixels)
            color: RGBA color

        Returns:
            Semi-transparent glow Surface
        """
        # Use radius as cache key (rounded to 1px precision)
        cache_key = round(radius, 0)
        if cache_key not in self._glow_cache:
            safe_radius = min(radius, 200.0)  # Safety limit
            size = int(safe_radius * 2)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            surf.fill((0, 0, 0, 0))

            r, g, b, a = color
            cx, cy = size // 2, size // 2

            # Draw multiple semi-transparent circles for gradient effect
            layers = 8
            for i in range(layers):
                t = i / layers
                layer_r = radius * (1.0 - t)
                layer_a = int(a * (1.0 - t * 0.8))
                if layer_a <= 0:
                    continue
                pygame.draw.circle(
                    surf, (r, g, b, layer_a),
                    (cx, cy), int(layer_r),
                )

            self._glow_cache[cache_key] = surf

        return self._glow_cache[cache_key]

    # ------------------------------------------------------------------
    # Box selection drawing
    # ------------------------------------------------------------------

    def draw_box_selection(self) -> None:
        """Draw a blue semi-transparent selection box.

        Uses box_select_start and box_select_end to determine the selection range.
        Uses min/max of both coordinates so the box can be dragged in any direction.
        Only drawn when the box is larger than 10px.
        """
        start = self.box_select_start
        end = self.box_select_end
        if start is None or end is None:
            return

        x1, y1 = min(start[0], end[0]), min(start[1], end[1])
        x2, y2 = max(start[0], end[0]), max(start[1], end[1])

        # Do not draw boxes smaller than 10px (avoid flicker from tiny clicks)
        if (x2 - x1) < 10 and (y2 - y1) < 10:
            return

        # Semi-transparent fill
        s = pygame.Surface((x2 - x1, y2 - y1), pygame.SRCALPHA)
        s.fill((0, 100, 255, 60))
        self.screen.blit(s, (x1, y1))

        # Border
        pygame.draw.rect(
            self.screen, (0, 150, 255),
            (x1, y1, x2 - x1, y2 - y1), 1,
        )

    # ------------------------------------------------------------------
    # Custom particle placement preview methods
    # ------------------------------------------------------------------

    def draw_placement_preview(
        self, world_x: float, world_y: float,
        radius_world: float, camera: ICamera,
        surface: pygame.Surface,
    ) -> None:
        """Draw a dashed placement preview circle + crosshair.

        Args:
            world_x: Preview center world x coordinate (m)
            world_y: Preview center world y coordinate (m)
            radius_world: Preview radius in world coordinates (m)
            camera: Camera object
            surface: Target draw Surface
        """
        sx, sy = camera.world_to_screen(world_x, world_y)
        screen_radius = max(2.0, camera.world_distance_to_screen(radius_world))
        int_sr = int(screen_radius)
        isx, isy = int(sx), int(sy)

        color = (200, 200, 255)

        # Dashed circle: 32 segments, draw every other segment
        num_segments = 32
        for i in range(0, num_segments, 2):
            angle1 = 2.0 * math.pi * i / num_segments
            angle2 = 2.0 * math.pi * (i + 1) / num_segments
            x1 = isx + int_sr * math.cos(angle1)
            y1 = isy + int_sr * math.sin(angle1)
            x2 = isx + int_sr * math.cos(angle2)
            y2 = isy + int_sr * math.sin(angle2)
            pygame.draw.line(surface, color, (x1, y1), (x2, y2), 2)

        # Crosshair
        cross_len = max(5, int_sr // 3)
        pygame.draw.line(surface, color, (isx - cross_len, isy), (isx + cross_len, isy), 1)
        pygame.draw.line(surface, color, (isx, isy - cross_len), (isx, isy + cross_len), 1)

        # Center point
        pygame.draw.circle(surface, color, (isx, isy), 2)

    def draw_velocity_arrow(
        self, start_world: Tuple[float, float],
        end_screen: Tuple[int, int],
        max_length: float,
        camera: ICamera,
        surface: pygame.Surface,
    ) -> None:
        """Draw a velocity direction arrow (orange).

        The arrow points from start_world toward the mouse screen position, capped at max_length pixels.
        If longer than max_length, it is truncated but maintains direction.

        Args:
            start_world: Arrow start world coordinates (x, y)
            end_screen: Arrow end screen coordinates (sx, sy)
            max_length: Maximum arrow length (pixels)
            camera: Camera object
            surface: Target draw Surface
        """
        sx0, sy0 = camera.world_to_screen(start_world[0], start_world[1])
        ex, ey = end_screen

        dx = ex - sx0
        dy = ey - sy0
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 1.0:
            return

        # Truncate arrows exceeding max length
        if dist > max_length:
            dx = dx / dist * max_length
            dy = dy / dist * max_length
            ex = int(sx0 + dx)
            ey = int(sy0 + dy)

        isx0, isy0 = int(sx0), int(sy0)
        iex, iey = int(ex), int(ey)

        # Main line (orange, width 3)
        arrow_color = (255, 180, 50)
        pygame.draw.line(surface, arrow_color, (isx0, isy0), (iex, iey), 3)

        # Arrowhead triangle
        arrow_size = 12
        angle = math.atan2(dy, dx)  # Direction from start to end
        wing_angle = math.atan2(1.0, 1.0)  # ~45 degrees (actually math.pi/4)
        wing_offset = math.pi * 5.0 / 6.0  # 150 degrees, arrow wings spread backward

        wing1_x = iex + arrow_size * math.cos(angle + wing_offset)
        wing1_y = iey + arrow_size * math.sin(angle + wing_offset)
        wing2_x = iex + arrow_size * math.cos(angle - wing_offset)
        wing2_y = iey + arrow_size * math.sin(angle - wing_offset)

        pygame.draw.polygon(surface, arrow_color, [
            (iex, iey), (int(wing1_x), int(wing1_y)), (int(wing2_x), int(wing2_y))
        ])

    def set_title_fps(self, fps: float) -> None:
        """Display FPS in the window title.

        Args:
            fps: Current FPS
        """
        pygame.display.set_caption(f"MiniSFS - {fps:.0f} FPS")
