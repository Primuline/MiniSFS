"""Startup mode menu tests."""

import os

import pytest

from src.rendering.hud import HUDManager


@pytest.fixture()
def pygame_dummy() -> None:
    """Initialize Pygame with dummy video driver."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame

    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def test_mode_menu_sandbox_button_starts_sandbox(pygame_dummy) -> None:
    """Clicking Sandbox Mode should emit the sandbox start command."""
    import pygame

    hud = HUDManager()
    sandbox_button = hud.mode_menu_buttons[1]
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": sandbox_button.rect.center, "button": 1},
    )

    assert hud.handle_mode_menu_event(event) == "START_SANDBOX"


def test_mode_menu_level_button_opens_level_select(pygame_dummy) -> None:
    """Clicking Level Mode should emit the level mode command."""
    import pygame

    hud = HUDManager()
    level_button = hud.mode_menu_buttons[0]
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": level_button.rect.center, "button": 1},
    )

    assert level_button.disabled is False
    assert hud.handle_mode_menu_event(event) == "LEVEL_MODE"


def test_level_select_has_two_by_four_grid_with_only_level_1_enabled(pygame_dummy) -> None:
    """Level selection exposes 8 slots, with Level 1 playable for now."""
    hud = HUDManager()

    assert len(hud.level_select_buttons) == 8
    assert hud.level_select_buttons[0].text == "Level 1"
    assert hud.level_select_buttons[0].disabled is False
    assert all(btn.disabled for btn in hud.level_select_buttons[1:])


def test_level_select_level_1_button_starts_level(pygame_dummy) -> None:
    """Clicking Level 1 should emit the start command."""
    import pygame

    hud = HUDManager()
    level_1_button = hud.level_select_buttons[0]
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": level_1_button.rect.center, "button": 1},
    )

    assert hud.handle_level_select_event(event) == "START_LEVEL_1"


def test_time_controls_include_pause_and_three_speed_buttons(pygame_dummy) -> None:
    """HUD should expose pause plus slow/reset/fast controls."""
    hud = HUDManager()

    assert [btn.action for btn in hud.time_buttons] == [
        "PLAY_PAUSE",
        "SLOW_HALF",
        "TIME_1X",
        "FAST_DOUBLE",
    ]
    hud.set_play_pause_state(False)
    assert hud.time_buttons[0].text == "||"
    hud.set_play_pause_state(True)
    assert hud.time_buttons[0].text == ">"


def test_mode_menu_draws_without_error(pygame_dummy) -> None:
    """Drawing the startup menu should work in headless Pygame."""
    import pygame

    hud = HUDManager()
    surface = pygame.Surface((hud.width, hud.height))

    hud.draw_mode_menu(surface)
    hud.draw_level_select(surface)
