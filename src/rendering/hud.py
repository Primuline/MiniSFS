"""HUD and UI system: info panel, time controls, toolbar, selection info.

All UI elements are drawn on top of the renderer using Pygame's Surface and Font.
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pygame

from src.config import (
    BODY_TYPE_CHARGED,
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_STAR,
    CUSTOM_CHARGE_DEFAULT,
    CUSTOM_MASS_DEFAULT,
    CUSTOM_RADIUS_DEFAULT,
    DEFAULT_CHARGE_CHARGED,
    DEFAULT_MASS_CHARGED,
    DEFAULT_MASS_PLANET,
    DEFAULT_MASS_PROBE,
    DEFAULT_MASS_STAR,
    DEFAULT_RADIUS_CHARGED,
    DEFAULT_RADIUS_PLANET,
    DEFAULT_RADIUS_PROBE,
    DEFAULT_RADIUS_STAR,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    WORLD_SCALE,
)
from src.core.utils.tools import round_to_nice_number
from src.rendering.input_dialog import EditBodyDialog, ScientificInputDialog
from src.core.types import (
    BODY_TYPE,
    CHARGE,
    IS_ACTIVE,
    MASS,
    RADIUS,
    VX,
    VY,
    X,
    Y,
)

# ============================================================================
# Panel configuration
# ============================================================================

PANEL_BG = (20, 20, 40, 200)
PANEL_BORDER = (60, 60, 100)
TEXT_COLOR = (200, 200, 220)
TEXT_HIGHLIGHT = (255, 255, 255)
LABEL_COLOR = (150, 150, 180)
BTN_NORMAL = (50, 50, 80)
BTN_HOVER = (70, 70, 110)
BTN_ACTIVE = (100, 120, 200)
BTN_DISABLED = (30, 30, 50)

INFO_PANEL_WIDTH = 220
TOOLBAR_WIDTH = 44
CONTROL_BAR_HEIGHT = 36


class Button:
    """A simple UI button."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        action: str = "",
        color: Tuple[int, int, int] = BTN_NORMAL,
        hover_color: Tuple[int, int, int] = BTN_HOVER,
        font_size: int = 16,
    ) -> None:
        """Initialize the button.

        Args:
            x, y: Top-left corner coordinates
            width, height: Dimensions
            text: Button label
            action: Action identifier triggered by the button
            color: Normal color
            hover_color: Hover color
            font_size: Font size
        """
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.action = action
        self.color = color
        self.hover_color = hover_color
        self.font = pygame.font.Font(None, font_size)
        self.hovered = False
        self.active = False
        self.disabled = False
        self.visible = True

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the button.

        Args:
            surface: Target Surface
        """
        if not self.visible:
            return

        color = self.color
        if self.disabled:
            color = BTN_DISABLED
        elif self.active:
            color = BTN_ACTIVE
        elif self.hovered:
            color = self.hover_color

        # Background
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 1, border_radius=4)

        # Text
        text_color = TEXT_HIGHLIGHT if (self.active or self.hovered) else TEXT_COLOR
        if self.disabled:
            text_color = (80, 80, 80)
        text_surf = self.font.render(self.text, True, text_color)
        tr = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, tr)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Handle events and return click action.

        Args:
            event: Pygame event

        Returns:
            Action string on click, None otherwise
        """
        if not self.visible or self.disabled:
            return None

        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return self.action

        return None

    def set_pos(self, x: int, y: int) -> None:
        """Set button position.

        Args:
            x, y: New top-left corner coordinates
        """
        self.rect.x = x
        self.rect.y = y


class HUDManager:
    """HUD manager that controls all UI elements.

    Manages the state and rendering of UI components such as the info panel,
    time controls, and toolbar.
    """

    def __init__(self) -> None:
        """Initialize the HUD manager."""
        self.width: int = WINDOW_WIDTH
        self.height: int = WINDOW_HEIGHT

        # Fonts
        self._font_title = pygame.font.Font(None, 20)
        self._font_label = pygame.font.Font(None, 16)
        self._font_value = pygame.font.Font(None, 16)
        self._font_small = pygame.font.Font(None, 14)

        # ============ Toolbar ============
        tool_y = 100
        tool_spacing = 46
        self.tool_buttons: List[Button] = []
        tools = [
            ("S", "TOOL_STAR", "Star"),
            ("P", "TOOL_PLANET", "Planet"),
            ("D", "TOOL_PROBE", "Probe"),
            ("C", "TOOL_CUSTOM", "Custom"),
        ]
        for i, (label, action, _) in enumerate(tools):
            btn = Button(
                5, tool_y + i * tool_spacing,
                34, 34, label, action,
                font_size=14,
            )
            self.tool_buttons.append(btn)

        self.active_tool: Optional[str] = None

        # ============ Time controls ============
        ctrl_y = self.height - CONTROL_BAR_HEIGHT - 5
        ctrl_x = self.width // 2 - 96  # center 5 buttons
        self.time_buttons: List[Button] = []
        time_actions = [
            ("|<", "REWIND"),
            (">", "PLAY_PAUSE"),
            (">>", "FAST_2X"),
            (">>>", "FAST_4X"),
            (">>>>", "FAST_8X"),
        ]
        for i, (label, action) in enumerate(time_actions):
            btn = Button(
                ctrl_x + i * 40, ctrl_y,
                36, CONTROL_BAR_HEIGHT - 4,
                label, action,
                font_size=13,
            )
            self.time_buttons.append(btn)

        # Time speed label
        self.time_speed: float = 1.0
        self.is_paused: bool = False

        # ============ Custom particle parameters ============
        self.custom_mass: float = CUSTOM_MASS_DEFAULT
        self.custom_charge: float = CUSTOM_CHARGE_DEFAULT

        # Scientific notation input dialog
        self.custom_dialog_visible: bool = False
        self._input_dialog: ScientificInputDialog = ScientificInputDialog()

        # Edit body parameter dialog
        self.edit_mass: float = 0.0
        self.edit_charge: float = 0.0
        self.edit_radius: float = 6.0
        self._edit_dialog: EditBodyDialog = EditBodyDialog()

        # Custom particle radius (read from dialog, in meters)
        self.custom_radius: float = CUSTOM_RADIUS_DEFAULT

        # ============ Info panel ============
        self.info_panel_visible: bool = False
        self._info_body_data: Optional[Dict[str, float]] = None
        self._info_body_type: int = -1

        # Selected body info bar
        self.selected_body_info: Optional[str] = None

        # Reference frame state
        self._reference_body_id: Optional[int] = None
        self._reference_body_type: int = -1

        # Status info (updated each frame by main.py)
        self._num_bodies: int = 0
        self._time_speed: float = 1.0
        self._fps: float = 0.0
        self._mouse_world_pos: tuple[float, float] = (0.0, 0.0)
        self._has_mouse_pos: bool = False

    # ------------------------------------------------------------------
    # Update methods
    # ------------------------------------------------------------------

    def set_selected_body(
        self, body_data: Optional[np.ndarray], body_id: int
    ) -> None:
        """Update the selected body's information.

        Args:
            body_data: Body state row (shape (NUM_FIELDS,))
            body_id: Body ID
        """
        if body_data is None:
            self.info_panel_visible = False
            self._info_body_data = None
            self.selected_body_info = None
            return

        self.info_panel_visible = True
        self._info_body_data = {
            "id": float(body_id),
            "x": float(body_data[X]),
            "y": float(body_data[Y]),
            "vx": float(body_data[VX]),
            "vy": float(body_data[VY]),
            "mass": float(body_data[MASS]),
            "radius": float(body_data[RADIUS]),
            "body_type": float(body_data[BODY_TYPE]),
            "charge": float(body_data[CHARGE]),
            "static": float(body_data[8]),  # IS_STATIC
        }
        self._info_body_type = int(body_data[BODY_TYPE])

        # Generate brief description
        type_names = {0: "Star", 1: "Planet", 2: "Probe", 3: "Charged"}
        type_name = type_names.get(self._info_body_type, "Unknown")
        speed = math.sqrt(
            float(body_data[VX]) ** 2 + float(body_data[VY]) ** 2
        )
        self.selected_body_info = (
            f"{type_name} #{body_id}  "
            f"Speed: {speed:.2e} m/s"
        )

    @property
    def reference_body_id(self) -> Optional[int]:
        """Get the current reference frame body ID."""
        return self._reference_body_id

    def set_reference_frame(self, body_id: int, body_type: int) -> None:
        """Set the reference frame body.

        Args:
            body_id: Body ID
            body_type: Body type
        """
        self._reference_body_id = body_id
        self._reference_body_type = body_type

    def clear_reference_frame(self) -> None:
        """Clear the reference frame."""
        self._reference_body_id = None
        self._reference_body_type = -1

    def set_status_info(self, num_bodies: int, time_speed: float, fps: float,
                        mouse_world_pos: tuple[float, float] | None = None) -> None:
        """Update status info (called each frame by main.py).

        Args:
            num_bodies: Current number of bodies
            time_speed: Time speed multiplier
            fps: Current frame rate
            mouse_world_pos: Mouse world position (None if no valid position)
        """
        self._num_bodies = num_bodies
        self._time_speed = time_speed
        self._fps = fps
        if mouse_world_pos is not None:
            self._mouse_world_pos = mouse_world_pos
            self._has_mouse_pos = True
        else:
            self._has_mouse_pos = False

    def get_tool_display_name(self, tool: str) -> str:
        """Get the display name for the body type corresponding to a tool.

        Args:
            tool: Tool identifier

        Returns:
            Display name
        """
        names = {
            "TOOL_STAR": "Star",
            "TOOL_PLANET": "Planet",
            "TOOL_PROBE": "Probe",
            "TOOL_CHARGED": "Charged",
            "TOOL_CUSTOM": "Custom",
        }
        return names.get(tool, tool)

    def get_tool_body_type(self, tool: str) -> int:
        """Get the body type value corresponding to a tool.

        Args:
            tool: Tool identifier

        Returns:
            BODY_TYPE_* constant
        """
        mapping = {
            "TOOL_STAR": BODY_TYPE_STAR,
            "TOOL_PLANET": BODY_TYPE_PLANET,
            "TOOL_PROBE": BODY_TYPE_PROBE,
            "TOOL_CHARGED": BODY_TYPE_CHARGED,
        }
        return mapping.get(tool, BODY_TYPE_PLANET)

    def get_default_body_params(self, tool: str) -> Tuple[float, float, float, float]:
        """Get the default body parameters for a tool.

        Args:
            tool: Tool identifier

        Returns:
            (mass, radius, charge, body_type) tuple
        """
        if tool == "TOOL_CUSTOM":
            # custom_radius is stored in meters, convert back to pixels (caller multiplies by WORLD_SCALE)
            pixel_radius = max(2.0, min(self.custom_radius / WORLD_SCALE, 30.0))
            return (self.custom_mass, pixel_radius, self.custom_charge, float(BODY_TYPE_PLANET))

        mapping = {
            "TOOL_STAR": (DEFAULT_MASS_STAR, DEFAULT_RADIUS_STAR, 0.0, float(BODY_TYPE_STAR)),
            "TOOL_PLANET": (DEFAULT_MASS_PLANET, DEFAULT_RADIUS_PLANET, 0.0, float(BODY_TYPE_PLANET)),
            "TOOL_PROBE": (DEFAULT_MASS_PROBE, DEFAULT_RADIUS_PROBE, 0.0, float(BODY_TYPE_PROBE)),
            "TOOL_CHARGED": (DEFAULT_MASS_CHARGED, DEFAULT_RADIUS_CHARGED, DEFAULT_CHARGE_CHARGED, float(BODY_TYPE_CHARGED)),
        }
        return mapping.get(tool, (DEFAULT_MASS_PLANET, DEFAULT_RADIUS_PLANET, 0.0, float(BODY_TYPE_PLANET)))

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Handle HUD events.

        Args:
            event: Pygame event

        Returns:
            Action string (e.g. "TOOL_STAR", "PLAY_PAUSE")
        """
        # Edit dialog has priority (when visible)
        if self._edit_dialog.visible:
            dlg_result = self._edit_dialog.handle_event(event)
            if dlg_result is not None:
                if isinstance(dlg_result, dict):
                    # OK: read results and store edit values
                    self.edit_mass = dlg_result["mass"]
                    self.edit_charge = dlg_result["charge"]
                    self.edit_radius = dlg_result["radius"]
                    return "EDIT_DIALOG_OK"
                elif dlg_result == "CANCEL":
                    return "EDIT_DIALOG_CANCEL"
            # Dialog consumed the event, do not propagate
            return None

        # Custom particle dialog has priority (when visible)
        if self.custom_dialog_visible:
            dlg_result = self._input_dialog.handle_event(event)
            if dlg_result is not None:
                if isinstance(dlg_result, dict):
                    # OK: read results and update custom parameters
                    self.custom_mass = dlg_result["mass"]
                    self.custom_charge = dlg_result["charge"]
                    self.custom_radius = dlg_result["radius"]
                    return "CUSTOM_DIALOG_OK"
                elif dlg_result == "CANCEL":
                    return "CUSTOM_DIALOG_CANCEL"
            # Dialog consumed the event, do not propagate
            return None

        # Toolbar events
        for btn in self.tool_buttons:
            action = btn.handle_event(event)
            if action:
                return action

        # Time control events
        for btn in self.time_buttons:
            action = btn.handle_event(event)
            if action:
                return action

        return None

    def set_tool_active(self, tool: Optional[str]) -> None:
        """Set the currently active tool.

        Args:
            tool: Tool identifier
        """
        self.active_tool = tool
        for btn in self.tool_buttons:
            btn.active = (btn.action == tool)

    def set_play_pause_state(self, is_paused: bool) -> None:
        """Set the play/pause state.

        Args:
            is_paused: Whether paused
        """
        self.is_paused = is_paused
        if len(self.time_buttons) >= 2:
            self.time_buttons[1].text = ">" if is_paused else "||"

    def set_time_speed(self, speed: float) -> None:
        """Set the time speed.

        Args:
            speed: Time speed multiplier
        """
        self.time_speed = speed
        for i, btn in enumerate(self.time_buttons):
            if i >= 2:  # fast-forward buttons
                btn.active = False
        if speed >= 8.0:
            self.time_buttons[4].active = True
        elif speed >= 4.0:
            self.time_buttons[3].active = True
        elif speed >= 2.0:
            self.time_buttons[2].active = True

    # ------------------------------------------------------------------
    # Edit dialog control
    # ------------------------------------------------------------------

    def show_custom_dialog(self) -> None:
        """Open the custom particle input dialog and prefill radius default value."""
        self._input_dialog.prefill(self.custom_mass)
        self.custom_dialog_visible = True
        self._input_dialog.visible = True

    def hide_custom_dialog(self) -> None:
        """Close the custom particle input dialog and reset input state."""
        self.custom_dialog_visible = False
        self._input_dialog.visible = False
        self._input_dialog.active_field_index = -1
        for field in self._input_dialog.fields:
            field["text"] = ""

    def show_edit_dialog(self, mass: float, charge: float, radius_meters: float = 6.0) -> None:
        """Open the edit body parameter dialog and prefill current values.

        Args:
            mass: Current mass (kg)
            charge: Current charge (C)
            radius_meters: Current radius (m), internally converted to km for display
        """
        self._edit_dialog.prefill(mass, charge, radius_meters)
        self._edit_dialog.visible = True

    def hide_edit_dialog(self) -> None:
        """Close the edit body parameter dialog and reset input state."""
        self._edit_dialog.visible = False
        self._edit_dialog.active_field_index = -1
        for field in self._edit_dialog.fields:
            field["text"] = ""

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, camera=None) -> None:
        """Draw all HUD elements.

        Args:
            surface: Target Surface
            camera: Optional Camera object for drawing the scale bar
        """
        self._draw_info_panel(surface)
        self._draw_toolbar(surface)
        if self._edit_dialog.visible:
            self._edit_dialog.draw(surface)
        if self.custom_dialog_visible:
            self._draw_custom_dialog(surface)
        self._draw_time_controls(surface)
        self._draw_active_tool_indicator(surface)
        self._draw_selected_info_bar(surface)
        self._draw_status_info(surface)
        if camera is not None:
            self._draw_scale_bar(surface, camera)

    def _draw_info_panel(self, surface: pygame.Surface) -> None:
        """Draw the info panel.

        Args:
            surface: Target Surface
        """
        if not self.info_panel_visible or self._info_body_data is None:
            return

        panel_x = self.width - INFO_PANEL_WIDTH - 10
        panel_y = 10
        panel_w = INFO_PANEL_WIDTH
        panel_h = 200

        # Background
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill(PANEL_BG)
        surface.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(
            surface, PANEL_BORDER,
            (panel_x, panel_y, panel_w, panel_h), 1, border_radius=4,
        )

        # Title
        type_names = {0: "Star", 1: "Planet", 2: "Probe", 3: "Charged"}
        type_name = type_names.get(self._info_body_type, "Unknown")
        title = f"{type_name} #{int(self._info_body_data['id'])}"
        title_surf = self._font_title.render(title, True, TEXT_HIGHLIGHT)
        surface.blit(title_surf, (panel_x + 10, panel_y + 8))

        # Info rows
        data = self._info_body_data
        lines = [
            ("Pos", f"({data['x']:.2e}, {data['y']:.2e})"),
            ("Vx", f"{data['vx']:.2e} m/s"),
            ("Vy", f"{data['vy']:.2e} m/s"),
            ("Mass", f"{data['mass']:.3e} kg"),
            ("Radius", f"{data['radius']:.2e} m"),
        ]
        if self._info_body_type == BODY_TYPE_CHARGED:
            lines.append(("Charge", f"{data['charge']:.2e} C"))

        if data.get('static', 0) == 1.0:
            lines.append(("Fixed", "Static"))

        for i, (label, value) in enumerate(lines):
            y = panel_y + 32 + i * 20
            label_surf = self._font_label.render(label + ":", True, LABEL_COLOR)
            surface.blit(label_surf, (panel_x + 10, y))
            value_surf = self._font_value.render(value, True, TEXT_COLOR)
            surface.blit(value_surf, (panel_x + 80, y))

    def _draw_toolbar(self, surface: pygame.Surface) -> None:
        """Draw the toolbar.

        Args:
            surface: Target Surface
        """
        # Toolbar background
        tool_bg = pygame.Surface((TOOLBAR_WIDTH, self.height), pygame.SRCALPHA)
        tool_bg.fill((15, 15, 35, 180))
        surface.blit(tool_bg, (0, 0))

        # Tool title
        title_surf = self._font_title.render("Tools", True, LABEL_COLOR)
        surface.blit(title_surf, (6, 70))

        # Tool buttons
        for btn in self.tool_buttons:
            btn.draw(surface)

        # Current tool hint
        if self.active_tool:
            hint = self.get_tool_display_name(self.active_tool)
            hint_surf = self._font_small.render(hint, True, TEXT_HIGHLIGHT)
            surface.blit(hint_surf, (5, 55))

    def _draw_custom_dialog(self, surface: pygame.Surface) -> None:
        """Draw the centered scientific notation input dialog.

        Args:
            surface: Target Surface
        """
        self._input_dialog.draw(surface)

    def _draw_time_controls(self, surface: pygame.Surface) -> None:
        """Draw the time control buttons.

        Args:
            surface: Target Surface
        """
        bar_y = self.height - CONTROL_BAR_HEIGHT - 5
        bar_w = 240
        bar_x = self.width // 2 - bar_w // 2

        # Background
        bar_bg = pygame.Surface((bar_w, CONTROL_BAR_HEIGHT), pygame.SRCALPHA)
        bar_bg.fill((15, 15, 35, 200))
        surface.blit(bar_bg, (bar_x, bar_y))
        pygame.draw.rect(
            surface, PANEL_BORDER,
            (bar_x, bar_y, bar_w, CONTROL_BAR_HEIGHT), 1, border_radius=4,
        )

        # Buttons
        for btn in self.time_buttons:
            btn.draw(surface)

        # Speed indicator
        speed_text = f"{self.time_speed:.0f}x"
        if self.is_paused:
            speed_text = "PAUSED"
        speed_surf = self._font_small.render(speed_text, True, TEXT_COLOR)
        sr = speed_surf.get_rect(
            midtop=(self.width // 2, bar_y - 16)
        )
        surface.blit(speed_surf, sr)

    def _draw_active_tool_indicator(self, surface: pygame.Surface) -> None:
        """Draw the active tool indicator hint.

        Args:
            surface: Target Surface
        """
        if self.active_tool:
            tool_name = self.get_tool_display_name(self.active_tool)
            text = f"Active: {tool_name}  (right-click to cancel)"
            text_surf = self._font_small.render(text, True, (180, 180, 200))
            surface.blit(text_surf, (50, 5))

    def _draw_selected_info_bar(self, surface: pygame.Surface) -> None:
        """Draw the selected body info bar and reference frame indicator (centered at top).

        Args:
            surface: Target Surface
        """
        lines = []
        if self.selected_body_info:
            lines.append(self.selected_body_info)
        if self._reference_body_id is not None:
            type_names = {0: "Star", 1: "Planet", 2: "Probe", 3: "Charged"}
            type_name = type_names.get(self._reference_body_type, "Unknown")
            lines.append(f"Frame: {type_name} #{self._reference_body_id}")

        if not lines:
            return

        line_height = 20
        for i, line in enumerate(lines):
            text_surf = self._font_label.render(line, True, TEXT_HIGHLIGHT)
            tr = text_surf.get_rect(midtop=(self.width // 2, 5 + i * line_height))
            bg = pygame.Surface((tr.width + 16, tr.height + 6), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            surface.blit(bg, (tr.x - 8, tr.y - 3))
            surface.blit(text_surf, tr)

    def _draw_status_info(self, surface: pygame.Surface) -> None:
        """Draw the top-left status info (FPS, body count, speed, mouse position).

        Args:
            surface: Target Surface
        """
        lines = [
            f"Bodies: {self._num_bodies}  |  Speed: {self._time_speed:.0f}x  |  FPS: {self._fps:.0f}",
        ]
        if self._has_mouse_pos:
            wx, wy = self._mouse_world_pos
            lines.append(f"Mouse: ({wx:.3e}, {wy:.3e}) m")

        # Calculate total dimensions
        line_height = 18
        total_h = len(lines) * line_height + 8
        max_w = max(self._font_small.size(l)[0] for l in lines) + 12

        bg = pygame.Surface((max_w, total_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        surface.blit(bg, (8, 8))

        for i, line in enumerate(lines):
            text_surf = self._font_small.render(line, True, TEXT_COLOR)
            surface.blit(text_surf, (14, 12 + i * line_height))

    def _draw_scale_bar(self, surface: pygame.Surface, camera) -> None:
        """Draw the bottom-right scale bar.

        Args:
            surface: Target Surface
            camera: Camera object used to calculate world distance
        """
        from src.config import SCALE_BAR_X, SCALE_BAR_Y

        raw = 200.0 * camera.world_scale / camera.zoom  # world distance corresponding to ~200px

        # Round to a nice number (1, 2, or 5 × power of 10)
        scaled = round_to_nice_number(raw)

        screen_length = scaled * camera.zoom / camera.world_scale
        int_length = int(screen_length)

        x = self.width - SCALE_BAR_X - int_length
        y = self.height - SCALE_BAR_Y

        # Horizontal line
        bar_color = (200, 200, 220)
        pygame.draw.line(surface, bar_color, (x, y), (x + int_length, y), 2)
        # Vertical end lines
        pygame.draw.line(surface, bar_color, (x, y - 3), (x, y + 3), 2)
        pygame.draw.line(surface, bar_color, (x + int_length, y - 3), (x + int_length, y + 3), 2)

        # Text
        if scaled >= 1e12:
            text = f"{scaled:.0e} m"
        elif scaled >= 1e9:
            text = f"{scaled:.0e} m"
        elif scaled >= 1e6:
            text = f"{scaled:.0e} m"
        elif scaled >= 1e3:
            text = f"{scaled:.0e} m"
        else:
            text = f"{scaled:.0f} m"

        text_surf = self._font_small.render(text, True, (200, 200, 220))
        tr = text_surf.get_rect(midtop=(x + int_length // 2, y + 6))
        surface.blit(text_surf, tr)
