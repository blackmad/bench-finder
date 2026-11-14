"""Aimed-view extraction: FOV formula, zoom choice, heading sign convention (task 2.2)."""

import itertools
import math

import numpy as np
import pytest

from bench_finder.core.pano_geometry import (
    FOV_MAX_DEG,
    FOV_MIN_DEG,
    apple_center_compass,
    choose_zoom,
    fov_for_distance,
    google_center_compass,
    render_aimed_view,
)


# ----------------------------------------------------------------------- FOV formula


@pytest.mark.parametrize(
    ("distance", "expected"),
    [
        (3.0, 90.0),  # 2*atan(1) = 90 exactly
        (2.0, 90.0),  # raw 112.6, clamped
        (4.0, math.degrees(2 * math.atan(3 / 4))),  # 73.74, unclamped
        (5.0, math.degrees(2 * math.atan(3 / 5))),  # 61.93, unclamped
        (6.0, math.degrees(2 * math.atan(3 / 6))),  # 53.13, unclamped
        (10.0, 40.0),  # raw 33.4, clamped
        (30.0, 40.0),
    ],
)
def test_fov_for_distance(distance, expected):
    assert fov_for_distance(distance) == pytest.approx(expected)


def test_fov_is_monotonic_and_clamped():
    fovs = [fov_for_distance(d) for d in range(1, 40)]
    assert all(a >= b for a, b in itertools.pairwise(fovs))
    assert min(fovs) >= FOV_MIN_DEG
    assert max(fovs) <= FOV_MAX_DEG


def test_choose_zoom_picks_lowest_sufficient_level():
    widths = [512, 1024, 2048, 4096, 8192, 16384]
    # 90 deg FOV at 1024 px needs 4096 px of panorama width.
    assert choose_zoom(widths, 90, tolerance=1.0) == 3
    # 40 deg needs 9216 -> only the top level reaches it at full tolerance.
    assert choose_zoom(widths, 40, tolerance=1.0) == 5
    # With the default tolerance 8192 is accepted (>= 0.85 * 9216).
    assert choose_zoom(widths, 40) == 4
    # Small panoramas fall back to the highest available level.
    assert choose_zoom([512, 1024], 40) == 1
    assert choose_zoom([], 40) == 0


# ------------------------------------------------- aimed-view rendering and signs

W, H = 2048, 1024


def stripe_equirect(stripe_compass, center_compass):
    """Black panorama with a white vertical stripe at a known compass bearing."""
    rel = (stripe_compass - center_compass + 180.0) % 360.0 - 180.0
    col = round((0.5 + rel / 360.0) * W) % W
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:, col - 3 : col + 4] = 255
    return img


def stripe_x(view):
    cols = np.where(view[view.shape[0] // 2, :, 0] > 128)[0]
    assert cols.size, "stripe not visible in view"
    return cols.mean()


@pytest.mark.parametrize("center", [0.0, 90.0, 200.0, 350.0])
def test_aimed_view_centres_target_bearing(center):
    stripe_at = 25.0
    view = render_aimed_view(
        stripe_equirect(stripe_at, center),
        center_compass_deg=center,
        aim_bearing_deg=stripe_at,
        fov_deg=60,
        out_size=256,
    )
    assert view.shape == (256, 256, 3)
    assert stripe_x(view) == pytest.approx(127.5, abs=2.0)


def test_aimed_view_sign_convention():
    """Camera turned left of the target (smaller bearing) sees it on the right."""
    center = 120.0
    pano = stripe_equirect(150.0, center)
    left = render_aimed_view(
        pano, center_compass_deg=center, aim_bearing_deg=140.0, fov_deg=60, out_size=256
    )
    right = render_aimed_view(
        pano, center_compass_deg=center, aim_bearing_deg=160.0, fov_deg=60, out_size=256
    )
    assert stripe_x(left) > 128 + 20
    assert stripe_x(right) < 128 - 20


def test_aimed_view_offset_matches_fov_geometry():
    """A target 15 deg off-axis at fov 60 lands at f*tan(15 deg) pixels from centre."""
    center = 0.0
    view = render_aimed_view(
        stripe_equirect(15.0, center),
        center_compass_deg=center,
        aim_bearing_deg=0.0,
        fov_deg=60,
        out_size=512,
    )
    f = 255.5 / math.tan(math.radians(30))
    assert stripe_x(view) - 255.5 == pytest.approx(
        f * math.tan(math.radians(15)), abs=3.0
    )


def test_aimed_view_wraps_across_seam():
    center = 180.0  # image seam is due north
    view = render_aimed_view(
        stripe_equirect(2.0, center),
        center_compass_deg=center,
        aim_bearing_deg=358.0,
        fov_deg=60,
        out_size=256,
    )
    assert stripe_x(view) > 128  # target is clockwise (right) of the aim


def test_zero_tilt_is_a_no_op_and_tilt_moves_horizon():
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[: H // 2] = 200  # sky above the horizon
    flat = render_aimed_view(
        img, center_compass_deg=0, aim_bearing_deg=0, fov_deg=60, out_size=128
    )
    same = render_aimed_view(
        img,
        center_compass_deg=0,
        aim_bearing_deg=0,
        fov_deg=60,
        out_size=128,
        pitch_rad=0,
        roll_rad=0,
    )
    assert np.array_equal(flat, same)
    horizon_row = int(np.argmax(flat[:, 64, 0] < 100))
    assert abs(horizon_row - 64) <= 1
    tilted = render_aimed_view(
        img,
        center_compass_deg=0,
        aim_bearing_deg=0,
        fov_deg=60,
        out_size=128,
        pitch_rad=math.radians(5),
    )
    assert abs(int(np.argmax(tilted[:, 64, 0] < 100)) - horizon_row) > 3


def test_center_compass_helpers():
    # Google: image centre faces the pano heading.
    assert google_center_compass(math.radians(30)) == pytest.approx(30)
    assert google_center_compass(math.radians(-30)) == pytest.approx(330)
    assert google_center_compass(None) == 0.0
    # Apple: CCW travel heading -> CW, then the stitched image looks backwards.
    assert apple_center_compass(math.radians(90)) == pytest.approx((270 + 180) % 360)
    assert apple_center_compass(0.0) == pytest.approx(180)
