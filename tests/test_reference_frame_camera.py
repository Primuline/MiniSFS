"""Reference-frame camera behavior tests."""

import pytest

from src.rendering.camera import Camera


def test_update_follow_with_zero_dt_does_not_feed_forward() -> None:
    """Paused reference-frame follow should converge to the current body position."""
    camera = Camera(width=800, height=600, world_scale=1.0)
    camera.follow(0.0, 0.0)

    camera.update_follow(
        target_x=100.0,
        target_y=-50.0,
        vel_x=25.0,
        vel_y=-10.0,
        dt=0.0,
        lerp_factor=1.0,
    )

    assert camera.center_x == pytest.approx(100.0)
    assert camera.center_y == pytest.approx(-50.0)


def test_update_follow_with_positive_dt_uses_velocity_feed_forward() -> None:
    """Active simulation follow may predict the target position within the frame."""
    camera = Camera(width=800, height=600, world_scale=1.0)
    camera.follow(0.0, 0.0)

    camera.update_follow(
        target_x=100.0,
        target_y=-50.0,
        vel_x=25.0,
        vel_y=-10.0,
        dt=2.0,
        lerp_factor=1.0,
    )

    assert camera.center_x == pytest.approx(150.0)
    assert camera.center_y == pytest.approx(-70.0)
