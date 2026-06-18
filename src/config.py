"""MiniSFS global configuration and constants.

This file holds all tunable game constants. Modules import them via
``from src.config import ...``. Constants are grouped by category
(physics, rendering, quadtree, game, input, UX) and sorted alphabetically
within each group.
"""

from pathlib import Path
from typing import Any

# ============================================================================
# Physics Constants
# ============================================================================

# Gravitational constant (N m^2 / kg^2)
GRAVITATIONAL_CONSTANT: float = 6.67430e-11

# Coulomb constant (N m^2 / C^2)
COULOMB_CONSTANT: float = 8.987551787e9

# Default physics time step (seconds)
TIME_STEP: float = 1.0 / 60.0

# Maximum physics time step — prevents tunneling at large dt (seconds)
TIME_STEP_MAX: float = 1.0 / 30.0

# Softening parameter (m) — prevents force divergence at close distances
SOFTENING: float = 1.0

# Physics sub-steps per frame — splits dt for better stability
SUBSTEPS: int = 4

# Minimum allowed mass (kg) — bodies below this are removed
MIN_MASS: float = 1.0

# ============================================================================
# Rendering Constants
# ============================================================================

# Window dimensions (pixels)
WINDOW_WIDTH: int = 1280
WINDOW_HEIGHT: int = 720

# Target frame rate (FPS)
TARGET_FPS: int = 60

# Background color (RGB)
BACKGROUND_COLOR: tuple[int, int, int] = (0, 0, 0)

# Monochrome UI palette (RGB / RGBA)
UI_BLACK: tuple[int, int, int] = (0, 0, 0)
UI_WHITE: tuple[int, int, int] = (255, 255, 255)
UI_DIM: tuple[int, int, int] = (150, 150, 150)
UI_DARK: tuple[int, int, int] = (16, 16, 16)
UI_DISABLED: tuple[int, int, int] = (70, 70, 70)
UI_PANEL_BG: tuple[int, int, int, int] = (0, 0, 0, 230)
UI_OVERLAY_BG: tuple[int, int, int, int] = (0, 0, 0, 180)

# Pixel font files. ``get_ui_font`` falls back to Pygame's default font if
# these files are missing or pygame cannot load them.
FONT_DIR: Path = Path(__file__).resolve().parent / "ttf"
UI_FONT_LATIN_PATH: str = str(FONT_DIR / "ark-pixel-10px-monospaced-latin.ttf")
UI_FONT_ZH_CN_PATH: str = str(FONT_DIR / "ark-pixel-10px-monospaced-zh_cn.ttf")

# World scale factor (m per pixel) — depends on simulation scale
WORLD_SCALE: float = 8.0e5  # 1 pixel = 800 km

# ============================================================================
# Quadtree Constants
# ============================================================================

# Barnes-Hut approximation threshold theta (s/d < theta → use COM approximation)
BARNES_HUT_THETA: float = 0.5

# Maximum points per quadtree node before subdivision
QUADTREE_CAPACITY: int = 4

# Force quadtree usage (otherwise fall back to O(n^2) when N < 50)
QUADTREE_FORCE_ENABLED: bool = False

# Collision broad-phase threshold — enable quadtree when active bodies >= this value
QUADTREE_COLLISION_THRESHOLD: int = 50

# ============================================================================
# Trail / Trajectory Constants
# ============================================================================

# Maximum trail points per body (frames)
MAX_TRAIL_LENGTH: int = 300

# Trail color gradient — slow to fast speed (RGB)
TRAIL_COLOR_SLOW: tuple[int, int, int] = (90, 90, 90)
TRAIL_COLOR_FAST: tuple[int, int, int] = (255, 255, 255)

# Trail alpha values (0-255)
TRAIL_ALPHA_NEW: int = 200
TRAIL_ALPHA_OLD: int = 30

# ============================================================================
# Body Type Constants
# ============================================================================

# Body type enum values (stored in the BODY_TYPE column of BodyState array)
BODY_TYPE_STAR: int = 0      # star — massive, luminous
BODY_TYPE_PLANET: int = 1    # planet — ordinary body
BODY_TYPE_PROBE: int = 2     # probe — player-controlled
BODY_TYPE_CHARGED: int = 3   # charged particle — affected by Coulomb force

# Default body radii/size (pixels). Probe uses equilateral triangle side length.
DEFAULT_RADIUS_STAR: float = 875.0     # 7e8 m = 7e5 km @ 800 km/px
DEFAULT_RADIUS_PLANET: float = 8.0
DEFAULT_RADIUS_PROBE: float = 5.1
DEFAULT_RADIUS_CHARGED: float = 6.0

# Default body masses (kg)
DEFAULT_MASS_STAR: float = 2.0e30
DEFAULT_MASS_PLANET: float = 6.0e26
DEFAULT_MASS_PROBE: float = 1.0
DEFAULT_MASS_CHARGED: float = 1.0e10

# Default body charges (C)
DEFAULT_CHARGE_CHARGED: float = 1.0e6

# ============================================================================
# Custom Particle Constants
# ============================================================================

# Default custom particle mass (kg)
CUSTOM_MASS_DEFAULT: float = 1.0e26
# Default custom particle charge (C)
CUSTOM_CHARGE_DEFAULT: float = 0.0
# Default custom particle speed (m/s)
CUSTOM_SPEED_DEFAULT: float = 1.0e4
# Default custom particle radius (m) — Earth radius 6400 km
CUSTOM_RADIUS_DEFAULT: float = 6.4e6
# Custom particle mass adjustment step (multiplier)
CUSTOM_MASS_STEP: float = 10.0
# Custom particle charge step (C)
CUSTOM_CHARGE_STEP: float = 1.0e5
# Custom particle speed adjustment step (multiplier)
CUSTOM_SPEED_STEP: float = 2.0
# Custom particle radius formula: radius = CUSTOM_RADIUS_FACTOR * sqrt(mass / 1e25) (pixels)
CUSTOM_RADIUS_FACTOR: float = 6.0
# Custom particle mass range
CUSTOM_MASS_MIN: float = 1.0e3
CUSTOM_MASS_MAX: float = 1.0e30

# Custom particle arrow maximum length (pixels)
CUSTOM_ARROW_MAX_LENGTH: float = 40.0

# Simple placement tool (Star/Planet/Probe) speed-per-pixel factor (m/s per pixel)
PLACEMENT_SPEED_PER_PX: float = 500.0

# Trajectory preview constants
DASH_GAP: float = 4.0       # Resampling gap (pixels)
DASH_ON: float = 6.0        # Dash length (pixels)
DASH_OFF: float = 6.0       # Gap length (pixels)
MAX_TRAJECTORY_STEPS: int = 2000  # Maximum integration steps
ESCAPE_RATIO: float = 50.0  # Escape threshold: distance > initial_dist * ESCAPE_RATIO

# ============================================================================
# Game Constants
# ============================================================================

# Game state enum values
GAME_STATE_MENU: str = "MENU"
GAME_STATE_PLAYING: str = "PLAYING"
GAME_STATE_PAUSED: str = "PAUSED"
GAME_STATE_WIN: str = "WIN"
GAME_STATE_LOSE: str = "LOSE"

# Level file extension
LEVEL_FILE_EXTENSION: str = ".json"

# Level directory path (relative to project root)
LEVEL_DIR: str = "assets/levels"

# Target zone detection radius (pixels)
TARGET_ZONE_RADIUS: float = 15.0

# Probe fuel cap (seconds)
PROBE_FUEL_MAX: float = 10.0

# Probe rocket defaults
PROBE_ROCKET_TOTAL_MASS_DEFAULT: float = 1.0e5
PROBE_ROCKET_FUEL_MASS_DEFAULT: float = 7.0e4
PROBE_ROCKET_EXHAUST_VELOCITY_DEFAULT: float = 3.0e3
PROBE_ROCKET_MASS_FLOW_RATE_DEFAULT: float = 50.0

# Score weights
SCORE_WEIGHT_TIME: float = 0.3
SCORE_WEIGHT_FUEL: float = 0.3
SCORE_WEIGHT_BODIES: float = 0.4

# ============================================================================
# Input Constants
# ============================================================================

# Camera pan speed (pixels/second)
CAMERA_PAN_SPEED: float = 500.0

# Camera zoom speed (per scroll step)
CAMERA_ZOOM_SPEED: float = 0.1

# Camera min/max zoom levels
CAMERA_ZOOM_MIN: float = 0.0005
CAMERA_ZOOM_MAX: float = 500.0

# Mouse click selection radius (pixels)
CLICK_SELECTION_RADIUS: float = 10.0

# ============================================================================
# UX Optimization Constants
# ============================================================================

# Grid overlay
GRID_COLOR: tuple[int, int, int] = (80, 80, 80)        # Grid line color
GRID_ALPHA: int = 120                                 # Grid transparency

# Scale bar
SCALE_BAR_X: int = 20                                 # Offset from right (pixels)
SCALE_BAR_Y: int = 75                                 # Offset from bottom (pixels), above controls
SCALE_BAR_HEIGHT: int = 4                             # Scale bar height (pixels)

# Smooth camera follow factor (0~1, smaller = smoother)
# Under reference frame, the camera approaches the target by this ratio each frame.
# High-speed targets need a larger value to reduce lag.
CAMERA_FOLLOW_LERP: float = 0.5

# Body labels
LABEL_FONT_SIZE: int = 12                             # Label font size
LABEL_OFFSET_Y: int = -12                             # Label offset above body (pixels)
LABEL_MIN_SCREEN_RADIUS: float = 3.0                  # Minimum screen radius to show label
LABEL_BG_ALPHA: int = 100                             # Label background transparency

# Default display states (toggled by hotkeys)
SHOW_FPS_DEFAULT: bool = True                         # Show FPS/info by default
SHOW_GRID_DEFAULT: bool = False                       # Grid hidden by default
SHOW_LABELS_DEFAULT: bool = False                     # Labels hidden by default


def get_ui_font(size: int, prefer_zh: bool = False) -> Any:
    """Load the project pixel font with a safe Pygame fallback.

    Args:
        size: Font size in pixels.
        prefer_zh: Whether to prefer the Chinese font file.

    Returns:
        A ``pygame.font.Font`` instance.
    """
    import pygame

    font_path = UI_FONT_ZH_CN_PATH if prefer_zh else UI_FONT_LATIN_PATH
    try:
        return pygame.font.Font(font_path, size)
    except (FileNotFoundError, pygame.error):
        return pygame.font.Font(None, size)
