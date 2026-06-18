"""Effects module: trail rendering, predicted trajectories, and particles.

Provides standalone drawing functions for the Renderer.
All functions read data and draw to a Pygame Surface without modifying physics state.
"""

import math
import random
from typing import Dict, List, Optional, Tuple

import numpy as np
import pygame

from src.config import (
    DASH_GAP,
    DASH_OFF,
    DASH_ON,
    GRID_ALPHA,
    GRID_COLOR,
    LABEL_BG_ALPHA,
    LABEL_FONT_SIZE,
    LABEL_MIN_SCREEN_RADIUS,
    LABEL_OFFSET_Y,
    TRAIL_ALPHA_NEW,
    TRAIL_ALPHA_OLD,
    TRAIL_COLOR_FAST,
    TRAIL_COLOR_SLOW,
    UI_BLACK,
    UI_DIM,
    UI_OVERLAY_BG,
    UI_WHITE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    get_ui_font,
)
from src.core.types import BODY_TYPE, IS_ACTIVE, RADIUS, VX, VY, X, Y

# ============================================================================
# Starfield Background
# ============================================================================


class StarField:
    """Starfield background: randomly distributed stars with slow drift.

    Stars are divided into two layers:
        - Far layer: small, dim, slow drift
        - Near layer: large, bright, fast drift
    """

    def __init__(
        self,
        num_stars_far: int = 200,
        num_stars_near: int = 100,
        width: int = WINDOW_WIDTH,
        height: int = WINDOW_HEIGHT,
    ) -> None:
        """Initialize the star field.

        Args:
            num_stars_far: Number of far-layer stars
            num_stars_near: Number of near-layer stars
            width: Viewport width (pixels)
            height: Viewport height (pixels)
        """
        del num_stars_far, num_stars_near
        self.width: int = width
        self.height: int = height
        self.far_stars: List[dict] = []
        self.near_stars: List[dict] = []
        self._time: float = 0.0
        self._surface: Optional[pygame.Surface] = None

    def update(self, dt: float) -> None:
        """Update star positions (drift).

        Args:
            dt: Time delta (seconds)
        """
        self._time += dt

        for star in self.far_stars:
            star["x"] += star["drift_x"] * dt * 60
            star["y"] += star["drift_y"] * dt * 60
            # Wrap around
            if star["x"] < 0:
                star["x"] += self.width
            if star["x"] > self.width:
                star["x"] -= self.width
            if star["y"] < 0:
                star["y"] += self.height
            if star["y"] > self.height:
                star["y"] -= self.height

        for star in self.near_stars:
            star["x"] += star["drift_x"] * dt * 60
            star["y"] += star["drift_y"] * dt * 60
            if star["x"] < 0:
                star["x"] += self.width
            if star["x"] > self.width:
                star["x"] -= self.width
            if star["y"] < 0:
                star["y"] += self.height
            if star["y"] > self.height:
                star["y"] -= self.height

    def render(self, surface: pygame.Surface) -> None:
        """Render the background star field.

        Args:
            surface: Target Pygame Surface
        """
        del surface


# ============================================================================
# Trail Drawing
# ============================================================================


def draw_trails(
    surface: pygame.Surface,
    trails: Dict[int, List[Tuple[float, float]]],
    body_speeds: Dict[int, float],
    camera: "ICamera",  # type: ignore
    fade_factors: Optional[Dict[int, float]] = None,
) -> None:
    """Draw trails for all bodies.

    Each trail is drawn with line segments, with color interpolating from old to new (alpha + hue).
    Faster bodies get warmer trail colors, slower bodies get cooler colors.
    Supports fade factors: trails of removed bodies fade out via fade_factor.

    Args:
        surface: Target Pygame Surface
        trails: Trail data {body_id: [(x1,y1), (x2,y2), ...]} (oldest to newest)
        body_speeds: Current body speeds {body_id: speed_magnitude}
        camera: Camera object
        fade_factors: Fade-out coefficients {body_id: fade_factor (0~1)}, default None (all 1.0)
    """
    # Get speed range for color normalization
    if body_speeds:
        max_speed = max(body_speeds.values()) if body_speeds else 1.0
    else:
        max_speed = 1.0
    max_speed = max(max_speed, 1.0)  # Avoid division by zero

    for body_id, trail_points in trails.items():
        if len(trail_points) < 2:
            continue

        speed = body_speeds.get(body_id, 0.0)
        speed_ratio = min(speed / max_speed, 1.0)

        # Determine base hue based on speed
        r_slow, g_slow, b_slow = TRAIL_COLOR_SLOW
        r_fast, g_fast, b_fast = TRAIL_COLOR_FAST
        base_r = int(r_slow + (r_fast - r_slow) * speed_ratio)
        base_g = int(g_slow + (g_fast - g_slow) * speed_ratio)
        base_b = int(b_slow + (b_fast - b_slow) * speed_ratio)

        # Get the fade-out factor for this body
        body_fade = 1.0
        if fade_factors is not None and body_id in fade_factors:
            body_fade = fade_factors[body_id]

        n_points = len(trail_points)

        # Draw line by line from old to new
        for i in range(n_points - 1):
            x1, y1 = trail_points[i]
            x2, y2 = trail_points[i + 1]

            # Convert to screen coordinates
            sx1, sy1 = camera.world_to_screen(x1, y1)
            sx2, sy2 = camera.world_to_screen(x2, y2)

            # Calculate segment alpha (interpolate old-to-new, then multiply by fade factor)
            t = i / (n_points - 1)  # 0 = oldest, 1 = newest
            alpha = int((TRAIL_ALPHA_OLD + (TRAIL_ALPHA_NEW - TRAIL_ALPHA_OLD) * t) * body_fade)
            alpha = max(0, min(255, alpha))

            # Width gradient (old segments thin, new segments thick)
            width = max(1.0, t * 2.5)

            # Slight color adjustment along the gradient
            r = int(base_r * (0.5 + 0.5 * t))
            g = int(base_g * (0.5 + 0.5 * t))
            b = int(base_b * (0.5 + 0.5 * t))

            color = (r, g, b, alpha)
            _draw_alpha_line(surface, color, (sx1, sy1), (sx2, sy2), width)


def _draw_alpha_line(
    surface: pygame.Surface,
    color: Tuple[int, int, int, int],
    start: Tuple[int, int],
    end: Tuple[int, int],
    width: float = 1.0,
) -> None:
    """Draw a line with per-segment alpha support.

    Pygame's draw.line does not support per-line alpha, so a temporary surface is used.

    Args:
        surface: Target Surface
        color: (R, G, B, A) color
        start: Start point (x, y)
        end: End point (x, y)
        width: Line width
    """
    r, g, b, a = color
    if a <= 0:
        return

    # Create temporary surface for alpha rendering
    line_surf = pygame.Surface((abs(end[0] - start[0]) + 3, abs(end[1] - start[1]) + 3), pygame.SRCALPHA)
    line_surf.fill((0, 0, 0, 0))

    # Draw on the temporary surface (relative coordinates)
    ox, oy = min(start[0], end[0]) - 1, min(start[1], end[1]) - 1
    local_start = (start[0] - ox, start[1] - oy)
    local_end = (end[0] - ox, end[1] - oy)

    pygame.draw.line(line_surf, (r, g, b, a), local_start, local_end, max(1, int(width)))
    surface.blit(line_surf, (ox, oy))


# ============================================================================
# Predicted Trajectory Drawing
# ============================================================================


def draw_predicted_trajectory(
    surface: pygame.Surface,
    trajectory: np.ndarray,
    camera: "ICamera",  # type: ignore
) -> None:
    """Draw predicted trajectory (dashed / semi-transparent).

    Args:
        surface: Target Pygame Surface
        trajectory: Predicted trajectory coordinate array of shape (M, 2)
        camera: Camera object
    """
    if trajectory.shape[0] < 2:
        return

    points_screen: List[Tuple[int, int]] = []
    for i in range(trajectory.shape[0]):
        sx, sy = camera.world_to_screen(
            float(trajectory[i, 0]), float(trajectory[i, 1])
        )
        points_screen.append((sx, sy))

    # Dash segments: draw every few segments
    dash_length = 6
    gap_length = 4
    total_segments = len(points_screen) - 1

    for i in range(total_segments):
        # Alternate segments visible/hidden
        if (i // 3) % 2 == 0:
            alpha = 120 - int(80 * (i / total_segments))
            alpha = max(30, alpha)
            color = (*UI_WHITE, alpha)
            _draw_alpha_line(
                surface, color,
                points_screen[i], points_screen[i + 1],
                1.5,
            )

    # Endpoint marker (small circle)
    if len(points_screen) > 0:
        last = points_screen[-1]
        pygame.draw.circle(surface, (*UI_WHITE, 100), last, 3, 1)


def draw_placement_trajectory(
    surface: pygame.Surface,
    result: Dict[str, object],
    camera: "ICamera",  # type: ignore
) -> None:
    """Draw trajectory preview when setting placement velocity.

    Resamples the world-space trajectory into equal screen-pixel-spaced points, then draws a dashed line.
    Collision end shows a red dot, escape end fades out, orbited end shows a green dot.

    Args:
        surface: Target Pygame Surface
        result: Dictionary returned by predict_single_star_trajectory, must contain:
            - "trajectory": trajectory coordinates of shape (N, 2)
            - "collided": bool
            - "escaped": bool
            - "orbited": bool
        camera: Camera object
    """
    trajectory = result["trajectory"]
    if not isinstance(trajectory, np.ndarray) or trajectory.shape[0] < 2:
        return

    collided: bool = bool(result.get("collided", False))
    escaped: bool = bool(result.get("escaped", False))
    orbited: bool = bool(result.get("orbited", False))

    # Step 1: Convert world coordinates to screen coordinates
    pts: List[Tuple[float, float]] = []
    for i in range(trajectory.shape[0]):
        sx, sy = camera.world_to_screen(
            float(trajectory[i, 0]), float(trajectory[i, 1])
        )
        pts.append((sx, sy))

    if len(pts) < 2:
        return

    # Step 2: Resample to equal screen pixel spacing
    resampled: List[Tuple[float, float]] = [pts[0]]
    accumulated: float = 0.0
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i - 1][0]
        dy = pts[i][1] - pts[i - 1][1]
        seg_len = math.sqrt(dx * dx + dy * dy)
        if seg_len < 0.5:
            continue
        accumulated += seg_len
        if accumulated >= DASH_GAP:
            # Linear interpolation to DASH_GAP position
            t = (accumulated - DASH_GAP) / seg_len
            ix = pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t
            iy = pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t
            resampled.append((ix, iy))
            accumulated = 0.0
    # Ensure the last point is included
    if len(resampled) >= 1 and resampled[-1] != pts[-1]:
        resampled.append(pts[-1])

    if len(resampled) < 2:
        return

    # Step 3: Draw dashed line (DASH_ON px drawn -> DASH_OFF px skipped)
    draw_state: str = "on"
    draw_len: float = 0.0
    for i in range(1, len(resampled)):
        dx = resampled[i][0] - resampled[i - 1][0]
        dy = resampled[i][1] - resampled[i - 1][1]
        seg_len = math.sqrt(dx * dx + dy * dy)
        if seg_len < 0.5:
            continue

        if draw_state == "on":
            _draw_alpha_line(
                surface, (*UI_WHITE, 150),
                (int(resampled[i - 1][0]), int(resampled[i - 1][1])),
                (int(resampled[i][0]), int(resampled[i][1])),
                2.0,
            )
            draw_len += seg_len
            if draw_len >= DASH_ON:
                draw_state = "off"
                draw_len = 0.0
        else:
            draw_len += seg_len
            if draw_len >= DASH_OFF:
                draw_state = "on"
                draw_len = 0.0

    # Step 4: Endpoint marker
    if len(resampled) > 0:
        last = (int(resampled[-1][0]), int(resampled[-1][1]))
        if collided:
            pygame.draw.line(
                surface, UI_WHITE,
                (last[0] - 5, last[1] - 5),
                (last[0] + 5, last[1] + 5),
                2,
            )
            pygame.draw.line(
                surface, UI_WHITE,
                (last[0] - 5, last[1] + 5),
                (last[0] + 5, last[1] - 5),
                2,
            )
        elif orbited:
            pygame.draw.circle(surface, UI_WHITE, last, 4)
        elif escaped:
            pygame.draw.circle(surface, UI_WHITE, last, 3, 1)
        else:
            pygame.draw.circle(surface, UI_WHITE, last, 3, 1)


# ============================================================================
# Collision Particle Effects
# ============================================================================


class Particle:
    """Single particle for collision effects, exhaust effects, etc."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        color: Tuple[int, int, int],
        lifetime: float = 1.0,
        radius: float = 2.0,
    ) -> None:
        """Initialize a particle.

        Args:
            x, y: Initial position (pixels)
            vx, vy: Initial velocity (pixels/second)
            color: RGB color
            lifetime: Lifetime (seconds)
            radius: Particle radius (pixels)
        """
        self.x: float = x
        self.y: float = y
        self.vx: float = vx
        self.vy: float = vy
        self.color: Tuple[int, int, int] = color
        self.lifetime: float = lifetime
        self.max_lifetime: float = lifetime
        self.radius: float = radius
        self.alive: bool = True

    def update(self, dt: float) -> None:
        """Update particle state.

        Args:
            dt: Time delta (seconds)
        """
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False
            return

        # Simple motion (no gravity)
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Drag deceleration
        self.vx *= 0.98
        self.vy *= 0.98

    def render(self, surface: pygame.Surface) -> None:
        """Render the particle.

        Args:
            surface: Target Surface
        """
        if not self.alive:
            return

        alpha = int(255 * (self.lifetime / self.max_lifetime))
        alpha = max(0, min(255, alpha))
        r, g, b = self.color
        grey = int((r + g + b) / 3)
        fade = self.lifetime / self.max_lifetime
        c = int(grey * fade)

        # Use temporary surface for alpha support
        size = int(self.radius * 2) + 2
        particle_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        particle_surf.fill((0, 0, 0, 0))
        pygame.draw.circle(
            particle_surf, (c, c, c, alpha),
            (size // 2, size // 2), self.radius,
        )
        surface.blit(particle_surf, (self.x - size // 2, self.y - size // 2))


class ParticleSystem:
    """Particle system manager: manages the lifecycle of a group of particles."""

    def __init__(self) -> None:
        """Initialize the particle system."""
        self.particles: List[Particle] = []
        self._next_id: int = 0

    def emit_explosion(
        self,
        x: float,
        y: float,
        color: Tuple[int, int, int],
        count: int = 20,
        speed: float = 200.0,
    ) -> None:
        """Emit explosion particles at a given position.

        Args:
            x, y: Explosion center (pixels)
            color: Main color
            count: Number of particles
            speed: Initial particle speed (pixels/second)
        """
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            spd = random.uniform(speed * 0.3, speed)
            lifetime = random.uniform(0.3, 1.0)
            radius = random.uniform(1.0, 3.0)
            # Slight color variation
            r_offset = random.randint(-30, 30)
            g_offset = random.randint(-30, 30)
            b_offset = random.randint(-30, 30)
            particle_color = (
                max(0, min(255, color[0] + r_offset)),
                max(0, min(255, color[1] + g_offset)),
                max(0, min(255, color[2] + b_offset)),
            )
            self.particles.append(Particle(
                x=x, y=y,
                vx=math.cos(angle) * spd,
                vy=math.sin(angle) * spd,
                color=particle_color,
                lifetime=lifetime,
                radius=radius,
            ))

    def emit_probe_exhaust(
        self,
        x: float,
        y: float,
        angle: float,
        count: int = 3,
    ) -> None:
        """Emit exhaust particles from the probe's tail.

        Args:
            x, y: Emission position (pixels)
            angle: Emission direction (radians), tail direction is opposite
            count: Particles per frame
        """
        for _ in range(count):
            # Tail direction
            spread = random.uniform(-0.3, 0.3)
            dir_angle = angle + math.pi + spread
            spd = random.uniform(50, 150)
            lifetime = random.uniform(0.1, 0.4)
            radius = random.uniform(1.0, 2.5)
            c = random.randint(180, 255)
            self.particles.append(Particle(
                x=x, y=y,
                vx=math.cos(dir_angle) * spd,
                vy=math.sin(dir_angle) * spd,
                color=(c, c, c),
                lifetime=lifetime,
                radius=radius,
            ))

    def update(self, dt: float) -> None:
        """Update all particles.

        Args:
            dt: Time delta (seconds)
        """
        for p in self.particles:
            p.update(dt)
        # Remove dead particles
        self.particles = [p for p in self.particles if p.alive]

    def render(self, surface: pygame.Surface) -> None:
        """Render all particles.

        Args:
            surface: Target Surface
        """
        for p in self.particles:
            p.render(surface)

    def clear(self) -> None:
        """Clear all particles."""
        self.particles.clear()


# ============================================================================
# Target Zone Pulse Animation
# ============================================================================


def draw_target_zone(
    surface: pygame.Surface,
    world_x: float,
    world_y: float,
    radius: float,
    camera: "ICamera",  # type: ignore
    time: float = 0.0,
) -> None:
    """Render a target zone (pulse animation).

    Draws a pulsating halo indicating the target area the probe needs to reach.

    Args:
        surface: Target Surface
        world_x, world_y: Target center world coordinates
        radius: Target zone radius (world units)
        camera: Camera object
        time: Accumulated time (seconds) for pulse animation
    """
    sx, sy = camera.world_to_screen(world_x, world_y)
    screen_radius = camera.world_distance_to_screen(radius)

    # Three pulsing rings
    for i in range(3):
        phase = time * 1.5 + i * 2.094  # 2pi/3 phase offset
        pulse = 0.3 + 0.3 * math.sin(phase)
        r = screen_radius * (1.0 + pulse * 0.5)
        alpha = int(80 + 60 * (0.5 + 0.5 * math.sin(phase)))
        alpha = max(20, min(200, alpha))

        color = (*UI_WHITE, alpha)

        # Draw ring (using a temporary surface)
        ring_size = int(r * 2) + 10
        ring_surf = pygame.Surface((ring_size, ring_size), pygame.SRCALPHA)
        ring_surf.fill((0, 0, 0, 0))
        pygame.draw.circle(
            ring_surf, color,
            (ring_size // 2, ring_size // 2),
            r, max(1, int(2 + pulse * 2)),
        )
        surface.blit(ring_surf, (sx - ring_size // 2, sy - ring_size // 2))


# ============================================================================
# Coordinate Grid
# ============================================================================


def draw_grid(
    surface: pygame.Surface,
    camera: "ICamera",  # type: ignore
) -> None:
    """Draw a semi-transparent coordinate grid.

    Grid spacing adapts to the camera zoom level.
    Only grid lines within the current viewport are drawn.

    Args:
        surface: Target Pygame Surface
        camera: Camera object
    """
    color = (*GRID_COLOR, GRID_ALPHA)
    left, top, right, bottom = camera.get_screen_rect_world()

    zoom = camera.zoom
    if zoom < 0.001:
        spacing = 5e11
    elif zoom < 0.01:
        spacing = 5e10
    elif zoom < 0.1:
        spacing = 5e9
    elif zoom < 1.0:
        spacing = 5e8
    elif zoom < 10:
        spacing = 5e7
    else:
        spacing = 5e6

    start_x = math.floor(left / spacing) * spacing
    start_y = math.floor(top / spacing) * spacing

    x = start_x
    while x <= right:
        sx, _ = camera.world_to_screen(x, 0)
        _draw_alpha_line(surface, color, (sx, 0), (sx, camera.height), 0.5)
        x += spacing

    y = start_y
    while y <= bottom:
        _, sy = camera.world_to_screen(0, y)
        _draw_alpha_line(surface, color, (0, sy), (camera.width, sy), 0.5)
        y += spacing


# ============================================================================
# Body Labels
# ============================================================================


def draw_body_labels(
    surface: pygame.Surface,
    bodies: np.ndarray,
    camera: "ICamera",  # type: ignore
) -> None:
    """Draw body labels (name and number above each body).

    Labels are drawn for active bodies with a sufficiently large screen radius.
    Each label has a semi-transparent black background and type-specific text color.

    Args:
        surface: Target Pygame Surface
        bodies: Body state array of shape (N, NUM_FIELDS)
        camera: Camera object
    """
    type_names = {0: "Star", 1: "Planet", 2: "Probe", 3: "Charged"}
    font = get_ui_font(LABEL_FONT_SIZE)

    for i in range(bodies.shape[0]):
        if bodies[i, IS_ACTIVE] == 0.0:
            continue

        sx, sy = camera.world_to_screen(float(bodies[i, X]), float(bodies[i, Y]))
        radius = float(bodies[i, RADIUS])
        screen_radius = camera.world_distance_to_screen(radius)
        if screen_radius < LABEL_MIN_SCREEN_RADIUS:
            continue

        btype = int(bodies[i, BODY_TYPE])
        label = f"{type_names.get(btype, '?')} #{i}"
        text_surf = font.render(label, True, UI_WHITE)
        tr = text_surf.get_rect(midbottom=(sx, sy + LABEL_OFFSET_Y))

        bg = pygame.Surface((tr.width + 4, tr.height + 4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, LABEL_BG_ALPHA))
        surface.blit(bg, (tr.x - 2, tr.y - 2))
        pygame.draw.rect(surface, UI_WHITE, (tr.x - 2, tr.y - 2, tr.width + 4, tr.height + 4), 1)
        surface.blit(text_surf, tr)


# ============================================================================
# Shortcuts Overlay
# ============================================================================


def draw_shortcuts_overlay(surface: pygame.Surface) -> None:
    """Draw the keyboard shortcuts overlay panel.

    A semi-transparent black background covers the screen, with all shortcuts centered.
    Two-column layout: keys in yellow, descriptions in light purple.

    Args:
        surface: Target Pygame Surface
    """
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill(UI_OVERLAY_BG)
    surface.blit(overlay, (0, 0))

    panel = pygame.Rect(WINDOW_WIDTH // 2 - 260, 48, 520, 330)
    pygame.draw.rect(surface, UI_BLACK, panel)
    pygame.draw.rect(surface, UI_WHITE, panel, 2)

    title_font = get_ui_font(28)
    font = get_ui_font(18)

    title = title_font.render("Shortcuts (H/Esc to close)", True, (255, 255, 255))
    tr = title.get_rect(midtop=(WINDOW_WIDTH // 2, 60))
    surface.blit(title, tr)

    shortcuts = [
        ("Space", "Pause/Resume"), ("G", "Toggle Grid"),
        ("L", "Toggle Labels"), ("H", "Toggle Shortcuts"),
        ("5", "1x Speed"), ("6", "2x Speed"),
        ("7", "4x Speed"), ("8", "8x Speed"),
        ("1~4", "Spawn Tools"), ("Del", "Delete Body"),
        ("Right-Drag", "Aim Probe"), ("Right-Click", "Edit Body"),
        ("Scroll", "Zoom"), ("Dbl-Click", "Reference Frame"),
        ("Drag", "Grab Body"), ("Esc", "Back/Quit"),
    ]

    col1_x = WINDOW_WIDTH // 2 - 180
    col2_x = WINDOW_WIDTH // 2 + 20
    start_y = 110

    for i, (key, desc) in enumerate(shortcuts):
        col = i % 2
        row = i // 2
        x = col1_x if col == 0 else col2_x
        y = start_y + row * 30

        key_surf = font.render(key, True, UI_WHITE)
        surface.blit(key_surf, (x, y))
        desc_surf = font.render(desc, True, UI_DIM)
        surface.blit(desc_surf, (x + 70, y))
