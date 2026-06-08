"""Scientific notation input dialog module.

Provides the ScientificInputDialog class for manual scientific notation input
of custom particle parameters (coefficient and exponent for mass, charge, and radius).

Provides the EditBodyDialog class for editing mass and charge parameters of
existing celestial bodies (no velocity input).
"""

import math
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

# ============================================================================
# Input field definition helpers
# ============================================================================

# Each field: (label, placeholder, allow_decimal, allow_negative)
# Index: 0=mass_coeff, 1=mass_exp, 2=charge_coeff, 3=charge_exp,
#        4=radius_coeff, 5=radius_exp
FIELD_DEFS: List[Tuple[str, str, bool, bool]] = [
    ("Mass coeff",    "1.0", True,  True),
    ("Mass exp",      "26",  False, True),
    ("Charge coeff",  "0.0", True,  True),
    ("Charge exp",    "0",   False, True),
    ("Radius coeff",  "6.4", True,  False),
    ("Radius exp",    "3",   False, False),
]

# Row labels
ROW_LABELS: List[str] = ["Mass", "Charge", "Radius"]
ROW_UNITS: List[str] = ["kg", "C", "km"]

# Edit dialog field definitions (3 rows: Mass, Charge, Radius)
EDIT_FIELD_DEFS: List[Tuple[str, str, bool, bool]] = [
    ("Mass coeff",  "1.0", True,  True),
    ("Mass exp",    "0",   False, True),
    ("Charge coeff","0.0", True,  True),
    ("Charge exp",  "0",   False, True),
    ("Radius coeff","6.4", True,  False),
    ("Radius exp",  "3",   False, False),
]

EDIT_ROW_LABELS: List[str] = ["Mass", "Charge", "Radius"]
EDIT_ROW_UNITS: List[str] = ["kg", "C", "km"]


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
# Edit dialog — EditBodyDialog
# ============================================================================


class EditBodyDialog:
    """Edit body parameters dialog.

    3 rows (Mass, Charge, Radius), each row has a coefficient and exponent input field,
    except the last row (Radius) which has only one coefficient field, totaling 5 input fields.
    Supports keyboard input (digits, decimal point, minus sign, Backspace, Enter).
    Active input field shows white border + blinking cursor.
    Provides OK / Cancel buttons.

    handle_event returns:
        - {"mass": float, "charge": float, "radius": float}  — confirm
        - "CANCEL"                                             — cancel
        - None                                                 — event consumed, no action
    """

    # Layout constants
    PANEL_WIDTH: int = 340
    PANEL_HEIGHT: int = 235
    FIELD_HEIGHT: int = 24
    COEFF_WIDTH: int = 80
    EXP_WIDTH: int = 45
    BUTTON_WIDTH: int = 72
    BUTTON_HEIGHT: int = 28
    ROW_SPACING: int = 35
    ROW_START_OFFSET: int = -30
    BLINK_INTERVAL_MS: int = 500

    def __init__(self) -> None:
        """Initialize the edit dialog."""
        self.visible: bool = False
        self.active_field_index: int = -1  # -1 = no active field
        self.cursor_visible: bool = True

        # 5 input field data
        self.fields: List[Dict] = []
        for idx, (_, placeholder, allow_decimal, allow_negative) in enumerate(EDIT_FIELD_DEFS):
            coeff_field = idx in (0, 2, 4)
            width = self.COEFF_WIDTH if coeff_field else self.EXP_WIDTH
            self.fields.append({
                "rect": pygame.Rect(0, 0, width, self.FIELD_HEIGHT),
                "text": placeholder,
                "placeholder": placeholder,
                "allow_decimal": allow_decimal,
                "allow_negative": allow_negative,
            })

        # OK / Cancel buttons rect
        self.ok_rect: pygame.Rect = pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT)
        self.cancel_rect: pygame.Rect = pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT)

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
    # Layout computation
    # ------------------------------------------------------------------

    def _compute_layout(self) -> None:
        """Compute positions for all input fields and buttons."""
        cx = WINDOW_WIDTH // 2

        # Center vertical offset
        cy = WINDOW_HEIGHT // 2
        row_start_y = cy + self.ROW_START_OFFSET

        # Left side of each row: coefficient field position
        coeff_x = cx - 55
        # Each row exponent field position
        exp_x = cx + 60

        for row in range(3):
            coeff_idx = row * 2
            exp_idx = row * 2 + 1
            row_y = row_start_y + row * self.ROW_SPACING

            # Coefficient field
            cf = self.fields[coeff_idx]
            cf["rect"].x = coeff_x
            cf["rect"].y = row_y
            cf["rect"].centery = row_y + self.FIELD_HEIGHT // 2

            # Exponent field
            ef = self.fields[exp_idx]
            ef["rect"].x = exp_x
            ef["rect"].y = row_y
            ef["rect"].centery = row_y + self.FIELD_HEIGHT // 2

        # OK / Cancel button position
        btn_y = row_start_y + 3 * self.ROW_SPACING + 5
        self.ok_rect.x = cx - 80
        self.ok_rect.y = btn_y
        self.cancel_rect.x = cx + 8
        self.cancel_rect.y = btn_y

    # ------------------------------------------------------------------
    # Prefill values
    # ------------------------------------------------------------------

    def prefill(self, mass: float, charge: float, radius_meters: float = 7.0e8) -> None:
        """Prefill the current mass, charge, and radius values (radius: m -> km).

        Args:
            mass: Current mass (kg)
            charge: Current charge (C)
            radius_meters: Current radius (m), internally converted to km
        """
        mass_coeff, mass_exp = _float_to_components(mass)
        charge_coeff, charge_exp = _float_to_components(charge)

        self.fields[0]["text"] = mass_coeff
        self.fields[1]["text"] = mass_exp
        self.fields[2]["text"] = charge_coeff
        self.fields[3]["text"] = charge_exp
        # Radius: m -> km then split
        radius_km = radius_meters / 1000.0
        r_coeff, r_exp = _float_to_components(radius_km)
        self.fields[4]["text"] = r_coeff
        self.fields[5]["text"] = r_exp

    # ------------------------------------------------------------------
    # Field value reading
    # ------------------------------------------------------------------

    def _get_field_value(
        self, coeff_idx: int, exp_idx: int
    ) -> float:
        """Read coefficient and exponent and compute the value.

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

    def get_results(self) -> Dict[str, float]:
        """Read all input fields and compute the final parameters.

        Returns:
            {"mass": float (kg), "charge": float (C), "radius": float (m)}

        Note: Radius is converted from km to m (x1000).
        On parse failure, silently uses defaults (coefficient 1.0, exponent 0).
        """
        mass = self._get_field_value(0, 1)
        charge = self._get_field_value(2, 3)
        radius = self._get_field_value(4, 5) * 1000.0  # km -> m
        radius = max(1.0, min(radius, 1.0e12))
        return {"mass": mass, "charge": charge, "radius": radius}

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    def _is_valid_input(self, char: str, field_idx: int) -> bool:
        """Check if the input character is valid.

        Args:
            char: Input character
            field_idx: Input field index

        Returns:
            True if valid
        """
        field = self.fields[field_idx]
        allow_decimal = field["allow_decimal"]
        allow_negative = field["allow_negative"]

        if char in "0123456789":
            return True
        if char == "." and allow_decimal:
            return "." not in field["text"]
        if char == "-" and allow_negative:
            return field["text"] == ""
        return False

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(
        self, event: pygame.event.Event
    ) -> Optional[Union[str, Dict[str, float]]]:
        """Handle an event.

        Args:
            event: Pygame event

        Returns:
            - {"mass": float, "charge": float} — confirm
            - "CANCEL" — cancel
            - None — event consumed, no action
        """
        if not self.visible:
            return None

        # Mouse motion: update button hover state
        if event.type == pygame.MOUSEMOTION:
            self.ok_hovered = self.ok_rect.collidepoint(event.pos)
            self.cancel_hovered = self.cancel_rect.collidepoint(event.pos)
            return None

        # Mouse click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check input field click
            for i, field in enumerate(self.fields):
                if field["rect"].collidepoint(event.pos):
                    self.active_field_index = i
                    self.cursor_visible = True
                    return None

            # Check OK button
            if self.ok_rect.collidepoint(event.pos):
                return self.get_results()

            # Check Cancel button
            if self.cancel_rect.collidepoint(event.pos):
                return "CANCEL"

            # Ignore clicks outside the dialog
            return None

        # Keyboard input
        if event.type == pygame.KEYDOWN:
            # Esc = Cancel
            if event.key == pygame.K_ESCAPE:
                return "CANCEL"

            # Enter = OK
            if event.key == pygame.K_RETURN:
                return self.get_results()

            if self.active_field_index < 0:
                return None

            field = self.fields[self.active_field_index]

            # Backspace
            if event.key == pygame.K_BACKSPACE:
                field["text"] = field["text"][:-1]
                return None

            # Get key character
            if event.key == pygame.K_KP_MINUS:
                char = "-"
            elif event.key == pygame.K_KP_PERIOD:
                char = "."
            else:
                try:
                    char = event.unicode
                except Exception:
                    return None

            # Validate and append
            if char and self._is_valid_input(char, self.active_field_index):
                field["text"] += char

            return None

        return None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the dialog.

        Args:
            surface: Target Surface
        """
        if not self.visible:
            return

        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        pw = self.PANEL_WIDTH
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
        title = "Edit Body Parameters"
        title_surf = self._font_title.render(title, True, TEXT_HIGHLIGHT)
        tr = title_surf.get_rect(center=(cx, py + 18))
        surface.blit(title_surf, tr)

        # Cursor blink
        now = pygame.time.get_ticks()
        self.cursor_visible = (now // self.BLINK_INTERVAL_MS) % 2 == 0

        row_start_y = cy + self.ROW_START_OFFSET
        label_x = px + 15

        for row in range(3):
            row_y = row_start_y + row * self.ROW_SPACING
            coeff_idx = row * 2
            exp_idx = row * 2 + 1

            # Row label
            lbl_surf = self._font_label.render(EDIT_ROW_LABELS[row], True, LABEL_COLOR)
            surface.blit(lbl_surf, (label_x, row_y + 3))

            # Each row: coefficient + *10^ + exponent + unit
            self._draw_field(surface, self.fields[coeff_idx], coeff_idx == self.active_field_index, row_y)

            # *10^ label
            power_surf = self._font_small.render("*10^", True, LABEL_COLOR)
            power_rect = power_surf.get_rect(
                midleft=(self.fields[coeff_idx]["rect"].right + 4, row_y + self.FIELD_HEIGHT // 2)
            )
            surface.blit(power_surf, power_rect)

            # Exponent input field
            self._draw_field(surface, self.fields[exp_idx], exp_idx == self.active_field_index, row_y)

            # Unit
            unit_surf = self._font_small.render(EDIT_ROW_UNITS[row], True, LABEL_COLOR)
            unit_rect = unit_surf.get_rect(
                midleft=(self.fields[exp_idx]["rect"].right + 4, row_y + self.FIELD_HEIGHT // 2)
            )
            surface.blit(unit_surf, unit_rect)

        # OK / Cancel buttons
        self._draw_button(
            surface, self.ok_rect, "OK",
            BTN_OK_HOVER if self.ok_hovered else BTN_OK_COLOR,
        )
        self._draw_button(
            surface, self.cancel_rect, "Cancel",
            BTN_CANCEL_HOVER if self.cancel_hovered else BTN_CANCEL_COLOR,
        )

        # Bottom hint
        hint = "Esc to cancel  |  Enter to confirm"
        hint_surf = self._font_small.render(hint, True, HINT_COLOR)
        hr = hint_surf.get_rect(center=(cx, py + ph - 10))
        surface.blit(hint_surf, hr)

    def _draw_field(
        self,
        surface: pygame.Surface,
        field: Dict,
        is_active: bool,
        row_y: int,
    ) -> None:
        """Draw a single input field.

        Args:
            surface: Target Surface
            field: Input field data dict
            is_active: Whether the field is active
            row_y: Row vertical position (used for cursor positioning)
        """
        rect = field["rect"]

        # Background
        bg_color = FIELD_ACTIVE if is_active else FIELD_INACTIVE
        pygame.draw.rect(surface, bg_color, rect, border_radius=3)

        # Border
        border_color = FIELD_BORDER_ACTIVE if is_active else FIELD_BORDER_INACTIVE
        pygame.draw.rect(surface, border_color, rect, 1, border_radius=3)

        # Text or placeholder
        if field["text"]:
            text_surf = self._font_field.render(field["text"], True, TEXT_HIGHLIGHT)
        else:
            text_surf = self._font_field.render(field["placeholder"], True, PLACEHOLDER_COLOR)

        text_rect = text_surf.get_rect(midleft=(rect.x + 4, rect.centery))
        surface.blit(text_surf, text_rect)

        # Cursor blink (active state only)
        if is_active and self.cursor_visible:
            cursor_x = text_rect.right + 1
            cursor_y1 = rect.y + 3
            cursor_y2 = rect.bottom - 3
            pygame.draw.line(surface, CURSOR_COLOR, (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        text: str,
        color: Tuple[int, int, int],
    ) -> None:
        """Draw a button.

        Args:
            surface: Target Surface
            rect: Button position rectangle
            text: Button text
            color: Button color
        """
        # Background
        pygame.draw.rect(surface, color, rect, border_radius=4)
        pygame.draw.rect(surface, DIALOG_BORDER, rect, 1, border_radius=4)

        # Text
        text_surf = self._font_field.render(text, True, BTN_TEXT_COLOR)
        tr = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, tr)


# ============================================================================
# Custom particle input dialog — ScientificInputDialog (original implementation preserved)
# ============================================================================


class ScientificInputDialog:
    """Scientific notation input dialog.

    6 input fields: mass coeff/exponent, charge coeff/exponent, radius coeff/exponent.
    Supports keyboard input (digits, decimal point, minus sign, Backspace, Enter).
    Active input field shows white border + blinking cursor.
    Provides OK / Cancel buttons.

    handle_event returns:
        - {"mass": float, "charge": float, "radius": float}  — confirm
        - "CANCEL"                                             — cancel
        - None                                                 — event consumed, no action
    """

    # Layout constants
    PANEL_WIDTH: int = 340
    PANEL_HEIGHT: int = 275
    FIELD_HEIGHT: int = 24
    COEFF_WIDTH: int = 80
    EXP_WIDTH: int = 45
    BUTTON_WIDTH: int = 72
    BUTTON_HEIGHT: int = 28
    ROW_SPACING: int = 35
    ROW_START_OFFSET: int = -70
    BUTTON_Y_OFFSET: int = 115
    BLINK_INTERVAL_MS: int = 500

    def __init__(self) -> None:
        """Initialize the scientific notation input dialog."""
        self.visible: bool = False
        self.active_field_index: int = -1  # -1 = no active field
        self.cursor_visible: bool = True

        # 6 input field data
        self.fields: List[Dict] = []
        for idx, (_, placeholder, allow_decimal, allow_negative) in enumerate(FIELD_DEFS):
            coeff_field = idx in (0, 2, 4)
            width = self.COEFF_WIDTH if coeff_field else self.EXP_WIDTH
            self.fields.append({
                "rect": pygame.Rect(0, 0, width, self.FIELD_HEIGHT),
                "text": placeholder,
                "placeholder": placeholder,
                "allow_decimal": allow_decimal,
                "allow_negative": allow_negative,
            })

        # OK / Cancel buttons rect
        self.ok_rect: pygame.Rect = pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT)
        self.cancel_rect: pygame.Rect = pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT)

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
    # Layout computation
    # ------------------------------------------------------------------

    def _compute_layout(self) -> None:
        """Compute positions for all input fields and buttons."""
        cx = WINDOW_WIDTH // 2

        # Center vertical offset
        cy = WINDOW_HEIGHT // 2
        row_start_y = cy + self.ROW_START_OFFSET

        # Left side of each row: coefficient field position
        coeff_x = cx - 55
        # Each row exponent field position
        exp_x = cx + 60

        for row in range(3):
            coeff_idx = row * 2
            exp_idx = row * 2 + 1
            row_y = row_start_y + row * self.ROW_SPACING

            # Coefficient field
            cf = self.fields[coeff_idx]
            cf["rect"].x = coeff_x
            cf["rect"].y = row_y
            # Center the coefficient field relative to the label on the right
            cf["rect"].centery = row_y + self.FIELD_HEIGHT // 2

            # Exponent field
            ef = self.fields[exp_idx]
            ef["rect"].x = exp_x
            ef["rect"].y = row_y
            ef["rect"].centery = row_y + self.FIELD_HEIGHT // 2

        # OK / Cancel button position
        btn_y = row_start_y + 3 * self.ROW_SPACING + 10
        self.ok_rect.x = cx - 80
        self.ok_rect.y = btn_y
        self.cancel_rect.x = cx + 8
        self.cancel_rect.y = btn_y

    # ------------------------------------------------------------------
    # Field value reading
    # ------------------------------------------------------------------

    def _get_field_value(
        self, coeff_idx: int, exp_idx: int
    ) -> float:
        """Read coefficient and exponent and compute the value.

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
    # Prefill values
    # ------------------------------------------------------------------

    def prefill(self, mass: float) -> None:
        """Prefill the default radius value.

        Args:
            mass: Current mass (kg), unused (kept for parameter compatibility)
        """
        # Reset all fields to placeholder
        for i, field in enumerate(self.fields):
            field["text"] = field["placeholder"]

        # Use fixed default radius (m), convert to km for the dialog
        from src.config import CUSTOM_RADIUS_DEFAULT
        radius_km = CUSTOM_RADIUS_DEFAULT / 1000.0
        r_coeff, r_exp = _float_to_components(radius_km)
        self.fields[4]["text"] = r_coeff
        self.fields[5]["text"] = r_exp

    # ------------------------------------------------------------------
    # Field value reading
    # ------------------------------------------------------------------

    def get_results(self) -> Dict[str, float]:
        """Read all input fields and compute the final parameters.

        Returns:
            {"mass": float (kg), "charge": float (C), "radius": float (m)}

        Note: Radius is converted from km to m (x1000).
        On parse failure, silently uses defaults (coefficient 1.0, exponent 0).
        """
        mass = self._get_field_value(0, 1)
        charge = self._get_field_value(2, 3)
        radius = self._get_field_value(4, 5) * 1000.0  # km -> m
        return {"mass": mass, "charge": charge, "radius": radius}

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    def _is_valid_input(self, char: str, field_idx: int) -> bool:
        """Check if the input character is valid.

        Args:
            char: Input character
            field_idx: Input field index

        Returns:
            True if valid
        """
        field = self.fields[field_idx]
        allow_decimal = field["allow_decimal"]
        allow_negative = field["allow_negative"]

        if char in "0123456789":
            return True
        if char == "." and allow_decimal:
            # Check for existing decimal point
            return "." not in field["text"]
        if char == "-" and allow_negative:
            # Negative sign only allowed at the beginning
            return field["text"] == ""
        return False

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(
        self, event: pygame.event.Event
    ) -> Optional[Union[str, Dict[str, float]]]:
        """Handle an event.

        Args:
            event: Pygame event

        Returns:
            - {"mass": float, "charge": float, "radius": float} — confirm
            - "CANCEL" — cancel
            - None — event consumed, no action
        """
        if not self.visible:
            return None

        # Mouse motion: update button hover state
        if event.type == pygame.MOUSEMOTION:
            self.ok_hovered = self.ok_rect.collidepoint(event.pos)
            self.cancel_hovered = self.cancel_rect.collidepoint(event.pos)
            return None

        # Mouse click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check input field click
            for i, field in enumerate(self.fields):
                if field["rect"].collidepoint(event.pos):
                    self.active_field_index = i
                    self.cursor_visible = True
                    return None

            # Check OK button
            if self.ok_rect.collidepoint(event.pos):
                return self.get_results()

            # Check Cancel button
            if self.cancel_rect.collidepoint(event.pos):
                return "CANCEL"

            # Ignore clicks outside the dialog
            return None

        # Keyboard input
        if event.type == pygame.KEYDOWN:
            # Esc = Cancel
            if event.key == pygame.K_ESCAPE:
                return "CANCEL"

            # Enter = OK
            if event.key == pygame.K_RETURN:
                return self.get_results()

            if self.active_field_index < 0:
                return None

            field = self.fields[self.active_field_index]

            # Backspace
            if event.key == pygame.K_BACKSPACE:
                field["text"] = field["text"][:-1]
                return None

            # Get key character
            if event.key == pygame.K_KP_MINUS:
                char = "-"
            elif event.key == pygame.K_KP_PERIOD:
                char = "."
            else:
                try:
                    char = event.unicode
                except Exception:
                    return None

            # Validate and append
            if char and self._is_valid_input(char, self.active_field_index):
                field["text"] += char

            return None

        return None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the dialog.

        Args:
            surface: Target Surface
        """
        if not self.visible:
            return

        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        pw = self.PANEL_WIDTH
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
        title = "Custom Particle Config"
        title_surf = self._font_title.render(title, True, TEXT_HIGHLIGHT)
        tr = title_surf.get_rect(center=(cx, py + 18))
        surface.blit(title_surf, tr)

        # Cursor blink
        now = pygame.time.get_ticks()
        self.cursor_visible = (now // self.BLINK_INTERVAL_MS) % 2 == 0

        row_start_y = cy + self.ROW_START_OFFSET
        label_x = px + 15

        for row in range(3):
            row_y = row_start_y + row * self.ROW_SPACING
            coeff_idx = row * 2
            exp_idx = row * 2 + 1

            # Row label
            lbl_surf = self._font_label.render(ROW_LABELS[row], True, LABEL_COLOR)
            surface.blit(lbl_surf, (label_x, row_y + 3))

            # Each row: coefficient + *10^ + exponent + unit
            self._draw_field(surface, self.fields[coeff_idx], coeff_idx == self.active_field_index, row_y)

            # *10^ label
            power_surf = self._font_small.render("*10^", True, LABEL_COLOR)
            power_rect = power_surf.get_rect(
                midleft=(self.fields[coeff_idx]["rect"].right + 4, row_y + self.FIELD_HEIGHT // 2)
            )
            surface.blit(power_surf, power_rect)

            # Exponent input field
            self._draw_field(surface, self.fields[exp_idx], exp_idx == self.active_field_index, row_y)

            # Unit (to the right of the exponent field)
            unit_surf = self._font_small.render(ROW_UNITS[row], True, LABEL_COLOR)
            unit_rect = unit_surf.get_rect(
                midleft=(self.fields[exp_idx]["rect"].right + 4, row_y + self.FIELD_HEIGHT // 2)
            )
            surface.blit(unit_surf, unit_rect)

        # OK / Cancel buttons
        self._draw_button(
            surface, self.ok_rect, "OK",
            BTN_OK_HOVER if self.ok_hovered else BTN_OK_COLOR,
        )
        self._draw_button(
            surface, self.cancel_rect, "Cancel",
            BTN_CANCEL_HOVER if self.cancel_hovered else BTN_CANCEL_COLOR,
        )

        # Bottom hint
        hint = "Esc to cancel  |  Enter to confirm"
        hint_surf = self._font_small.render(hint, True, HINT_COLOR)
        hr = hint_surf.get_rect(center=(cx, py + ph - 10))
        surface.blit(hint_surf, hr)

    def _draw_field(
        self,
        surface: pygame.Surface,
        field: Dict,
        is_active: bool,
        row_y: int,
    ) -> None:
        """Draw a single input field.

        Args:
            surface: Target Surface
            field: Input field data dict
            is_active: Whether the field is active
            row_y: Row vertical position (used for cursor positioning)
        """
        rect = field["rect"]

        # Background
        bg_color = FIELD_ACTIVE if is_active else FIELD_INACTIVE
        pygame.draw.rect(surface, bg_color, rect, border_radius=3)

        # Border
        border_color = FIELD_BORDER_ACTIVE if is_active else FIELD_BORDER_INACTIVE
        pygame.draw.rect(surface, border_color, rect, 1, border_radius=3)

        # Text or placeholder
        if field["text"]:
            text_surf = self._font_field.render(field["text"], True, TEXT_HIGHLIGHT)
        else:
            text_surf = self._font_field.render(field["placeholder"], True, PLACEHOLDER_COLOR)

        text_rect = text_surf.get_rect(midleft=(rect.x + 4, rect.centery))
        surface.blit(text_surf, text_rect)

        # Cursor blink (active state only)
        if is_active and self.cursor_visible:
            cursor_x = text_rect.right + 1
            cursor_y1 = rect.y + 3
            cursor_y2 = rect.bottom - 3
            pygame.draw.line(surface, CURSOR_COLOR, (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        text: str,
        color: Tuple[int, int, int],
    ) -> None:
        """Draw a button.

        Args:
            surface: Target Surface
            rect: Button position rectangle
            text: Button text
            color: Button color
        """
        # Background
        pygame.draw.rect(surface, color, rect, border_radius=4)
        pygame.draw.rect(surface, DIALOG_BORDER, rect, 1, border_radius=4)

        # Text
        text_surf = self._font_field.render(text, True, BTN_TEXT_COLOR)
        tr = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, tr)
