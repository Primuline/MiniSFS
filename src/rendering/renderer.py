"""Rendering pipeline: draws physics state to the Pygame window.

Implements the ``IRenderer`` interface (defined in ``src.core.interfaces``).
The renderer does **not** modify physics state — it only reads BodyState arrays and TrailBuffer.
"""

import math
from typing import Dict, List, Optional, Tuple

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
    UI_BLACK,
    UI_DARK,
    UI_DIM,
    UI_WHITE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    get_ui_font,
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
        star_field: Deprecated; monochrome mode uses a blank background.
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

        # Fonts
        self._font_small: pygame.font.Font = get_ui_font(18)
        self._font_medium: pygame.font.Font = get_ui_font(24)
        self._font_large: pygame.font.Font = get_ui_font(36)

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

        # Clear screen
        self.screen.fill(BACKGROUND_COLOR)

        # Background is intentionally empty for the black/white geometry style.
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
        """Render static background.

        The old starfield is intentionally removed; the screen clear in
        ``render`` is the full background pass.
        """

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
            pause_text = self._font_large.render("PAUSED", True, UI_WHITE)
            text_rect = pause_text.get_rect(center=(self.width // 2, 50))
            bg_rect = pygame.Rect(
                text_rect.x - 10,
                text_rect.y - 5,
                text_rect.width + 20,
                text_rect.height + 10,
            )
            pygame.draw.rect(self.screen, UI_BLACK, bg_rect)
            pygame.draw.rect(self.screen, UI_WHITE, bg_rect, 2)
            self.screen.blit(pause_text, text_rect)

        # Bottom status bar
        state_text = self._font_small.render(f"State: {game_state}", True, UI_WHITE)
        self.screen.blit(state_text, (56, self.height - 25))

        # Shortcut hints
        hint = "Space:Pause  R:Reset  Esc:Menu"
        hint_text = self._font_small.render(hint, True, UI_DIM)
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
                landing_normal = self._probe_landing_normal(bodies, i)
                speed = math.sqrt(vx * vx + vy * vy)
                if landing_normal is None and speed <= 1.0:
                    # Fallback: orient away from nearest non-probe body
                    probe_pos = bodies[i, [X, Y]]
                    min_dist = float("inf")
                    nearest_dir = None
                    for j in range(bodies.shape[0]):
                        if j == i or int(bodies[j, BODY_TYPE]) == BODY_TYPE_PROBE:
                            continue
                        if bodies[j, IS_ACTIVE] == 0.0:
                            continue
                        delta = probe_pos - bodies[j, [X, Y]]
                        dist = float(np.linalg.norm(delta))
                        if dist < min_dist and dist > 1e-12:
                            min_dist = dist
                            nearest_dir = (float(delta[0] / dist), float(delta[1] / dist))
                    landing_normal = nearest_dir
                self._draw_probe(sx, sy, screen_radius, vx, vy, landing_normal)
            elif body_type == BODY_TYPE_CHARGED:
                self._draw_charged(sx, sy, screen_radius, charge)

    def _draw_star(self, sx: int, sy: int, radius: float, mass: float) -> None:
        """Draw a star as a rotating regular 17-gon.

        Args:
            sx, sy: Screen center coordinates
            radius: Screen radius (pixels)
            mass: Mass (unused, kept for interface symmetry)
        """
        del mass
        draw_radius = max(4.0, radius)
        rotation = pygame.time.get_ticks() * 0.0012
        points = self._regular_polygon_points(sx, sy, draw_radius, 17, rotation)
        pygame.draw.polygon(self.screen, UI_BLACK, points)
        pygame.draw.polygon(self.screen, UI_WHITE, points, 2)
        pygame.draw.circle(self.screen, UI_WHITE, (sx, sy), max(2, int(draw_radius * 0.28)), 1)

    def _draw_planet(self, sx: int, sy: int, radius: float, mass: float, is_static: bool) -> None:
        """Draw a planet as a monochrome circle.

        Args:
            sx, sy: Screen center coordinates
            radius: Screen radius (pixels)
            mass: Mass (unused, kept for interface symmetry)
            is_static: Whether the body is static
        """
        del mass
        draw_radius = max(2, int(radius))
        fill = UI_DARK if is_static else UI_WHITE
        pygame.draw.circle(self.screen, fill, (sx, sy), draw_radius)
        pygame.draw.circle(self.screen, UI_WHITE, (sx, sy), draw_radius, 2)
        if not is_static and draw_radius > 4:
            pygame.draw.circle(self.screen, UI_BLACK, (sx, sy), max(1, draw_radius // 2), 1)

    def _probe_landing_normal(self, bodies: np.ndarray, probe_id: int) -> Optional[Tuple[float, float]]:
        """Return the outward host normal when a probe is resting on a body."""
        probe_pos = bodies[probe_id, [X, Y]]
        probe_vel = bodies[probe_id, [VX, VY]]
        probe_side = float(bodies[probe_id, RADIUS])
        for host_id in range(bodies.shape[0]):
            if host_id == probe_id:
                continue
            if (
                bodies[host_id, IS_ACTIVE] == 0.0
                or int(bodies[host_id, BODY_TYPE]) == BODY_TYPE_PROBE
            ):
                continue

            delta = probe_pos - bodies[host_id, [X, Y]]
            dist = float(np.linalg.norm(delta))
            if dist < 1e-12:
                continue
            contact_dist = float(bodies[host_id, RADIUS] + probe_side)
            tolerance = max(1.0, probe_side * 0.05)
            relative_speed = float(np.linalg.norm(probe_vel - bodies[host_id, [VX, VY]]))
            if abs(dist - contact_dist) <= tolerance and relative_speed <= 1.0:
                return (float(delta[0] / dist), float(delta[1] / dist))

        return None

    def _draw_probe(
        self,
        sx: int,
        sy: int,
        side_length: float,
        vx: float,
        vy: float,
        landing_normal: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Draw a probe as an equilateral triangle with a marked nose.

        Args:
            sx, sy: Screen center coordinates
            side_length: Triangle side length in screen pixels
            vx, vy: Velocity components
            landing_normal: Optional outward normal from a landed host body.
        """
        speed = math.sqrt(vx * vx + vy * vy)
        if landing_normal is not None:
            angle = math.atan2(landing_normal[1], landing_normal[0])
        else:
            angle = math.atan2(vy, vx) if speed > 0.1 else 0.0

        side = max(5.1, side_length * 2.0 * math.sqrt(3.0))
        height = math.sqrt(3.0) * side / 2.0
        nose_dist = height * 2.0 / 3.0
        base_dist = height / 3.0
        half_side = side / 2.0
        px = -math.sin(angle)
        py = math.cos(angle)
        nose = (
            int(sx + math.cos(angle) * nose_dist),
            int(sy + math.sin(angle) * nose_dist),
        )
        base_mid_x = sx - math.cos(angle) * base_dist
        base_mid_y = sy - math.sin(angle) * base_dist
        left = (
            int(base_mid_x + px * half_side),
            int(base_mid_y + py * half_side),
        )
        right = (
            int(base_mid_x - px * half_side),
            int(base_mid_y - py * half_side),
        )
        pygame.draw.polygon(self.screen, UI_WHITE, [nose, left, right])
        pygame.draw.polygon(self.screen, UI_BLACK, [nose, left, right], 1)
        pygame.draw.circle(self.screen, UI_BLACK, nose, max(2, int(side * 0.12)))
        pygame.draw.circle(self.screen, UI_WHITE, nose, max(2, int(side * 0.12)), 1)

    def _draw_charged(self, sx: int, sy: int, radius: float, charge: float) -> None:
        """Draw a charged particle with +/- sign.

        Args:
            sx, sy: Screen center coordinates
            radius: Screen radius (pixels)
            charge: Charge amount
        """
        sign = "+" if charge >= 0 else "-"
        draw_radius = max(4, int(radius))
        fill = UI_WHITE if charge >= 0 else UI_BLACK
        sign_color = UI_BLACK if charge >= 0 else UI_WHITE

        pygame.draw.circle(self.screen, fill, (sx, sy), draw_radius)
        pygame.draw.circle(self.screen, UI_WHITE, (sx, sy), draw_radius, 2)

        # Sign character
        sign_text = self._font_small.render(sign, True, sign_color)
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

            pulse = 0.8 + 0.2 * math.sin(self._time * 4)
            highlight_r = max(6, int(screen_radius * 1.5 * pulse))
            pygame.draw.circle(self.screen, UI_WHITE, (sx, sy), highlight_r, 1)

    @staticmethod
    def _regular_polygon_points(
        sx: int,
        sy: int,
        radius: float,
        sides: int,
        rotation: float,
    ) -> List[Tuple[int, int]]:
        """Return screen points for a regular polygon."""
        return [
            (
                int(sx + math.cos(rotation + math.tau * i / sides) * radius),
                int(sy + math.sin(rotation + math.tau * i / sides) * radius),
            )
            for i in range(sides)
        ]

    # ------------------------------------------------------------------
    # Box selection drawing
    # ------------------------------------------------------------------

    def draw_box_selection(self) -> None:
        """Draw a monochrome selection box.

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

        pygame.draw.rect(self.screen, UI_WHITE, (x1, y1, x2 - x1, y2 - y1), 1)

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

        color = UI_WHITE

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
        """Draw a monochrome velocity direction arrow.

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

        arrow_color = UI_WHITE
        pygame.draw.line(surface, arrow_color, (isx0, isy0), (iex, iey), 3)

        # Arrowhead triangle
        arrow_size = 12
        angle = math.atan2(dy, dx)  # Direction from start to end
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
