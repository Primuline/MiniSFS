"""Tests for probe rocket UI helpers."""

import os

import pytest

from src.rendering.input_dialog import ProbeInputDialog, validate_probe_parameters


@pytest.fixture()
def pygame_dummy() -> None:
    """Initialize Pygame with a dummy display."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame

    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def test_validate_probe_parameters_computes_dry_mass() -> None:
    """Valid probe settings should include dry mass."""
    result = validate_probe_parameters(
        total_mass=1.0e5,
        fuel_mass=7.0e4,
        exhaust_velocity=3.0e3,
        mass_flow_rate=50.0,
        radius=8.0e5,
    )

    assert result["dry_mass"] == pytest.approx(3.0e4)
    assert result["fuel_mass"] == pytest.approx(7.0e4)


def test_validate_probe_parameters_rejects_invalid_fuel() -> None:
    """Fuel mass must stay below total mass."""
    with pytest.raises(ValueError):
        validate_probe_parameters(
            total_mass=1.0e5,
            fuel_mass=1.0e5,
            exhaust_velocity=3.0e3,
            mass_flow_rate=50.0,
            radius=8.0e5,
        )


def test_probe_dialog_prefill_and_results(pygame_dummy) -> None:
    """Probe dialog should return validated defaults."""
    dialog = ProbeInputDialog()
    dialog.visible = True
    dialog.prefill()

    result = dialog.get_results()

    assert result["total_mass"] == pytest.approx(1.0e5)
    assert result["fuel_mass"] == pytest.approx(7.0e4)
    assert result["dry_mass"] == pytest.approx(3.0e4)


def test_hud_probe_fuel_panel_draws(pygame_dummy) -> None:
    """Fuel panel drawing should work in dummy video mode."""
    import pygame

    from src.rendering.hud import HUDManager

    surface = pygame.Surface((1280, 720))
    hud = HUDManager()
    hud.set_probe_fuel_info(
        fuel_mass=3.5e4,
        dry_mass=3.0e4,
        initial_fuel_mass=7.0e4,
    )

    hud.draw(surface)

    assert hud._probe_fuel_info is not None
    assert hud._probe_fuel_info["fuel_pct"] == pytest.approx(50.0)
