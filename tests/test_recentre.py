import math

import numpy as np

from bench_finder.core.pano_geometry import render_aimed_view
from bench_finder.recentre import BOX_SHARE, BOX_Y, frame_for_box


def test_frame_turns_towards_box_and_lands_it_low():
    # Box right of centre and below the horizon in a 60° view.
    box = {"x1": 500, "x2": 1000, "y1": 600, "y2": 700}
    yaw, tilt, fov = frame_for_box(box, 60.0)
    assert yaw > 0
    # Re-project the box centre into the new view: it sits at BOX_Y of the height.
    c, f = 511.5, 511.5 / math.tan(math.radians(30))
    below = math.atan((650 - c) / f) - math.radians(tilt)
    f2 = c / math.tan(math.radians(fov) / 2)
    assert abs((c + f2 * math.tan(below)) / 1023 - BOX_Y) < 0.01
    width = math.degrees(math.atan((1000 - c) / f) - math.atan((500 - c) / f))
    assert abs(width / fov - BOX_SHARE) < 0.01


def test_centred_box_needs_no_turn():
    yaw, _, _ = frame_for_box({"x1": 412, "x2": 612, "y1": 500, "y2": 600}, 60.0)
    assert abs(yaw) < 0.1


def test_tilt_moves_horizon_up():
    # Top half white (sky), bottom half black (ground).
    pano = np.zeros((200, 400, 3), np.uint8)
    pano[:100] = 255
    kw = {
        "center_compass_deg": 0.0,
        "aim_bearing_deg": 0.0,
        "fov_deg": 60.0,
        "out_size": 101,
    }
    level = render_aimed_view(pano, **kw)
    down = render_aimed_view(pano, **kw, tilt_deg=15.0)
    sky = lambda im: int((im[:, 50, 0] > 127).sum())  # noqa: E731
    assert abs(sky(level) - 50) <= 2
    assert sky(down) < sky(level) - 10
