"""Tests for reference-frame trail display helpers."""

import numpy as np
import pytest

from src.config import BODY_TYPE_PLANET, BODY_TYPE_PROBE
from src.core.types import VX, VY, X, Y, make_body
from src.main import find_landed_probe_ids, transform_trails_to_reference_frame
from src.rendering.camera import Camera


def test_transform_trails_to_reference_frame_aligns_history_by_tail() -> None:
    """Trails are displayed relative to matching reference-body history frames."""
    bodies = make_body(
        x=30.0,
        y=5.0,
        vx=0.0,
        vy=0.0,
        mass=1.0,
        radius=1.0,
        body_type=BODY_TYPE_PLANET,
    ).reshape(1, -1)
    trails = {
        0: [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)],
        1: [(120.0, 10.0), (140.0, 20.0)],
    }

    transformed = transform_trails_to_reference_frame(trails, bodies, 0)

    assert np.allclose(transformed[1], [(140.0, 15.0), (150.0, 25.0)])
    assert np.allclose(transformed[0], [(30.0, 5.0), (30.0, 5.0), (30.0, 5.0)])


def test_transform_trails_to_reference_frame_returns_absolute_without_reference_trail() -> None:
    """Missing reference history leaves absolute trails unchanged."""
    bodies = make_body(
        x=30.0,
        y=5.0,
        vx=0.0,
        vy=0.0,
        mass=1.0,
        radius=1.0,
        body_type=BODY_TYPE_PLANET,
    ).reshape(1, -1)
    trails = {1: [(120.0, 10.0), (140.0, 20.0)]}

    assert transform_trails_to_reference_frame(trails, bodies, 0) is trails


def test_camera_follow_zero_dt_does_not_feed_forward_velocity() -> None:
    """Paused reference-frame follow should converge to current position only."""
    camera = Camera(width=800, height=600, world_scale=1.0)
    camera.follow(0.0, 0.0)

    camera.update_follow(
        100.0,
        50.0,
        vel_x=1000.0,
        vel_y=1000.0,
        dt=0.0,
        lerp_factor=1.0,
    )

    assert camera.center_x == pytest.approx(100.0)
    assert camera.center_y == pytest.approx(50.0)


def test_find_landed_probe_ids_detects_resting_probe() -> None:
    """A probe resting on a host surface should be excluded from trail recording."""
    host = make_body(
        x=0.0,
        y=0.0,
        vx=12.0,
        vy=-3.0,
        mass=1.0e24,
        radius=10.0,
        body_type=BODY_TYPE_PLANET,
    )
    probe = make_body(
        x=15.0,
        y=0.0,
        vx=12.0,
        vy=-3.0,
        mass=1.0,
        radius=5.0,
        body_type=BODY_TYPE_PROBE,
    )
    bodies = np.vstack([host, probe])

    assert find_landed_probe_ids(bodies) == {1}

    bodies[1, VX] += 10.0
    bodies[1, VY] += 10.0
    assert find_landed_probe_ids(bodies) == set()
