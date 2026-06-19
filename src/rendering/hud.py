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
    PROBE_LANDING_SPEED_LIMIT_DEFAULT,
    DEFAULT_RADIUS_STAR,
    PROBE_ROCKET_EXHAUST_VELOCITY_DEFAULT,
    PROBE_ROCKET_FUEL_MASS_DEFAULT,
    PROBE_ROCKET_MASS_FLOW_RATE_DEFAULT,
    PROBE_ROCKET_TOTAL_MASS_DEFAULT,
    UI_BLACK,
    UI_DARK,
    UI_DIM,
    UI_DISABLED,
    UI_PANEL_BG,
    UI_WHITE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    WORLD_SCALE,
    get_ui_font,
)
from src.core.utils.tools import round_to_nice_number
from src.rendering.input_dialog import (
    EditBodyDialog,
    ProbeInputDialog,
    ScientificInputDialog,
)
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

PANEL_BG = UI_PANEL_BG
PANEL_BORDER = UI_WHITE
TEXT_COLOR = UI_WHITE
TEXT_HIGHLIGHT = UI_WHITE
LABEL_COLOR = UI_DIM
BTN_NORMAL = UI_BLACK
BTN_HOVER = UI_DARK
BTN_ACTIVE = UI_WHITE
BTN_DISABLED = UI_BLACK

INFO_PANEL_WIDTH = 220
TOOLBAR_WIDTH = 44
CONTROL_BAR_HEIGHT = 36


def format_time_multiplier(speed: float) -> str:
    """Return a compact label for the current time multiplier."""
    if speed <= 0.0:
        return "0x"
    if speed < 1.0:
        denominator = int(round(1.0 / speed))
        return f"1/{denominator}x"
    return f"{speed:.0f}x"


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
        self.font = get_ui_font(font_size)
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

        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2 if self.active else 1)

        # Text
        text_color = UI_BLACK if self.active else TEXT_COLOR
        if self.hovered and not self.active:
            text_color = TEXT_HIGHLIGHT
        if self.disabled:
            text_color = UI_DISABLED
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
        self._font_title = get_ui_font(20)
        self._font_medium = get_ui_font(18)
        self._font_label = get_ui_font(16)
        self._font_value = get_ui_font(16)
        self._font_small = get_ui_font(14)

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
        ctrl_x = self.width // 2 - 112
        self.time_buttons: List[Button] = []
        time_actions = [
            ("||", "PLAY_PAUSE"),
            ("<<", "SLOW_HALF"),
            ("1x", "TIME_1X"),
            (">>", "FAST_DOUBLE"),
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

        # Probe rocket parameter dialog
        self.probe_total_mass: float = 0.0
        self.probe_fuel_mass: float = 0.0
        self.probe_dry_mass: float = 0.0
        self.probe_exhaust_velocity: float = 0.0
        self.probe_mass_flow_rate: float = 0.0
        self.probe_radius: float = DEFAULT_RADIUS_PROBE * WORLD_SCALE
        self.probe_landing_speed_limit: float = PROBE_LANDING_SPEED_LIMIT_DEFAULT
        self.probe_dialog_visible: bool = False
        self._probe_dialog: ProbeInputDialog = ProbeInputDialog()

        # Probe fuel HUD, shown only in probe reference frame.
        self._probe_fuel_info: Optional[Dict[str, float]] = None

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

        # ============ Startup mode menu ============
        menu_w = 260
        menu_h = 48
        menu_x = self.width // 2 - menu_w // 2
        menu_y = self.height // 2 - 20
        self.mode_menu_buttons: List[Button] = [
            Button(
                menu_x,
                menu_y,
                menu_w,
                menu_h,
                "Level Mode",
                "LEVEL_MODE",
                font_size=22,
            ),
            Button(
                menu_x,
                menu_y + 64,
                menu_w,
                menu_h,
                "Sandbox Mode",
                "START_SANDBOX",
                font_size=22,
            ),
        ]
        self.level_select_buttons: List[Button] = []
        grid_w = 120
        grid_h = 44
        grid_gap_x = 18
        grid_gap_y = 18
        grid_total_w = 4 * grid_w + 3 * grid_gap_x
        grid_x = self.width // 2 - grid_total_w // 2
        grid_y = self.height // 2 - 70
        for row in range(2):
            for col in range(4):
                level_number = row * 4 + col + 1
                btn = Button(
                    grid_x + col * (grid_w + grid_gap_x),
                    grid_y + row * (grid_h + grid_gap_y),
                    grid_w,
                    grid_h,
                    f"Level {level_number}",
                    f"START_LEVEL_{level_number}",
                    font_size=18,
                )
                if level_number not in (1, 2):
                    btn.disabled = True
                self.level_select_buttons.append(btn)
        self.level_mode_enabled = False

        # ============ Level message dialog ============
        dialog_w = 480
        dialog_h = 230
        dialog_y = self.height // 2 - dialog_h // 2
        self.level_message_visible: bool = False
        self._level_message_title: str = ""
        self._level_message_lines: List[str] = []
        self._level_message_escape_action: str = "LEVEL_MESSAGE_OK"
        self._level_message_buttons: List[Button] = []
        self._level_message_button = Button(
            self.width // 2 - 56,
            dialog_y + dialog_h - 58,
            112,
            34,
            "OK",
            "LEVEL_MESSAGE_OK",
            font_size=18,
        )
        self._level_message_buttons = [self._level_message_button]

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

        # Probe rocket dialog has priority (when visible)
        if self.probe_dialog_visible:
            dlg_result = self._probe_dialog.handle_event(event)
            if dlg_result is not None:
                if isinstance(dlg_result, dict):
                    self.probe_total_mass = dlg_result["total_mass"]
                    self.probe_fuel_mass = dlg_result["fuel_mass"]
                    self.probe_dry_mass = dlg_result["dry_mass"]
                    self.probe_exhaust_velocity = dlg_result["exhaust_velocity"]
                    self.probe_mass_flow_rate = dlg_result["mass_flow_rate"]
                    self.probe_radius = dlg_result["radius"]
                    self.probe_landing_speed_limit = dlg_result["landing_speed_limit"]
                    return "PROBE_DIALOG_OK"
                if dlg_result == "CANCEL":
                    return "PROBE_DIALOG_CANCEL"
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

    def handle_mode_menu_event(self, event: pygame.event.Event) -> Optional[str]:
        """Handle startup mode menu events.

        Args:
            event: Pygame event

        Returns:
            Menu command string, or None.
        """
        for btn in self.mode_menu_buttons:
            action = btn.handle_event(event)
            if action:
                return action
        return None

    def handle_level_select_event(self, event: pygame.event.Event) -> Optional[str]:
        """Handle level selection menu events."""
        for btn in self.level_select_buttons:
            action = btn.handle_event(event)
            if action:
                return action
        return None

    def handle_level_message_event(self, event: pygame.event.Event) -> Optional[str]:
        """Handle level objective/result popup events."""
        if not self.level_message_visible:
            return None
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.hide_level_message()
            return self._level_message_escape_action
        for button in self._level_message_buttons:
            action = button.handle_event(event)
            if action:
                self.hide_level_message()
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

    def set_level_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable sandbox editing tools while in a fixed level."""
        self.level_mode_enabled = enabled
        if enabled:
            self.active_tool = None
        for btn in self.tool_buttons:
            btn.disabled = enabled
            if enabled:
                btn.active = False

    def show_level_message(
        self,
        title: str,
        lines: List[str],
        buttons: Optional[List[Tuple[str, str]]] = None,
        escape_action: str = "LEVEL_MESSAGE_OK",
    ) -> None:
        """Show a centered level objective/result popup."""
        self._level_message_title = title
        self._level_message_lines = lines
        self._level_message_escape_action = escape_action
        if buttons is None:
            buttons = [("OK", "LEVEL_MESSAGE_OK")]
        dialog_w = 480
        dialog_h = 230
        dialog_y = self.height // 2 - dialog_h // 2
        total_w = len(buttons) * 112 + max(0, len(buttons) - 1) * 16
        start_x = self.width // 2 - total_w // 2
        self._level_message_buttons = []
        for idx, (label, action) in enumerate(buttons):
            self._level_message_buttons.append(
                Button(
                    start_x + idx * (112 + 16),
                    dialog_y + dialog_h - 58,
                    112,
                    34,
                    label,
                    action,
                    font_size=18,
                )
            )
        self._level_message_button = self._level_message_buttons[0]
        self.level_message_visible = True
        for button in self._level_message_buttons:
            button.hovered = False

    def hide_level_message(self) -> None:
        """Hide the centered level objective/result popup."""
        self.level_message_visible = False

    def set_play_pause_state(self, is_paused: bool) -> None:
        """Set the play/pause state.

        Args:
            is_paused: Whether paused
        """
        self.is_paused = is_paused
        if self.time_buttons:
            self.time_buttons[0].text = ">" if is_paused else "||"

    def set_time_speed(self, speed: float) -> None:
        """Set the time speed.

        Args:
            speed: Time speed multiplier
        """
        self.time_speed = speed
        for btn in self.time_buttons:
            btn.active = False
        if len(self.time_buttons) >= 3 and abs(speed - 1.0) < 1e-9:
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

    def show_probe_dialog(
        self,
        total_mass: float = PROBE_ROCKET_TOTAL_MASS_DEFAULT,
        fuel_mass: float = PROBE_ROCKET_FUEL_MASS_DEFAULT,
        exhaust_velocity: float = PROBE_ROCKET_EXHAUST_VELOCITY_DEFAULT,
        mass_flow_rate: float = PROBE_ROCKET_MASS_FLOW_RATE_DEFAULT,
        radius_meters: float = DEFAULT_RADIUS_PROBE * WORLD_SCALE,
        landing_speed_limit: float = PROBE_LANDING_SPEED_LIMIT_DEFAULT,
    ) -> None:
        """Open the probe rocket parameter dialog."""
        self._probe_dialog.prefill(
            total_mass=total_mass,
            fuel_mass=fuel_mass,
            exhaust_velocity=exhaust_velocity,
            mass_flow_rate=mass_flow_rate,
            radius_meters=radius_meters,
            landing_speed_limit=landing_speed_limit,
        )
        self.probe_dialog_visible = True
        self._probe_dialog.visible = True

    def hide_probe_dialog(self) -> None:
        """Close the probe rocket parameter dialog and reset input state."""
        self.probe_dialog_visible = False
        self._probe_dialog.visible = False
        self._probe_dialog.active_field_index = -1
        self._probe_dialog.error_message = ""

    def set_probe_fuel_info(
        self,
        fuel_mass: float,
        dry_mass: float,
        initial_fuel_mass: float,
    ) -> None:
        """Update the probe fuel HUD data.

        Args:
            fuel_mass: Current fuel mass in kg.
            dry_mass: Dry mass in kg.
            initial_fuel_mass: Initial fuel mass in kg.
        """
        fuel_pct = 0.0
        if initial_fuel_mass > 0.0:
            fuel_pct = max(0.0, min(100.0, fuel_mass / initial_fuel_mass * 100.0))
        self._probe_fuel_info = {
            "fuel_mass": max(0.0, fuel_mass),
            "dry_mass": dry_mass,
            "initial_fuel_mass": initial_fuel_mass,
            "fuel_pct": fuel_pct,
        }

    def clear_probe_fuel_info(self) -> None:
        """Hide the probe fuel HUD."""
        self._probe_fuel_info = None

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
        if self.probe_dialog_visible:
            self._probe_dialog.draw(surface)
        if self.custom_dialog_visible:
            self._draw_custom_dialog(surface)
        self._draw_time_controls(surface)
        self._draw_active_tool_indicator(surface)
        self._draw_selected_info_bar(surface)
        self._draw_status_info(surface)
        self._draw_probe_fuel_panel(surface)
        if camera is not None:
            self._draw_scale_bar(surface, camera)
        if self.level_message_visible:
            self._draw_level_message(surface)

    def draw_mode_menu(self, surface: pygame.Surface) -> None:
        """Draw the startup mode selection menu.

        Args:
            surface: Target Surface
        """
        title = self._font_title.render("MiniSFS", True, TEXT_HIGHLIGHT)
        title_rect = title.get_rect(center=(self.width // 2, self.height // 2 - 110))
        surface.blit(title, title_rect)

        subtitle = self._font_label.render("Select mode", True, TEXT_COLOR)
        subtitle_rect = subtitle.get_rect(center=(self.width // 2, self.height // 2 - 82))
        surface.blit(subtitle, subtitle_rect)

        for btn in self.mode_menu_buttons:
            btn.draw(surface)

        esc_hint = self._font_small.render("Esc: quit", True, LABEL_COLOR)
        esc_rect = esc_hint.get_rect(center=(self.width // 2, self.height // 2 + 130))
        surface.blit(esc_hint, esc_rect)

    def draw_level_select(self, surface: pygame.Surface) -> None:
        """Draw the level selection grid."""
        title = self._font_title.render("Level Mode", True, TEXT_HIGHLIGHT)
        title_rect = title.get_rect(center=(self.width // 2, self.height // 2 - 150))
        surface.blit(title, title_rect)

        subtitle = self._font_label.render("Select level", True, TEXT_COLOR)
        subtitle_rect = subtitle.get_rect(center=(self.width // 2, self.height // 2 - 122))
        surface.blit(subtitle, subtitle_rect)

        for btn in self.level_select_buttons:
            btn.draw(surface)

        esc_hint = self._font_small.render("Esc: back", True, LABEL_COLOR)
        esc_rect = esc_hint.get_rect(center=(self.width // 2, self.height // 2 + 96))
        surface.blit(esc_hint, esc_rect)

    def _draw_level_message(self, surface: pygame.Surface) -> None:
        """Draw the centered level objective/result popup."""
        mask = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 160))
        surface.blit(mask, (0, 0))

        panel_w = 480
        panel_h = 230
        panel_x = self.width // 2 - panel_w // 2
        panel_y = self.height // 2 - panel_h // 2
        pygame.draw.rect(surface, UI_BLACK, (panel_x, panel_y, panel_w, panel_h))
        pygame.draw.rect(surface, UI_WHITE, (panel_x, panel_y, panel_w, panel_h), 2)

        title = self._font_medium.render(self._level_message_title, True, TEXT_HIGHLIGHT)
        title_rect = title.get_rect(center=(self.width // 2, panel_y + 36))
        surface.blit(title, title_rect)

        line_y = panel_y + 78
        for line in self._level_message_lines:
            text = self._font_label.render(line, True, TEXT_COLOR)
            text_rect = text.get_rect(center=(self.width // 2, line_y))
            surface.blit(text, text_rect)
            line_y += 28

        for button in self._level_message_buttons:
            button.draw(surface)

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

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill(PANEL_BG)
        surface.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(
            surface, PANEL_BORDER,
            (panel_x, panel_y, panel_w, panel_h), 2,
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
            value_font = self._font_value
            if value_font.size(value)[0] > panel_w - 92:
                value_font = self._font_small
            value_surf = value_font.render(value, True, TEXT_COLOR)
            surface.blit(value_surf, (panel_x + 80, y))

    def _draw_toolbar(self, surface: pygame.Surface) -> None:
        """Draw the toolbar.

        Args:
            surface: Target Surface
        """
        tool_rect = pygame.Rect(0, 0, TOOLBAR_WIDTH, self.height)
        pygame.draw.rect(surface, UI_BLACK, tool_rect)
        pygame.draw.rect(surface, UI_WHITE, tool_rect, 1)

        title_font = get_ui_font(11)
        if title_font.size("TOOLS")[0] > TOOLBAR_WIDTH - 4:
            title_font = get_ui_font(10)
        title_surf = title_font.render("TOOLS", True, LABEL_COLOR)
        title_rect = title_surf.get_rect(center=(TOOLBAR_WIDTH // 2, 70))
        surface.blit(title_surf, title_rect)

        # Tool buttons
        for btn in self.tool_buttons:
            btn.draw(surface)

        # Current tool hint
        if self.active_tool:
            hint = self.get_tool_display_name(self.active_tool)
            hint_surf = self._font_small.render(hint, True, TEXT_HIGHLIGHT)
            surface.blit(hint_surf, (TOOLBAR_WIDTH + 8, 55))

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
        bar_w = 276
        bar_x = self.width // 2 - bar_w // 2

        bar_bg = pygame.Surface((bar_w, CONTROL_BAR_HEIGHT), pygame.SRCALPHA)
        bar_bg.fill(PANEL_BG)
        surface.blit(bar_bg, (bar_x, bar_y))
        pygame.draw.rect(
            surface, PANEL_BORDER,
            (bar_x, bar_y, bar_w, CONTROL_BAR_HEIGHT), 2,
        )

        # Buttons
        for btn in self.time_buttons:
            btn.draw(surface)

        # Speed indicator
        speed_text = format_time_multiplier(self.time_speed)
        if self.is_paused:
            speed_text = f"PAUSED {speed_text}"
        speed_surf = self._font_small.render(speed_text, True, TEXT_COLOR)
        sr = speed_surf.get_rect(
            midleft=(self.time_buttons[-1].rect.right + 10, bar_y + CONTROL_BAR_HEIGHT // 2)
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
            text_surf = self._font_small.render(text, True, TEXT_COLOR)
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
            bg.fill(PANEL_BG)
            surface.blit(bg, (tr.x - 8, tr.y - 3))
            pygame.draw.rect(surface, PANEL_BORDER, (tr.x - 8, tr.y - 3, tr.width + 16, tr.height + 6), 1)
            surface.blit(text_surf, tr)

    def _draw_status_info(self, surface: pygame.Surface) -> None:
        """Draw the top-left status info (FPS, body count, speed, mouse position).

        Args:
            surface: Target Surface
        """
        lines = [
            f"Bodies: {self._num_bodies}  |  Speed: {format_time_multiplier(self._time_speed)}  |  FPS: {self._fps:.0f}",
        ]
        if self._has_mouse_pos:
            wx, wy = self._mouse_world_pos
            lines.append(f"Mouse: ({wx:.3e}, {wy:.3e}) m")

        # Calculate total dimensions
        line_height = 18
        total_h = len(lines) * line_height + 8
        max_w = max(self._font_small.size(l)[0] for l in lines) + 12

        bg = pygame.Surface((max_w, total_h), pygame.SRCALPHA)
        bg.fill(PANEL_BG)
        surface.blit(bg, (TOOLBAR_WIDTH + 8, 8))
        pygame.draw.rect(surface, PANEL_BORDER, (TOOLBAR_WIDTH + 8, 8, max_w, total_h), 1)

        for i, line in enumerate(lines):
            text_surf = self._font_small.render(line, True, TEXT_COLOR)
            surface.blit(text_surf, (TOOLBAR_WIDTH + 14, 12 + i * line_height))

    def _draw_probe_fuel_panel(self, surface: pygame.Surface) -> None:
        """Draw the right-side fuel panel for probe reference frame mode."""
        if self._probe_fuel_info is None:
            return

        panel_w = 220
        panel_h = 78
        panel_x = self.width - panel_w - 10
        panel_y = 220 if self.info_panel_visible else 10

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill(PANEL_BG)
        surface.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(
            surface,
            PANEL_BORDER,
            (panel_x, panel_y, panel_w, panel_h),
            2,
        )

        info = self._probe_fuel_info
        title = self._font_title.render("Probe Fuel", True, TEXT_HIGHLIGHT)
        surface.blit(title, (panel_x + 10, panel_y + 8))

        pct = info["fuel_pct"]
        pct_text = self._font_value.render(f"Fuel: {pct:.1f}%", True, TEXT_COLOR)
        surface.blit(pct_text, (panel_x + 10, panel_y + 30))

        mass_text = self._font_value.render(
            f"Fuel Mass: {info['fuel_mass']:.3e} kg",
            True,
            TEXT_COLOR,
        )
        surface.blit(mass_text, (panel_x + 10, panel_y + 50))

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
        bar_color = UI_WHITE
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

        text_surf = self._font_small.render(text, True, TEXT_COLOR)
        tr = text_surf.get_rect(midtop=(x + int_length // 2, y + 6))
        surface.blit(text_surf, tr)
