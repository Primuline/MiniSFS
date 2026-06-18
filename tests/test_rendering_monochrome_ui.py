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


class ScaledCamera(StubCamera):
    """Camera stub using the real project world scale conversion."""

    world_scale: float = 8.0e5

    def __init__(self, zoom: float = 1.0) -> None:
        self.zoom = zoom

    def world_distance_to_screen(self, distance: float) -> float:
        """Convert world meters to pixels."""
        return float(distance) / self.world_scale * self.zoom


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


def test_probe_render_size_scales_with_radius() -> None:
    """Probe display size should grow when its stored radius grows."""
    renderer = Renderer(width=120, height=90)

    renderer.screen.fill((0, 0, 0))
    renderer._draw_probe(60, 45, side_length=1.0, vx=1.0, vy=0.0)
    small_pixels = pygame.surfarray.array3d(renderer.screen)
    small_count = np.count_nonzero(small_pixels)

    renderer.screen.fill((0, 0, 0))
    renderer._draw_probe(60, 45, side_length=8.0, vx=1.0, vy=0.0)
    large_pixels = pygame.surfarray.array3d(renderer.screen)
    large_count = np.count_nonzero(large_pixels)

    assert large_count > small_count


def test_probe_visual_radius_floor_is_one_meter() -> None:
    """Probe visual radius should only clamp below the 1 m physical floor."""
    renderer = Renderer(width=120, height=90)
    camera = ScaledCamera()

    tiny = renderer._probe_screen_radius(0.1, camera)
    floor = renderer._probe_screen_radius(1.0, camera)
    larger = renderer._probe_screen_radius(2.0, camera)

    assert tiny == pytest.approx(floor)
    assert larger > floor


def test_probe_visual_radius_varies_below_one_thousand_kilometers() -> None:
    """Sub-1000 km probes should not collapse to the same display size."""
    renderer = Renderer(width=120, height=90)
    camera = ScaledCamera()

    one_meter = renderer._probe_screen_radius(1.0, camera)
    one_kilometer = renderer._probe_screen_radius(1_000.0, camera)
    one_hundred_kilometers = renderer._probe_screen_radius(100_000.0, camera)
    below_one_thousand_kilometers = renderer._probe_screen_radius(999_000.0, camera)

    assert one_meter < one_kilometer
    assert one_kilometer < one_hundred_kilometers
    assert one_hundred_kilometers < below_one_thousand_kilometers


def test_rendered_probe_size_varies_below_one_thousand_kilometers() -> None:
    """Rendered probe pixels should reflect sub-1000 km radius changes."""
    renderer = Renderer(width=120, height=90)

    def rendered_size(radius_world: float) -> Tuple[int, int]:
        renderer.screen.fill((0, 0, 0))
        screen_radius = renderer._probe_screen_radius(radius_world, ScaledCamera())
        renderer._draw_probe(60, 45, screen_radius, vx=1.0, vy=0.0)
        pixels = pygame.surfarray.array3d(renderer.screen)
        filled = pixels.sum(axis=2) > 0
        xs, ys = filled.nonzero()
        return (int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))

    one_hundred_meters = rendered_size(100.0)
    one_hundred_kilometers = rendered_size(100_000.0)
    below_one_thousand_kilometers = rendered_size(999_000.0)

    assert one_hundred_meters < one_hundred_kilometers
    assert one_hundred_kilometers < below_one_thousand_kilometers


def test_small_probe_preview_uses_world_scale() -> None:
    """A 0.1 km probe should not render larger than an Earth-sized planet."""
    renderer = Renderer(width=120, height=90)
    camera = ScaledCamera()

    probe_radius = renderer._probe_screen_radius(100.0, camera)
    planet_radius = camera.world_distance_to_screen(6.371e6)

    assert probe_radius < planet_radius


def test_probe_placement_preview_draws_triangle() -> None:
    """Probe placement preview should render a triangle instead of a circle."""
    renderer = Renderer(width=120, height=90)
    camera = StubCamera()

    renderer.draw_placement_preview(
        60.0,
        45.0,
        radius_world=8.0,
        camera=camera,
        surface=renderer.screen,
        body_type=BODY_TYPE_PROBE,
    )

    pixels = pygame.surfarray.array3d(renderer.screen)
    assert np.count_nonzero(pixels) > 0


def test_renderer_state_label_is_shifted_right_of_toolbar() -> None:
    """The bottom State label should not overlap the left toolbar."""
    renderer = Renderer(width=240, height=180)

    renderer.render_hud("PLAYING")

    toolbar_pixels = pygame.surfarray.array3d(renderer.screen)[:44, 150:180]
    state_area_pixels = pygame.surfarray.array3d(renderer.screen)[56:130, 150:180]
    assert np.count_nonzero(state_area_pixels) > np.count_nonzero(toolbar_pixels)
