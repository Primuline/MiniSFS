"""Scientific notation input dialog module.

Provides a base dialog class for scientific notation input with coefficient/exponent fields,
and two concrete subclasses: EditBodyDialog and ScientificInputDialog.
"""

import math
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Union

import pygame

from src.config import WINDOW_HEIGHT, WINDOW_WIDTH

# ============================================================================
# Color constants
# ============================================================================

DIALOG_BG = (20, 20, 40, 220)
DIALOG_BORDER = (60, 60, 100)
TEXT_COLOR = (200, 200, 220)
TEXT_HIGHLIGHT = (255, 255, 255)
LABEL_COLOR = (150, 150, 180)
PLACEHOLDER_COLOR = (100, 100, 120)
FIELD_INACTIVE = (50, 50, 80)
FIELD_ACTIVE = (60, 60, 100)
FIELD_BORDER_INACTIVE = (80, 80, 110)
FIELD_BORDER_ACTIVE = (200, 200, 255)
CURSOR_COLOR = (200, 200, 255)
BTN_OK_COLOR = (40, 80, 40)
BTN_OK_HOVER = (60, 140, 60)
BTN_CANCEL_COLOR = (80, 40, 40)
BTN_CANCEL_HOVER = (140, 60, 60)
BTN_TEXT_COLOR = (220, 220, 220)
HINT_COLOR = (120, 120, 140)

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

    def __init__(self) -> None:
        """Initialize the base dialog."""
        self.visible: bool = False
        self.active_field_index: int = -1  # -1 = no active field
        self.cursor_visible: bool = True

        # Input fields
        self.fields: List[Dict] = []
        for idx, (_, placeholder, allow_decimal, allow_negative) in enumerate(FIELD_DEFS):
            coeff_field = idx in (0, 2, 4)
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
        self._font_title: pygame.font.Font = pygame.font.Font(None, 20)
        self._font_field: pygame.font.Font = pygame.font.Font(None, 18)
        self._font_label: pygame.font.Font = pygame.font.Font(None, 16)
        self._font_small: pygame.font.Font = pygame.font.Font(None, 14)

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

        for row in range(NUM_ROWS):
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
        btn_y = row_start_y + NUM_ROWS * ROW_SPACING + 5
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
                return self.get_results()
            if self.cancel_rect.collidepoint(event.pos):
                return "CANCEL"
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "CANCEL"
            if event.key == pygame.K_RETURN:
                return self.get_results()
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

            return None

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

        # Semi-transparent background overlay
        mask = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 120))
        surface.blit(mask, (0, 0))

        # Panel background
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill(DIALOG_BG)
        surface.blit(panel_surf, (px, py))
        pygame.draw.rect(surface, DIALOG_BORDER, (px, py, pw, ph), 2, border_radius=8)

        # Title
        title_surf = self._font_title.render(self._title, True, TEXT_HIGHLIGHT)
        tr = title_surf.get_rect(center=(cx, py + 18))
        surface.blit(title_surf, tr)

        # Cursor blink
        now = pygame.time.get_ticks()
        self.cursor_visible = (now // BLINK_INTERVAL_MS) % 2 == 0

        row_start_y = cy + self.ROW_START_OFFSET
        label_x = px + 15

        for row in range(NUM_ROWS):
            row_y = row_start_y + row * ROW_SPACING
            coeff_idx = row * 2
            exp_idx = row * 2 + 1

            # Row label
            lbl_surf = self._font_label.render(ROW_LABELS[row], True, LABEL_COLOR)
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
            unit_surf = self._font_small.render(ROW_UNITS[row], True, LABEL_COLOR)
            unit_rect = unit_surf.get_rect(
                midleft=(self.fields[exp_idx]["rect"].right + 4, row_y + FIELD_HEIGHT // 2)
            )
            surface.blit(unit_surf, unit_rect)

        # OK / Cancel buttons
        self._draw_button(surface, self.ok_rect, "OK",
                          BTN_OK_HOVER if self.ok_hovered else BTN_OK_COLOR)
        self._draw_button(surface, self.cancel_rect, "Cancel",
                          BTN_CANCEL_HOVER if self.cancel_hovered else BTN_CANCEL_COLOR)

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
        pygame.draw.rect(surface, bg_color, rect, border_radius=3)

        border_color = FIELD_BORDER_ACTIVE if is_active else FIELD_BORDER_INACTIVE
        pygame.draw.rect(surface, border_color, rect, 1, border_radius=3)

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
        pygame.draw.rect(surface, color, rect, border_radius=4)
        pygame.draw.rect(surface, DIALOG_BORDER, rect, 1, border_radius=4)
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
