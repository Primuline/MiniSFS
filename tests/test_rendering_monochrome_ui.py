"""Regression tests for the monochrome rendering UI."""

import os
from typing import Tuple

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from src.config import (
    BODY_TYPE_CHARGED,
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_STAR,
    get_ui_font,
)
from src.core.types import (
    BODY_TYPE,
    CHARGE,
    IS_ACTIVE,
    MASS,
    NUM_FIELDS,
    RADIUS,
    VX,
    VY,
    X,
    Y,
)
from src.rendering.effects import StarField
from src.rendering.renderer import Renderer


class StubCamera:
    """Minimal camera for renderer unit tests."""

    width: int = 240
    height: int = 180
    zoom: float = 1.0
    world_scale: float = 1.0

    def world_to_screen(self, wx: float, wy: float) -> Tuple[int, int]:
        """Map test world coordinates directly into screen space."""
        return (int(wx), int(wy))

    def world_distance_to_screen(self, distance: float) -> float:
        """Map test world distances directly into screen pixels."""
        return float(distance)

    def get_screen_rect_world(self) -> Tuple[float, float, float, float]:
        """Return the visible world rectangle."""
        return (0.0, 0.0, float(self.width), float(self.height))


def setup_module() -> None:
    """Initialize pygame for headless rendering tests."""
    pygame.init()
    pygame.font.init()


def teardown_module() -> None:
    """Shut down pygame after headless rendering tests."""
    pygame.quit()


def test_ui_font_helper_loads_with_fallback() -> None:
    """The project font helper should always return a usable font."""
    font = get_ui_font(16)

    assert isinstance(font, pygame.font.Font)
    assert font.size("MiniSFS")[0] > 0


def test_starfield_render_is_noop() -> None:
    """The monochrome style removes the old starfield background."""
    surface = pygame.Surface((64, 64))
    surface.fill((0, 0, 0))
    StarField(num_stars_far=10, num_stars_near=10, width=64, height=64).render(surface)

    pixels = pygame.surfarray.array3d(surface)
    assert np.count_nonzero(pixels) == 0


def test_renderer_draws_bodies_in_grayscale_only() -> None:
    """Body rendering should use black/white geometric shapes only."""
    renderer = Renderer(width=240, height=180)
    camera = StubCamera()
    bodies = np.zeros((4, NUM_FIELDS), dtype=np.float64)
    bodies[:, IS_ACTIVE] = 1.0
    bodies[:, MASS] = 1.0

    bodies[0, [X, Y, RADIUS, BODY_TYPE]] = [45.0, 50.0, 18.0, BODY_TYPE_STAR]
    bodies[1, [X, Y, RADIUS, BODY_TYPE]] = [100.0, 50.0, 12.0, BODY_TYPE_PLANET]
    bodies[2, [X, Y, RADIUS, BODY_TYPE, VX, VY]] = [
        150.0, 50.0, 3.0, BODY_TYPE_PROBE, 1.0, 0.0,
    ]
    bodies[3, [X, Y, RADIUS, BODY_TYPE, CHARGE]] = [
        200.0, 50.0, 10.0, BODY_TYPE_CHARGED, -1.0,
    ]

    renderer.render(bodies, {}, camera)

    pixels = pygame.surfarray.array3d(renderer.screen)
    non_black = pixels[np.any(pixels != 0, axis=2)]
    assert non_black.size > 0
    assert np.all(non_black[:, 0] == non_black[:, 1])
    assert np.all(non_black[:, 1] == non_black[:, 2])


def test_renderer_detects_landed_probe_normal() -> None:
    """Renderer should orient a resting probe away from the host center."""
    renderer = Renderer(width=240, height=180)
    bodies = np.zeros((2, NUM_FIELDS), dtype=np.float64)
    bodies[:, IS_ACTIVE] = 1.0
    bodies[:, MASS] = 1.0
    bodies[0, [X, Y, RADIUS, BODY_TYPE]] = [0.0, 0.0, 10.0, BODY_TYPE_PLANET]
    bodies[1, [X, Y, RADIUS, BODY_TYPE, VX, VY]] = [
        15.0, 0.0, 5.0, BODY_TYPE_PROBE, 0.0, 0.0,
    ]

    assert renderer._probe_landing_normal(bodies, 1) == (1.0, 0.0)


def test_landed_probe_normal_ignores_absolute_host_velocity() -> None:
    """A probe resting on a moving host should still orient away from the host."""
    renderer = Renderer(width=240, height=180)
    bodies = np.zeros((2, NUM_FIELDS), dtype=np.float64)
    bodies[:, IS_ACTIVE] = 1.0
    bodies[:, MASS] = 1.0
    bodies[0, [X, Y, RADIUS, BODY_TYPE, VX, VY]] = [
        0.0, 0.0, 10.0, BODY_TYPE_PLANET, 100.0, -50.0,
    ]
    bodies[1, [X, Y, RADIUS, BODY_TYPE, VX, VY]] = [
        15.0, 0.0, 5.0, BODY_TYPE_PROBE, 100.0, -50.0,
    ]

    assert renderer._probe_landing_normal(bodies, 1) == (1.0, 0.0)


def test_probe_direction_uses_relative_velocity_input() -> None:
    """Probe nose direction should follow the velocity supplied by the caller."""
    renderer = Renderer(width=240, height=180)

    assert renderer._probe_direction_angle(0.0, -10.0) == pytest.approx(-np.pi / 2)


def test_probe_direction_landing_normal_overrides_velocity() -> None:
    """Landed probes should point away from the host even if moving with it."""
    renderer = Renderer(width=240, height=180)

    assert renderer._probe_direction_angle(100.0, -50.0, (1.0, 0.0)) == pytest.approx(0.0)


def test_renderer_state_label_is_shifted_right_of_toolbar() -> None:
    """The bottom State label should not overlap the left toolbar."""
    renderer = Renderer(width=240, height=180)

    renderer.render_hud("PLAYING")

    toolbar_pixels = pygame.surfarray.array3d(renderer.screen)[:44, 150:180]
    state_area_pixels = pygame.surfarray.array3d(renderer.screen)[56:130, 150:180]
    assert np.count_nonzero(state_area_pixels) > np.count_nonzero(toolbar_pixels)
