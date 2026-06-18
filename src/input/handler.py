"""Input handler: Translates Pygame events into game operation commands.

Implements the ``IInputHandler`` interface (defined in ``src.core.interfaces``).
Separated from rendering logic, only responsible for event parsing and command generation.
"""

import math
from typing import List, Optional, Tuple

import pygame

from src.config import CAMERA_ZOOM_SPEED, CLICK_SELECTION_RADIUS
from src.core.interfaces import ICamera, IInputHandler
from src.core.types import IS_ACTIVE, WorldPoint


class InputHandler(IInputHandler):
    """Pygame input handler.

    Converts raw Pygame events into a list of semantic command strings.
    Maintains mouse state (press, drag, position) for other modules to query.

    Attributes:
        mouse_screen_x: Current mouse X position (pixels)
        mouse_screen_y: Current mouse Y position (pixels)
        mouse_world_x: Current mouse world X coordinate (m)
        mouse_world_y: Current mouse world Y coordinate (m)
        is_dragging: Whether currently dragging
        drag_start_x: Drag start screen X
        drag_start_y: Drag start screen Y
        is_panning: Whether currently panning the camera
    """

    def __init__(self) -> None:
        """Initialize the input handler."""
        # Mouse state
        self.mouse_screen_x: int = 0
        self.mouse_screen_y: int = 0
        self.mouse_world_x: float = 0.0
        self.mouse_world_y: float = 0.0

        # Drag state
        self.is_dragging: bool = False
        self.drag_start_x: int = 0
        self.drag_start_y: int = 0

        # Pan state
        self.is_panning: bool = False
        self.pan_last_x: int = 0
        self.pan_last_y: int = 0
        self.pan_camera_center_x: float = 0.0
        self.pan_camera_center_y: float = 0.0

        # Grab-drag state
        self.is_grabbing: bool = False
        self.grabbed_body_id: Optional[int] = None

        # Probe-launch drag state
        self.is_aiming: bool = False
        self.aim_start_x: int = 0
        self.aim_start_y: int = 0

        # Key state
        self._keys_down: set = set()
        self._keys_held: set = set()

        # Double-click detection
        self._last_click_time: float = 0.0
        self._last_click_pos: Tuple[int, int] = (0, 0)
        self._double_click_threshold: float = 0.3  # seconds

        # Double-click event flag
        self._double_click_happened: bool = False

    # ------------------------------------------------------------------
    # IInputHandler interface methods
    # ------------------------------------------------------------------

    def process_events(self) -> List[str]:
        """Process all pending Pygame events.

        Returns:
            List of operation command strings
        """
        commands: List[str] = []
        self._double_click_happened = False

        for event in pygame.event.get():
            cmd = self.handle_event(event)
            if cmd is not None:
                commands.append(cmd)

        # Held key detection
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            commands.append("PAN_LEFT")
        if keys[pygame.K_RIGHT]:
            commands.append("PAN_RIGHT")
        if keys[pygame.K_UP]:
            commands.append("PAN_UP")
        if keys[pygame.K_DOWN]:
            commands.append("PAN_DOWN")

        return commands

    def get_mouse_world_pos(self, camera: ICamera) -> WorldPoint:
        """Get the current world position of the mouse.

        Args:
            camera: Camera object

        Returns:
            (x, y) world coordinates
        """
        return camera.screen_to_world(self.mouse_screen_x, self.mouse_screen_y)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event,
                     bodies: Optional["np.ndarray"] = None,
                     camera: Optional[ICamera] = None) -> Optional[str]:
        """Handle a single Pygame event (public method, called by the main loop to dispatch events).

        Unlike ``process_events()``, this method only processes a single passed-in event and does not
        automatically pull events from the event queue. Used when the main loop needs to dispatch
        events to both the HUD and InputHandler.

        Args:
            event: Pygame event
            bodies: Optional body state array, used for left-click grab detection
            camera: Optional camera object, used for coordinate transformation in grab detection

        Returns:
            Command string, or None
        """
        # Window close
        if event.type == pygame.QUIT:
            return "QUIT"

        # Mouse motion
        if event.type == pygame.MOUSEMOTION:
            self.mouse_screen_x, self.mouse_screen_y = event.pos

            # Update mouse world coordinates (for HUD display)
            if camera is not None:
                self.mouse_world_x, self.mouse_world_y = camera.screen_to_world(
                    self.mouse_screen_x, self.mouse_screen_y
                )

            # Drag pan (middle button)
            if self.is_panning:
                dx = event.pos[0] - self.pan_last_x
                dy = event.pos[1] - self.pan_last_y
                self.pan_last_x, self.pan_last_y = event.pos
                return f"PAN:{dx},{dy}"

            # Grab-drag
            if self.is_grabbing and self.grabbed_body_id is not None:
                return f"GRAB_DRAG:{self.grabbed_body_id},{self.mouse_screen_x},{self.mouse_screen_y}"

            # Probe aim-drag
            if self.is_aiming:
                pass  # Drag vector read by external modules

            return None

        # Mouse wheel (SDL 2.28+ on Windows uses MOUSEWHEEL instead of MOUSEBUTTONDOWN button 4/5)
        if event.type == pygame.MOUSEWHEEL:
            x, y = self.mouse_screen_x, self.mouse_screen_y
            if event.y > 0:
                return f"ZOOM_IN:{x},{y}"
            elif event.y < 0:
                return f"ZOOM_OUT:{x},{y}"
            return None

        # Mouse down
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self._handle_mouse_down(event, bodies, camera)

        # Mouse up
        if event.type == pygame.MOUSEBUTTONUP:
            return self._handle_mouse_up(event)

        # Key down
        if event.type == pygame.KEYDOWN:
            return self._handle_key_down(event)

        # Key up
        if event.type == pygame.KEYUP:
            if event.key in self._keys_down:
                self._keys_down.remove(event.key)
            return None

        return None

    def _handle_mouse_down(self, event: pygame.event.Event,
                           bodies: Optional["np.ndarray"] = None,
                           camera: Optional[ICamera] = None) -> Optional[str]:
        """Handle mouse down event.

        Args:
            event: Pygame event
            bodies: Optional body state array, used for left-click grab detection
            camera: Optional camera object, used for coordinate transformation in grab detection

        Returns:
            Command string
        """
        x, y = event.pos
        self.mouse_screen_x, self.mouse_screen_y = x, y

        if event.button == 1:  # Left button — select
            # Double-click detection
            now = pygame.time.get_ticks() / 1000.0
            time_since_last = now - self._last_click_time
            dist_since_last = math.sqrt(
                (x - self._last_click_pos[0]) ** 2
                + (y - self._last_click_pos[1]) ** 2
            )

            if (
                time_since_last < self._double_click_threshold
                and dist_since_last < 10
            ):
                self._double_click_happened = True
                return f"DOUBLE_CLICK:{x},{y}"

            self._last_click_time = now
            self._last_click_pos = (x, y)

            # Check if clicked on a celestial body (grab-drag)
            if bodies is not None and camera is not None:
                found_id = self.find_body_at_screen_pos(x, y, bodies, camera)
                if found_id is not None:
                    self.is_grabbing = True
                    self.grabbed_body_id = found_id
                    return f"GRAB_START:{found_id},{x},{y}"

            # Start drag detection
            self.is_dragging = True
            self.drag_start_x = x
            self.drag_start_y = y

            return f"CLICK:{x},{y}"

        elif event.button == 2:  # Middle button - pan
            self.is_panning = True
            self.pan_last_x, self.pan_last_y = event.pos
            return None

        elif event.button == 3:  # Right button - launch probe or deselect
            return f"RIGHT_CLICK:{x},{y}"

        elif event.button == 4:  # Wheel up - zoom in
            return f"ZOOM_IN:{x},{y}"

        elif event.button == 5:  # Wheel down - zoom out
            return f"ZOOM_OUT:{x},{y}"

        return None

    def _handle_mouse_up(self, event: pygame.event.Event) -> Optional[str]:
        """Handle mouse up event.

        Args:
            event: Pygame event

        Returns:
            Command string
        """
        if event.button == 1:
            if self.is_grabbing:
                self.is_grabbing = False
                self.grabbed_body_id = None
                return "GRAB_END"

            if self.is_dragging:
                self.is_dragging = False
                # Detect box selection end (drag distance > 10px)
                sx, sy = event.pos
                dx = sx - self.drag_start_x
                dy = sy - self.drag_start_y
                if math.sqrt(dx * dx + dy * dy) > 10:
                    x1 = min(self.drag_start_x, sx)
                    y1 = min(self.drag_start_y, sy)
                    x2 = max(self.drag_start_x, sx)
                    y2 = max(self.drag_start_y, sy)
                    return f"BOX_SELECT_END:{x1},{y1},{x2},{y2}"
                return None

            self.is_dragging = False
            # If drag distance is large, treat as probe launch
            if self.is_aiming:
                self.is_aiming = False
                dx = event.pos[0] - self.aim_start_x
                dy = event.pos[1] - self.aim_start_y
                if math.sqrt(dx * dx + dy * dy) > 5:
                    return f"LAUNCH_PROBE:{self.aim_start_x},{self.aim_start_y},{dx},{dy}"
            return None

        elif event.button == 2:  # Release middle button
            self.is_panning = False
            return None

        elif event.button == 3:  # Release right button — probe aim-launch
            if self.is_aiming:
                self.is_aiming = False
                dx = event.pos[0] - self.aim_start_x
                dy = event.pos[1] - self.aim_start_y
                if math.sqrt(dx * dx + dy * dy) > 5:
                    return f"LAUNCH_PROBE:{self.aim_start_x},{self.aim_start_y},{dx},{dy}"
            return None

        return None

    def _handle_key_down(self, event: pygame.event.Event) -> Optional[str]:
        """Handle key down event.

        Args:
            event: Pygame event

        Returns:
            Command string
        """
        if event.key == pygame.K_SPACE:
            return "TOGGLE_PAUSE"
        elif event.key == pygame.K_ESCAPE:
            return "MENU"
        elif event.key == pygame.K_1:
            return "TOOL_STAR"
        elif event.key == pygame.K_2:
            return "TOOL_PLANET"
        elif event.key == pygame.K_3:
            return "TOOL_PROBE"
        elif event.key == pygame.K_4:
            return "TOOL_CUSTOM"
        elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
            return "DELETE_SELECTED"
        elif event.key == pygame.K_g:
            return "TOGGLE_GRID"
        elif event.key == pygame.K_l:
            return "TOGGLE_LABELS"
        elif event.key == pygame.K_h:
            return "TOGGLE_SHORTCUTS"

        return None

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def is_double_click(self) -> bool:
        """Check whether a double-click event occurred in the current frame.

        Returns:
            True if a double-click occurred
        """
        return self._double_click_happened

    def get_aim_vector(
        self,
    ) -> Tuple[float, float]:
        """Get the probe aim vector (from the start point to the current mouse position).

        Returns:
            (dx, dy) pixel offset, or (0, 0) if not aiming
        """
        if not self.is_aiming:
            return 0.0, 0.0

        dx = self.mouse_screen_x - self.aim_start_x
        dy = self.mouse_screen_y - self.aim_start_y
        return float(dx), float(dy)

    def reset_grab(self) -> None:
        """Cancel the grab state (called when main.py decides not to enter grab mode)."""
        self.is_grabbing = False
        self.grabbed_body_id = None

    def start_aiming(self) -> None:
        """Start aiming (called when the right button is pressed on a probe)."""
        self.is_aiming = True
        self.aim_start_x = self.mouse_screen_x
        self.aim_start_y = self.mouse_screen_y

    # ------------------------------------------------------------------
    # Camera control helpers
    # ------------------------------------------------------------------

    def handle_camera_commands(
        self, commands: List[str], camera: ICamera, dt: float
    ) -> None:
        """Handle camera-related commands.

        Args:
            commands: Command list
            camera: Camera object
            dt: Time delta (seconds)
        """
        from src.config import CAMERA_PAN_SPEED

        for cmd in commands:
            if cmd == "RESET_CAMERA":
                camera.reset()

            elif cmd.startswith("PAN:"):
                # cmd = "PAN:dx,dy" or "PAN:100,200"
                parts = cmd.split(":")
                if len(parts) >= 2:
                    coords = parts[1].split(",")
                    if len(coords) == 2:
                        dx = float(coords[0])
                        dy = float(coords[1])
                        camera.pan(-dx, -dy)

            elif cmd == "PAN_LEFT":
                camera.pan(-CAMERA_PAN_SPEED * dt, 0)
            elif cmd == "PAN_RIGHT":
                camera.pan(CAMERA_PAN_SPEED * dt, 0)
            elif cmd == "PAN_UP":
                camera.pan(0, -CAMERA_PAN_SPEED * dt)
            elif cmd == "PAN_DOWN":
                camera.pan(0, CAMERA_PAN_SPEED * dt)

            elif cmd.startswith("ZOOM_IN"):
                parts = cmd.split(":")
                if len(parts) >= 2:
                    coords = parts[1].split(",")
                    if len(coords) == 2:
                        sx, sy = int(coords[0]), int(coords[1])
                        camera.zoom_at(1.0 + CAMERA_ZOOM_SPEED, sx, sy)
                else:
                    camera.zoom_at(1.0 + CAMERA_ZOOM_SPEED, camera.width // 2, camera.height // 2)

            elif cmd.startswith("ZOOM_OUT"):
                parts = cmd.split(":")
                if len(parts) >= 2:
                    coords = parts[1].split(",")
                    if len(coords) == 2:
                        sx, sy = int(coords[0]), int(coords[1])
                        camera.zoom_at(1.0 - CAMERA_ZOOM_SPEED, sx, sy)
                else:
                    camera.zoom_at(1.0 - CAMERA_ZOOM_SPEED, camera.width // 2, camera.height // 2)

    # ------------------------------------------------------------------
    # Selection detection
    # ------------------------------------------------------------------

    def find_body_at_screen_pos(
        self,
        screen_x: int,
        screen_y: int,
        bodies: "np.ndarray",  # type: ignore
        camera: ICamera,
    ) -> Optional[int]:
        """Find the nearest celestial body at the given screen coordinates.

        Args:
            screen_x, screen_y: Screen coordinates
            bodies: Body state array
            camera: Camera object

        Returns:
            Body ID, or None
        """
        import numpy as np

        world_x, world_y = camera.screen_to_world(screen_x, screen_y)
        selection_radius_world = CLICK_SELECTION_RADIUS / camera.zoom * camera.world_scale

        best_id: Optional[int] = None
        best_dist: float = float("inf")

        for i in range(bodies.shape[0]):
            if bodies[i, IS_ACTIVE] == 0.0:
                continue
            dx = float(bodies[i, 0]) - world_x  # X
            dy = float(bodies[i, 1]) - world_y  # Y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < selection_radius_world and dist < best_dist:
                best_dist = dist
                best_id = i

        return best_id

    # ------------------------------------------------------------------
    # Test injection API (simulated input events)
    # ------------------------------------------------------------------

    def inject_mouse_click(self, x: int, y: int, button: int = 1) -> str:
        """Simulate a mouse click event and return the generated command string.

        Generates and processes MOUSEBUTTONDOWN + MOUSEBUTTONUP events.
        Left button (button=1) generates "CLICK:x,y", middle button (button=2) starts panning.

        Args:
            x: Screen x coordinate (pixels)
            y: Screen y coordinate (pixels)
            button: Mouse button (1=left, 2=middle, 3=right)

        Returns:
            Generated command string, or empty string if no command
        """
        down_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {'pos': (x, y), 'button': button}
        )
        cmd = self.handle_event(down_event)

        up_event = pygame.event.Event(
            pygame.MOUSEBUTTONUP, {'pos': (x, y), 'button': button}
        )
        self.handle_event(up_event)

        return cmd if cmd is not None else ""

    def inject_mouse_drag(
        self, x1: int, y1: int, x2: int, y2: int, button: int = 1
    ) -> List[str]:
        """Simulate a mouse drag operation (press -> move -> release) and return the command list.

        Used to simulate left-click drag selection, middle-button camera panning, etc.

        Args:
            x1, y1: Start screen coordinates (pixels)
            x2, y2: End screen coordinates (pixels)
            button: Mouse button (1=left, 2=middle, 3=right)

        Returns:
            List of generated command strings
        """
        cmds: List[str] = []

        # Mouse down
        down_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {'pos': (x1, y1), 'button': button}
        )
        cmd = self.handle_event(down_event)
        if cmd is not None:
            cmds.append(cmd)

        # Update mouse position
        self.mouse_screen_x, self.mouse_screen_y = x2, y2

        # If panning, generate a motion event
        if self.is_panning:
            move_event = pygame.event.Event(
                pygame.MOUSEMOTION, {'pos': (x2, y2)}
            )
            cmd = self.handle_event(move_event)
            if cmd is not None:
                cmds.append(cmd)

        # Mouse up
        up_event = pygame.event.Event(
            pygame.MOUSEBUTTONUP, {'pos': (x2, y2), 'button': button}
        )
        cmd = self.handle_event(up_event)
        if cmd is not None:
            cmds.append(cmd)

        return cmds

    def inject_key_press(self, key: str) -> str:
        """Simulate a keyboard key press event and return the generated command string.

        Simulates a key press using the pygame key constant name (e.g., 'K_SPACE', 'K_r').

        Args:
            key: String name of pygame.K_* constant, e.g., 'K_SPACE', 'K_r', 'K_ESCAPE'

        Returns:
            Generated command string, or empty string if no command
        """
        key_attr = getattr(pygame, key, None)
        if key_attr is None:
            return ""

        event = pygame.event.Event(pygame.KEYDOWN, {'key': key_attr})
        cmd = self.handle_event(event)
        return cmd if cmd is not None else ""

    def get_mouse_pos(self) -> Tuple[int, int]:
        """Return the current mouse screen position.

        Returns:
            (x, y) screen coordinates (pixels)
        """
        return (self.mouse_screen_x, self.mouse_screen_y)
