"""Scientific notation input dialog module.

Provides a base dialog class for scientific notation input with coefficient/exponent fields,
and two concrete subclasses: EditBodyDialog and ScientificInputDialog.
"""

import math
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Union

import pygame

from src.config import (
    DEFAULT_RADIUS_PROBE,
    PROBE_ROCKET_EXHAUST_VELOCITY_DEFAULT,
    PROBE_ROCKET_FUEL_MASS_DEFAULT,
    PROBE_ROCKET_MASS_FLOW_RATE_DEFAULT,
    PROBE_ROCKET_TOTAL_MASS_DEFAULT,
    UI_BLACK,
    UI_DARK,
    UI_DIM,
    UI_DISABLED,
    UI_OVERLAY_BG,
    UI_PANEL_BG,
    UI_WHITE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    WORLD_SCALE,
    get_ui_font,
)

# ============================================================================
# Color constants
# ============================================================================

DIALOG_BG = UI_PANEL_BG
DIALOG_BORDER = UI_WHITE
TEXT_COLOR = UI_WHITE
TEXT_HIGHLIGHT = UI_WHITE
LABEL_COLOR = UI_DIM
PLACEHOLDER_COLOR = UI_DISABLED
FIELD_INACTIVE = UI_BLACK
FIELD_ACTIVE = UI_DARK
FIELD_BORDER_INACTIVE = UI_DIM
FIELD_BORDER_ACTIVE = UI_WHITE
CURSOR_COLOR = UI_WHITE
BTN_OK_COLOR = UI_BLACK
BTN_OK_HOVER = UI_DARK
BTN_CANCEL_COLOR = UI_BLACK
BTN_CANCEL_HOVER = UI_DARK
BTN_TEXT_COLOR = UI_WHITE
HINT_COLOR = UI_DIM

# Shared layout constants
FIELD_HEIGHT: int = 24
COEFF_WIDTH: int = 80
EXP_WIDTH: int = 45
BUTTON_WIDTH: int = 72
BUTTON_HEIGHT: int = 28
PANEL_WIDTH: int = 340
ROW_SPACING: int = 35
BLINK_INTERVAL_MS: int = 500

# Each field definition: (label, placeholder, allow_decimal, allow_negative)
# Three rows: Mass, Charge, Radius — each with coefficient + exponent.
FIELD_DEFS: List[Tuple[str, str, bool, bool]] = [
    ("Mass coeff",    "1.0", True,  True),
    ("Mass exp",      "26",  False, True),
    ("Charge coeff",   "0.0", True,  True),
    ("Charge exp",    "0",   False, True),
    ("Radius coeff",  "6.4", True,  False),
    ("Radius exp",    "3",   False, False),
]

ROW_LABELS: List[str] = ["Mass", "Charge", "Radius"]
ROW_UNITS: List[str] = ["kg", "C", "km"]

NUM_ROWS: int = 3
NUM_FIELDS: int = 6  # 3 rows x 2 fields (coeff, exp)

PROBE_FIELD_DEFS: List[Tuple[str, str, bool, bool]] = [
    ("Total mass coeff", "1.0", True, False),
    ("Total mass exp", "5", False, True),
    ("Fuel mass coeff", "7.0", True, False),
    ("Fuel mass exp", "4", False, True),
    ("Exhaust velocity coeff", "3.0", True, False),
    ("Exhaust velocity exp", "3", False, True),
    ("Mass flow coeff", "5.0", True, False),
    ("Mass flow exp", "1", False, True),
    ("Radius coeff", "8.0", True, False),
    ("Radius exp", "2", False, True),
]

PROBE_ROW_LABELS: List[str] = [
    "Total mass",
    "Fuel mass",
    "Exhaust v",
    "Mass flow",
    "Radius",
]
PROBE_ROW_UNITS: List[str] = ["kg", "kg", "m/s", "kg/s", "km"]


# ============================================================================
# Utility functions
# ============================================================================


def _float_to_components(value: float) -> Tuple[str, str]:
    """Split a float into coefficient and exponent text.

    Args:
        value: Float value

    Returns:
        (coefficient_text, exponent_text) tuple
    """
    if value == 0.0:
        return ("0", "0")
    exp = int(math.floor(math.log10(abs(value))))
    coeff = value / (10 ** exp)
    coeff = round(coeff, 6)
    coeff_str = str(coeff)
    return (coeff_str, str(exp))


def validate_probe_parameters(
    total_mass: float,
    fuel_mass: float,
    exhaust_velocity: float,
    mass_flow_rate: float,
    radius: float,
) -> Dict[str, float]:
    """Validate and normalize probe rocket parameters.

    Args:
        total_mass: Initial total mass in kg.
        fuel_mass: Initial fuel mass in kg.
        exhaust_velocity: Exhaust velocity in m/s.
        mass_flow_rate: Fuel consumption rate in kg/s.
        radius: Body radius in meters.

    Returns:
        Validated parameters including dry_mass.

    Raises:
        ValueError: If any parameter violates the probe rocket constraints.
    """
    values = (total_mass, fuel_mass, exhaust_velocity, mass_flow_rate, radius)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("All values must be finite")
    if total_mass <= 0.0:
        raise ValueError("Total mass must be > 0")
    if fuel_mass < 0.0 or fuel_mass >= total_mass:
        raise ValueError("Fuel mass must be >= 0 and < total mass")
    if exhaust_velocity <= 0.0:
        raise ValueError("Exhaust velocity must be > 0")
    if mass_flow_rate <= 0.0:
        raise ValueError("Mass flow rate must be > 0")
    if radius <= 0.0:
        raise ValueError("Radius must be > 0")

    return {
        "total_mass": total_mass,
        "fuel_mass": fuel_mass,
        "dry_mass": total_mass - fuel_mass,
        "exhaust_velocity": exhaust_velocity,
        "mass_flow_rate": mass_flow_rate,
        "radius": radius,
    }


# ============================================================================
# Base dialog — shared logic
# ============================================================================


class BaseInputDialog(ABC):
    """Abstract base dialog for scientific notation input.

    Provides shared logic for layout computation, field drawing, input validation,
    keyboard/mouse event handling, and cursor blinking.

    Subclasses must set:
        - _title: Dialog title string
        - PANEL_HEIGHT: Panel height in pixels
        - ROW_START_OFFSET: Y offset from screen center for the first row

    Subclasses may override:
        - prefill(): To set initial field values
        - get_results(): To compute return values from fields
    """

    # Layout constants (overridable)
    PANEL_HEIGHT: int = 235
    ROW_START_OFFSET: int = -30
    FIELD_DEFS: List[Tuple[str, str, bool, bool]] = FIELD_DEFS
    ROW_LABELS: List[str] = ROW_LABELS
    ROW_UNITS: List[str] = ROW_UNITS

    def __init__(self) -> None:
        """Initialize the base dialog."""
        self.visible: bool = False
        self.active_field_index: int = -1  # -1 = no active field
        self.cursor_visible: bool = True
        self.error_message: str = ""

        # Input fields
        self.fields: List[Dict] = []
        for idx, (_, placeholder, allow_decimal, allow_negative) in enumerate(self.FIELD_DEFS):
            coeff_field = idx % 2 == 0
            width = COEFF_WIDTH if coeff_field else EXP_WIDTH
            self.fields.append({
                "rect": pygame.Rect(0, 0, width, FIELD_HEIGHT),
                "text": placeholder,
                "placeholder": placeholder,
                "allow_decimal": allow_decimal,
                "allow_negative": allow_negative,
            })

        # OK / Cancel buttons rect
        self.ok_rect: pygame.Rect = pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT)
        self.cancel_rect: pygame.Rect = pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT)

        # Button hover state
        self.ok_hovered: bool = False
        self.cancel_hovered: bool = False

        # Fonts
        self._font_title: pygame.font.Font = get_ui_font(20)
        self._font_field: pygame.font.Font = get_ui_font(18)
        self._font_label: pygame.font.Font = get_ui_font(16)
        self._font_small: pygame.font.Font = get_ui_font(14)

        # Compute layout
        self._compute_layout()

    # ------------------------------------------------------------------
    # Properties for subclass customization
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def _title(self) -> str:
        """Dialog title string."""
        ...

    # ------------------------------------------------------------------
    # Layout computation
    # ------------------------------------------------------------------

    def _compute_layout(self) -> None:
        """Compute positions for all input fields and buttons."""
        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        row_start_y = cy + self.ROW_START_OFFSET

        coeff_x = cx - 55
        exp_x = cx + 60

        num_rows = len(self.ROW_LABELS)
        for row in range(num_rows):
            coeff_idx = row * 2
            exp_idx = row * 2 + 1
            row_y = row_start_y + row * ROW_SPACING

            cf = self.fields[coeff_idx]
            cf["rect"].x = coeff_x
            cf["rect"].y = row_y
            cf["rect"].centery = row_y + FIELD_HEIGHT // 2

            ef = self.fields[exp_idx]
            ef["rect"].x = exp_x
            ef["rect"].y = row_y
            ef["rect"].centery = row_y + FIELD_HEIGHT // 2

        # OK / Cancel buttons
        btn_y = row_start_y + num_rows * ROW_SPACING + 5
        self.ok_rect.x = cx - 80
        self.ok_rect.y = btn_y
        self.cancel_rect.x = cx + 8
        self.cancel_rect.y = btn_y

    # ------------------------------------------------------------------
    # Field value access
    # ------------------------------------------------------------------

    def _get_field_value(self, coeff_idx: int, exp_idx: int) -> float:
        """Read coefficient and exponent fields and compute the value.

        Args:
            coeff_idx: Coefficient input field index
            exp_idx: Exponent input field index

        Returns:
            Computed numeric value
        """
        coeff_text = self.fields[coeff_idx]["text"]
        exp_text = self.fields[exp_idx]["text"]
        try:
            coeff = float(coeff_text) if coeff_text else 1.0
        except ValueError:
            coeff = 1.0
        try:
            exp = int(exp_text) if exp_text else 0
        except ValueError:
            exp = 0
        return coeff * (10 ** exp)

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    def _is_valid_input(self, char: str, field_idx: int) -> bool:
        """Check if the input character is valid for the given field.

        Args:
            char: Input character
            field_idx: Input field index

        Returns:
            True if valid
        """
        field = self.fields[field_idx]
        if char in "0123456789":
            return True
        if char == "." and field["allow_decimal"]:
            return "." not in field["text"]
        if char == "-" and field["allow_negative"]:
            return field["text"] == ""
        return False

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(
        self, event: pygame.event.Event
    ) -> Optional[Union[str, Dict[str, float]]]:
        """Handle a Pygame event.

        Args:
            event: Pygame event

        Returns:
            - dict with results on OK, or
            - "CANCEL" on cancel, or
            - None if event was consumed with no action
        """
        if not self.visible:
            return None

        if event.type == pygame.MOUSEMOTION:
            self.ok_hovered = self.ok_rect.collidepoint(event.pos)
            self.cancel_hovered = self.cancel_rect.collidepoint(event.pos)
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, field in enumerate(self.fields):
                if field["rect"].collidepoint(event.pos):
                    self.active_field_index = i
                    self.cursor_visible = True
                    return None
            if self.ok_rect.collidepoint(event.pos):
                return self._try_get_results()
            if self.cancel_rect.collidepoint(event.pos):
                return "CANCEL"
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "CANCEL"
            if event.key == pygame.K_RETURN:
                return self._try_get_results()
            if self.active_field_index < 0:
                return None

            field = self.fields[self.active_field_index]

            if event.key == pygame.K_BACKSPACE:
                field["text"] = field["text"][:-1]
                return None

            if event.key == pygame.K_KP_MINUS:
                char = "-"
            elif event.key == pygame.K_KP_PERIOD:
                char = "."
            else:
                try:
                    char = event.unicode
                except Exception:
                    return None

            if char and self._is_valid_input(char, self.active_field_index):
                field["text"] += char
                self.error_message = ""

            return None

        return None

    def _try_get_results(self) -> Optional[Dict[str, float]]:
        """Return dialog results, keeping the dialog open on validation errors."""
        try:
            self.error_message = ""
            return self.get_results()
        except ValueError as exc:
            self.error_message = str(exc)
            return None

    @abstractmethod
    def get_results(self) -> Dict[str, float]:
        """Read all input fields and return the computed parameters."""
        ...

    @abstractmethod
    def prefill(self, *args, **kwargs) -> None:
        """Prefill field values before showing the dialog."""
        ...

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the dialog on the given surface.

        Args:
            surface: Target Pygame Surface
        """
        if not self.visible:
            return

        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        pw = PANEL_WIDTH
        ph = self.PANEL_HEIGHT
        px = cx - pw // 2
        py = cy - ph // 2

        mask = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        mask.fill(UI_OVERLAY_BG)
        surface.blit(mask, (0, 0))

        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill(DIALOG_BG)
        surface.blit(panel_surf, (px, py))
        pygame.draw.rect(surface, DIALOG_BORDER, (px, py, pw, ph), 2)

        # Title
        title_surf = self._font_title.render(self._title, True, TEXT_HIGHLIGHT)
        tr = title_surf.get_rect(center=(cx, py + 18))
        surface.blit(title_surf, tr)

        # Cursor blink
        now = pygame.time.get_ticks()
        self.cursor_visible = (now // BLINK_INTERVAL_MS) % 2 == 0

        row_start_y = cy + self.ROW_START_OFFSET
        label_x = px + 15

        for row in range(len(self.ROW_LABELS)):
            row_y = row_start_y + row * ROW_SPACING
            coeff_idx = row * 2
            exp_idx = row * 2 + 1

            # Row label
            lbl_surf = self._font_label.render(self.ROW_LABELS[row], True, LABEL_COLOR)
            surface.blit(lbl_surf, (label_x, row_y + 3))

            # Coefficient field
            self._draw_field(surface, self.fields[coeff_idx], coeff_idx == self.active_field_index)

            # *10^ label
            power_surf = self._font_small.render("*10^", True, LABEL_COLOR)
            power_rect = power_surf.get_rect(
                midleft=(self.fields[coeff_idx]["rect"].right + 4, row_y + FIELD_HEIGHT // 2)
            )
            surface.blit(power_surf, power_rect)

            # Exponent field
            self._draw_field(surface, self.fields[exp_idx], exp_idx == self.active_field_index)

            # Unit
            unit_surf = self._font_small.render(self.ROW_UNITS[row], True, LABEL_COLOR)
            unit_rect = unit_surf.get_rect(
                midleft=(self.fields[exp_idx]["rect"].right + 4, row_y + FIELD_HEIGHT // 2)
            )
            surface.blit(unit_surf, unit_rect)

        # OK / Cancel buttons
        self._draw_button(surface, self.ok_rect, "OK",
                          BTN_OK_HOVER if self.ok_hovered else BTN_OK_COLOR)
        self._draw_button(surface, self.cancel_rect, "Cancel",
                          BTN_CANCEL_HOVER if self.cancel_hovered else BTN_CANCEL_COLOR)

        if self.error_message:
            err_surf = self._font_small.render(self.error_message, True, TEXT_HIGHLIGHT)
            er = err_surf.get_rect(center=(cx, self.ok_rect.bottom + 12))
            surface.blit(err_surf, er)

        # Bottom hint
        hint_surf = self._font_small.render("Esc to cancel  |  Enter to confirm", True, HINT_COLOR)
        hr = hint_surf.get_rect(center=(cx, py + ph - 10))
        surface.blit(hint_surf, hr)

    def _draw_field(self, surface: pygame.Surface, field: Dict, is_active: bool) -> None:
        """Draw a single input field.

        Args:
            surface: Target Surface
            field: Input field data dict
            is_active: Whether the field is active
        """
        rect = field["rect"]
        bg_color = FIELD_ACTIVE if is_active else FIELD_INACTIVE
        pygame.draw.rect(surface, bg_color, rect)

        border_color = FIELD_BORDER_ACTIVE if is_active else FIELD_BORDER_INACTIVE
        pygame.draw.rect(surface, border_color, rect, 1)

        if field["text"]:
            text_surf = self._font_field.render(field["text"], True, TEXT_HIGHLIGHT)
        else:
            text_surf = self._font_field.render(field["placeholder"], True, PLACEHOLDER_COLOR)

        text_rect = text_surf.get_rect(midleft=(rect.x + 4, rect.centery))
        surface.blit(text_surf, text_rect)

        if is_active and self.cursor_visible:
            cursor_x = text_rect.right + 1
            cursor_y1 = rect.y + 3
            cursor_y2 = rect.bottom - 3
            pygame.draw.line(surface, CURSOR_COLOR, (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)

    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect,
                     text: str, color: Tuple[int, int, int]) -> None:
        """Draw a button.

        Args:
            surface: Target Surface
            rect: Button position rectangle
            text: Button text
            color: Button color
        """
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, DIALOG_BORDER, rect, 1)
        text_surf = self._font_field.render(text, True, BTN_TEXT_COLOR)
        tr = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, tr)


# ============================================================================
# Edit body dialog
# ============================================================================


class EditBodyDialog(BaseInputDialog):
    """Dialog for editing mass, charge, and radius of an existing body.

    handle_event returns:
        - {"mass": float, "charge": float, "radius": float} on OK
        - "CANCEL" on cancel
        - None on consumed event with no action
    """

    PANEL_HEIGHT: int = 235
    ROW_START_OFFSET: int = -30

    @property
    def _title(self) -> str:
        return "Edit Body Parameters"

    def prefill(self, mass: float, charge: float, radius_meters: float = 7.0e8) -> None:
        """Prefill fields with current body values (radius m -> km).

        Args:
            mass: Current mass (kg)
            charge: Current charge (C)
            radius_meters: Current radius (m), internally converted to km
        """
        mass_coeff, mass_exp = _float_to_components(mass)
        charge_coeff, charge_exp = _float_to_components(charge)
        radius_km = radius_meters / 1000.0
        r_coeff, r_exp = _float_to_components(radius_km)

        self.fields[0]["text"] = mass_coeff
        self.fields[1]["text"] = mass_exp
        self.fields[2]["text"] = charge_coeff
        self.fields[3]["text"] = charge_exp
        self.fields[4]["text"] = r_coeff
        self.fields[5]["text"] = r_exp

    def get_results(self) -> Dict[str, float]:
        """Read fields and return mass (kg), charge (C), radius (m).

        Returns:
            {"mass": float (kg), "charge": float (C), "radius": float (m)}
        """
        mass = self._get_field_value(0, 1)
        charge = self._get_field_value(2, 3)
        radius = self._get_field_value(4, 5) * 1000.0  # km -> m
        radius = max(1.0, min(radius, 1.0e12))
        return {"mass": mass, "charge": charge, "radius": radius}


# ============================================================================
# Custom particle input dialog
# ============================================================================


class ScientificInputDialog(BaseInputDialog):
    """Dialog for configuring custom particle parameters.

    handle_event returns:
        - {"mass": float, "charge": float, "radius": float} on OK
        - "CANCEL" on cancel
        - None on consumed event with no action
    """

    PANEL_HEIGHT: int = 275
    ROW_START_OFFSET: int = -70

    @property
    def _title(self) -> str:
        return "Custom Particle Config"

    def prefill(self, mass: float) -> None:
        """Prefill fields with defaults and compute radius from mass.

        Args:
            mass: Current mass (kg), used to compute default radius
        """
        from src.config import CUSTOM_RADIUS_DEFAULT

        for field in self.fields:
            field["text"] = field["placeholder"]

        radius_km = CUSTOM_RADIUS_DEFAULT / 1000.0
        r_coeff, r_exp = _float_to_components(radius_km)
        self.fields[4]["text"] = r_coeff
        self.fields[5]["text"] = r_exp

    def get_results(self) -> Dict[str, float]:
        """Read fields and return mass (kg), charge (C), radius (m).

        Returns:
            {"mass": float (kg), "charge": float (C), "radius": float (m)}
        """
        mass = self._get_field_value(0, 1)
        charge = self._get_field_value(2, 3)
        radius = self._get_field_value(4, 5) * 1000.0  # km -> m
        return {"mass": mass, "charge": charge, "radius": radius}


# ============================================================================
# Probe rocket input dialog
# ============================================================================


class ProbeInputDialog(BaseInputDialog):
    """Dialog for configuring a probe's rocket parameters."""

    PANEL_HEIGHT: int = 330
    ROW_START_OFFSET: int = -105
    FIELD_DEFS = PROBE_FIELD_DEFS
    ROW_LABELS = PROBE_ROW_LABELS
    ROW_UNITS = PROBE_ROW_UNITS

    @property
    def _title(self) -> str:
        return "Probe Rocket Config"

    def prefill(self) -> None:
        """Prefill fields with the configured probe rocket defaults."""
        defaults = [
            PROBE_ROCKET_TOTAL_MASS_DEFAULT,
            PROBE_ROCKET_FUEL_MASS_DEFAULT,
            PROBE_ROCKET_EXHAUST_VELOCITY_DEFAULT,
            PROBE_ROCKET_MASS_FLOW_RATE_DEFAULT,
            DEFAULT_RADIUS_PROBE * WORLD_SCALE / 1000.0,
        ]
        for row, value in enumerate(defaults):
            coeff, exp = _float_to_components(value)
            self.fields[row * 2]["text"] = coeff
            self.fields[row * 2 + 1]["text"] = exp
        self.error_message = ""

    def get_results(self) -> Dict[str, float]:
        """Read and validate probe rocket parameters.

        Returns:
            Probe rocket settings with radius converted to meters.
        """
        total_mass = self._get_field_value(0, 1)
        fuel_mass = self._get_field_value(2, 3)
        exhaust_velocity = self._get_field_value(4, 5)
        mass_flow_rate = self._get_field_value(6, 7)
        radius = self._get_field_value(8, 9) * 1000.0
        return validate_probe_parameters(
            total_mass,
            fuel_mass,
            exhaust_velocity,
            mass_flow_rate,
            radius,
        )
