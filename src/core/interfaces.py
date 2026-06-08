"""Abstract interface definitions for MiniSFS modules.

All core modules interact through the abstract base classes (ABCs) defined in this file.

Interface design principles:
    - **Physics engine does not depend on Pygame** — PhysicsEngine input and output are NumPy arrays only
    - **Renderer is read-only on physics state** — Renderer receives the bodies array but does not modify it
    - **Quadtree is a pure data structure** — Quadtree does not care about body types, it only performs spatial partitioning
    - **Testability** — All interfaces can be instantiated and tested without a GUI environment
"""

from abc import ABC, abstractmethod
from typing import Dict, List, NamedTuple, Optional, Tuple

import numpy as np

from src.core.types import WorldPoint


class Rect(NamedTuple):
    """A 2D axis-aligned rectangle.

    Attributes:
        x: X-coordinate of the top-left corner
        y: Y-coordinate of the top-left corner
        w: Width of the rectangle
        h: Height of the rectangle
    """
    x: float
    y: float
    w: float
    h: float


# ============================================================================
# Physics Engine Interface
# ============================================================================


class IPhysicsEngine(ABC):
    """Physics engine interface.

    Responsible for multi-body gravitational / Coulomb force computation,
    numerical integration, collision detection and response.
    """

    @abstractmethod
    def update(self, bodies: np.ndarray, dt: float) -> np.ndarray:
        """Update all body states by one time step.

        Internal workflow:
            1. Compute forces between all bodies
            2. Update velocities and positions using numerical integrator
            3. Detect and handle collisions
            4. Remove bodies with IS_ACTIVE == 0

        Args:
            bodies: Body state array of shape (N, NUM_FIELDS)
            dt: Time step (seconds)

        Returns:
            Updated body state array (bodies may be removed or merged,
            row count may change)
        """

    @abstractmethod
    def compute_forces(self, bodies: np.ndarray) -> np.ndarray:
        """Compute the net force on all bodies.

        Returns a force array of shape (N, 2), each row corresponds to (fx, fy).

        Args:
            bodies: Body state array of shape (N, NUM_FIELDS)

        Returns:
            Net force array of shape (N, 2) (N)
        """

    @abstractmethod
    def predict_trajectory(
        self,
        probe: np.ndarray,
        bodies: np.ndarray,
        steps: int,
        dt: float,
    ) -> np.ndarray:
        """Predict the future trajectory of a probe.

        Uses RK4 for simulation without modifying real state.
        Stops predicting when the probe collides with a body or goes out of bounds.

        Args:
            probe: Probe state of shape (1, NUM_FIELDS)
            bodies: Static body state array of shape (N, NUM_FIELDS)
            steps: Number of prediction steps
            dt: Time interval per step (seconds)

        Returns:
            Predicted trajectory coordinate array of shape (M, 2)
            (M <= steps, may terminate early due to collision)
        """

    @abstractmethod
    def handle_collisions(self, bodies: np.ndarray) -> np.ndarray:
        """Detect and handle collisions.

        Supports elastic collisions (mass-weighted velocity exchange)
        and merger collisions (smaller bodies are absorbed).

        Args:
            bodies: Body state array of shape (N, NUM_FIELDS)

        Returns:
            Body state array after collision handling
        """


# ============================================================================
# Quadtree Interface
# ============================================================================


class IQuadtree(ABC):
    """Quadtree interface.

    Used for spatial partitioning to accelerate gravity computation
    and collision detection.
    """

    @abstractmethod
    def insert(self, body_id: int, x: float, y: float) -> bool:
        """Insert a body ID into the quadtree.

        Args:
            body_id: Row index of the body in the bodies array
            x: X-coordinate of the body
            y: Y-coordinate of the body

        Returns:
            True if insertion is successful, False if out of bounds
        """

    @abstractmethod
    def rebuild(self, bodies: np.ndarray) -> None:
        """Clear and rebuild the quadtree.

        Args:
            bodies: Body state array of shape (N, NUM_FIELDS)
        """

    @abstractmethod
    def query_range(
        self, x: float, y: float, radius: float
    ) -> List[int]:
        """Range query: return the list of body IDs within a specified circular area.

        Args:
            x: X-coordinate of the circle center
            y: Y-coordinate of the circle center
            radius: Radius of the circle

        Returns:
            List of body IDs within the area
        """

    @abstractmethod
    def query_nearest(
        self, x: float, y: float
    ) -> Optional[int]:
        """Nearest neighbor query: return the ID of the body closest
        to the specified coordinates.

        Args:
            x: X-coordinate of the query point
            y: Y-coordinate of the query point

        Returns:
            ID of the nearest body, or None if no bodies exist
        """

    @abstractmethod
    def barnes_hut_force(
        self, body_id: int, bodies: np.ndarray, theta: float
    ) -> Tuple[float, float]:
        """Compute the total gravitational force on a specified body
        using the Barnes-Hut approximation.

        For distant nodes, the node's center of mass is used instead of
        computing each body in the subtree individually.
        Decision condition: s / d < theta (s = node side length,
        d = distance to center of mass)

        Args:
            body_id: ID of the target body
            bodies: State array of all bodies
            theta: Barnes-Hut threshold (typically 0.5)

        Returns:
            (fx, fy) force vector (N)
        """


# ============================================================================
# Trail Buffer Interface
# ============================================================================


class ITrailBuffer(ABC):
    """Trail buffer interface.

    Uses collections.deque to maintain a fixed-length history of
    positions for each body.
    """

    @abstractmethod
    def push_frame(self, body_id: int, x: float, y: float) -> None:
        """Append a frame of coordinates to the trail of the specified body.

        Args:
            body_id: Body ID
            x: Current frame x-coordinate
            y: Current frame y-coordinate
        """

    @abstractmethod
    def push_all(self, bodies: np.ndarray) -> None:
        """Append trail frames for the current positions of all active bodies.

        Args:
            bodies: Body state array of shape (N, NUM_FIELDS)
        """

    @abstractmethod
    def get_trail(self, body_id: int) -> List[Tuple[float, float]]:
        """Get the trail coordinate list for the specified body
        (oldest to newest).

        Args:
            body_id: Body ID

        Returns:
            Coordinate list [(x1,y1), (x2,y2), ...],
            empty list indicates no trail
        """

    @abstractmethod
    def rewind(self, body_id: int, frames: int) -> Optional[Tuple[float, float]]:
        """Return the coordinates of the specified body from `frames` frames ago.

        Args:
            body_id: Body ID
            frames: Number of frames to rewind

        Returns:
            (x, y) coordinates, or None if insufficient history
        """

    @abstractmethod
    def clear(self, body_id: int) -> None:
        """Clear the trail of the specified body.

        Args:
            body_id: Body ID
        """

    @abstractmethod
    def clear_all(self) -> None:
        """Clear the trails of all bodies."""


# ============================================================================
# Renderer Interface
# ============================================================================


class IRenderer(ABC):
    """Renderer interface.

    Receives physics state arrays and draws to the Pygame window.
    The renderer does **not modify** the physics state.
    """

    @abstractmethod
    def render(
        self,
        bodies: np.ndarray,
        trails: Dict[int, List[Tuple[float, float]]],
        camera: "ICamera",
    ) -> None:
        """Render a single frame.

        Args:
            bodies: Body state array of shape (N, NUM_FIELDS)
            trails: Trail data {body_id: [(x1,y1), (x2,y2), ...]}
            camera: Camera object, used for world-to-screen
                    coordinate transformation
        """

    @abstractmethod
    def render_background(self) -> None:
        """Render the static background (nebula, grid, etc.)."""

    @abstractmethod
    def render_hud(self, game_state: str, score: Optional[Dict[str, float]]) -> None:
        """Render HUD information.

        Args:
            game_state: Current game state
            score: Score data (optional)
        """

    @abstractmethod
    def render_predicted_trajectory(
        self, trajectory: np.ndarray, camera: "ICamera"
    ) -> None:
        """Render the predicted trajectory (dashed / semi-transparent).

        Args:
            trajectory: Predicted trajectory coordinates of shape (M, 2)
            camera: Camera object
        """

    @abstractmethod
    def render_target_zone(
        self, x: float, y: float, radius: float, camera: "ICamera"
    ) -> None:
        """Render the target zone (pulsing animation).

        Args:
            x, y: World coordinates of the target center
            radius: Target zone radius (meters)
            camera: Camera object
        """


# ============================================================================
# Camera Interface
# ============================================================================


class ICamera(ABC):
    """Camera interface.

    Manages viewport transformation: world coordinates <-> screen coordinates.
    """

    @abstractmethod
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

    @abstractmethod
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

    @abstractmethod
    def pan(self, dx: float, dy: float) -> None:
        """Pan the camera.

        Args:
            dx: Offset in the x-direction (pixels)
            dy: Offset in the y-direction (pixels)
        """

    @abstractmethod
    def zoom_at(self, factor: float, screen_center_x: int, screen_center_y: int) -> None:
        """Zoom centered on a specific screen point.

        Args:
            factor: Zoom factor (>1 zoom in, <1 zoom out)
            screen_center_x: Zoom center x (pixels)
            screen_center_y: Zoom center y (pixels)
        """

    @abstractmethod
    def follow(self, world_x: float, world_y: float) -> None:
        """Make the camera follow the specified world coordinates (centered).

        Args:
            world_x: Target x-coordinate (m)
            world_y: Target y-coordinate (m)
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset the camera to its initial position and zoom."""


# ============================================================================
# Game Logic Interface
# ============================================================================


class IGameManager(ABC):
    """Game manager interface.

    Manages the game state machine
    (MENU -> PLAYING -> PAUSED / WIN / LOSE),
    level loading, condition evaluation, and scoring.
    """

    @abstractmethod
    def load_level(self, level_id: str) -> np.ndarray:
        """Load a level and return the initial body state array for that level.

        Args:
            level_id: Level identifier (e.g. "1-1", "1-2")

        Returns:
            Initial body state array of shape (N, NUM_FIELDS)

        Raises:
            FileNotFoundError: If the level file does not exist
        """

    @abstractmethod
    def check_win_condition(
        self, probe_pos: Tuple[float, float]
    ) -> bool:
        """Check whether the probe has reached the target zone.

        Args:
            probe_pos: Current world coordinates of the probe (x, y)

        Returns:
            True if the probe has reached the target
        """

    @abstractmethod
    def check_lose_condition(
        self, probe: np.ndarray, bodies: np.ndarray, bounds: Rect
    ) -> bool:
        """Check whether the lose condition is met.

        Args:
            probe: Probe state array
            bodies: All body state arrays
            bounds: World boundaries (flying out means losing)

        Returns:
            True if the condition is met (lose)
        """

    @abstractmethod
    def get_score(self) -> Dict[str, float]:
        """Get the current score.

        Returns:
            {'stars': 3, 'time': 45.2, 'fuel': 0.7, 'total': 0.85}
            stars is an integer from 1-3, the rest are floats
        """

    @abstractmethod
    def set_state(self, new_state: str) -> None:
        """Set the game state.

        Args:
            new_state: New state (MENU / PLAYING / PAUSED / WIN / LOSE)
        """

    @abstractmethod
    def get_state(self) -> str:
        """Get the current game state."""


# ============================================================================
# Input Handler Interface
# ============================================================================


class IInputHandler(ABC):
    """Input handler interface.

    Converts Pygame events into game actions, decoupled from rendering logic.
    """

    @abstractmethod
    def process_events(self) -> List[str]:
        """Process all pending Pygame events.

        Returns:
            List of action command strings,
            e.g. ['SELECT:3', 'PAN_LEFT', 'ZOOM_IN', 'PAUSE']
        """

    @abstractmethod
    def get_mouse_world_pos(self, camera: ICamera) -> WorldPoint:
        """Get the current world coordinates of the mouse.

        Args:
            camera: Camera object

        Returns:
            (x, y) world coordinates
        """
