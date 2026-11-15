import json
import math

import cv2
import numpy as np
import pytest

from bench_finder.core.pano_geometry import fov_for_distance, render_aimed_view
from bench_finder.recut import (
    HIRES_PX,
    RecutJob,
    apple_zoom,
    google_zoom,
    job_from_row,
    output_path,
    pose_drift,
    render_params,
)


GOOGLE_WIDTHS = [512, 1024, 2048, 4096, 8192, 16384]


def _row(**over):
    row = {
        "id": 46563,
        "bench_candidate_id": 1,
        "filename": "aimed_2016846984_node_PANO_streetview.jpg",
        "filepath": "images/aimed_2016846984_node_PANO_streetview.jpg",
        "image_source": "STREETVIEW_STREETLEVEL",
        "kind": "aimed",
        "pano_id": "PANO",
        "camera_bearing_deg": 86.7,
        "camera_distance_m": 20.5,
        "fov_deg": 40.0,
        "panorama_lat": 40.79,
        "panorama_lng": -73.97,
        "panorama_metadata": json.dumps(
            {"panorama_heading": 3.64, "pitch": 0.0015, "roll": 6.2745}
        ),
    }
    row.update(over)
    return row


def test_job_from_google_row():
    job = job_from_row(_row())
    assert (job.source, job.pano_id, job.fov_deg, job.aim_bearing_deg) == (
        "google",
        "PANO",
        40.0,
        86.7,
    )
    assert (job.stored_heading, job.stored_pitch, job.stored_roll) == (
        3.64,
        0.0015,
        6.2745,
    )


def test_job_from_apple_row_with_int_pano_id():
    job = job_from_row(
        _row(image_source="APPLE_STREETLEVEL", pano_id=17312702962440616940)
    )
    assert job.source == "apple" and job.pano_id == "17312702962440616940"


def test_job_fov_falls_back_to_distance():
    job = job_from_row(_row(fov_deg=None, camera_distance_m=4.0))
    assert job.fov_deg == pytest.approx(fov_for_distance(4.0))


def test_job_filename_from_filepath_and_bad_metadata():
    job = job_from_row(_row(filename=None, panorama_metadata="{nope"))
    assert job.filename == "aimed_2016846984_node_PANO_streetview.jpg"
    assert job.stored_heading is None


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"kind": "legacy"}, "aimed"),
        ({"image_source": "STREETVIEW_API"}, "image_source"),
        ({"pano_id": None}, "pano_id"),
        ({"camera_bearing_deg": None}, "bearing"),
        ({"fov_deg": None, "camera_distance_m": None}, "fov"),
    ],
)
def test_job_rejects(over, reason):
    with pytest.raises(ValueError, match=reason):
        job_from_row(_row(**over))


def test_output_path_keeps_basename(tmp_path):
    job = job_from_row(_row(filename="sub/x.jpg"))
    assert output_path(tmp_path / "hires", job) == tmp_path / "hires" / "x.jpg"


def test_zoom_choice_for_hires():
    # 2048 px across 40 deg needs ~15.7k px of panorama: Google zoom 5.
    assert google_zoom(GOOGLE_WIDTHS, 40.0) == 5
    assert google_zoom(GOOGLE_WIDTHS, 90.0) == 4
    # The 1024 px originals used one level lower.
    assert google_zoom(GOOGLE_WIDTHS, 40.0, out_px=1024) == 4
    # Old panoramas without zoom 5 fall back to their best level.
    assert google_zoom(GOOGLE_WIDTHS[:5], 40.0) == 4
    # Look Around: zoom 0 is the highest resolution.
    assert apple_zoom(40.0) == 0
    assert apple_zoom(73.7) == 1
    assert apple_zoom(90.0) == 1
    assert apple_zoom(73.7, out_px=1024) == 3


def test_render_params_reproduce_original_call():
    job = job_from_row(_row())
    p = render_params(job, 3.64, 0.0015, 6.2745)
    assert p["center_compass_deg"] == pytest.approx(math.degrees(3.64))
    assert p["aim_bearing_deg"] == 86.7 and p["fov_deg"] == 40.0
    assert p["out_size"] == HIRES_PX
    assert p["roll_rad"] == pytest.approx(6.2745 - 2 * math.pi)  # wrapped like capture
    assert render_params(job, None, None, None)["pitch_rad"] == 0.0
    apple = job_from_row(_row(image_source="APPLE_STREETLEVEL"))
    # Apple heading is CCW travel direction; the equirect centre looks backwards.
    ap = render_params(apple, math.radians(90.0), 0.0, 0.0)
    assert ap["center_compass_deg"] == pytest.approx(90.0)


def test_pose_drift():
    job = job_from_row(_row())
    assert pose_drift(job, 3.64, 0.0015, 6.2745) == pytest.approx(0.0)
    assert pose_drift(job, 3.64, 0.0015, 6.2745 - 2 * math.pi) == pytest.approx(0.0)
    assert pose_drift(job, 3.70, 0.0015, 6.2745) == pytest.approx(0.06)
    unknown = RecutJob(1, 1, "google", "P", "x.jpg", 0.0, 60.0)
    assert pose_drift(unknown, 1.0, 0.0, 0.0) is None


def test_hires_render_matches_original_framing():
    """Same params at 2x size, downscaled, reproduce the 1x view."""
    rng = np.random.default_rng(0)
    small = rng.integers(0, 255, (64, 128, 3), dtype=np.uint8)
    equirect = cv2.resize(small, (4096, 2048), interpolation=cv2.INTER_CUBIC)
    job = job_from_row(_row(fov_deg=60.0, camera_bearing_deg=123.0))
    base = render_params(job, 1.0, 0.05, -0.03, out_px=256)
    hi = render_params(job, 1.0, 0.05, -0.03, out_px=512)
    v1 = render_aimed_view(equirect, **base).astype(float)
    v2 = render_aimed_view(equirect, **hi)
    down = cv2.resize(v2, (256, 256), interpolation=cv2.INTER_AREA).astype(float)
    assert np.abs(down - v1).mean() < 3.0
    # A 5 degree aim error would be clearly visible.
    off = render_params(job, 1.0 + math.radians(5), 0.05, -0.03, out_px=256)
    assert np.abs(render_aimed_view(equirect, **off).astype(float) - v1).mean() > 10
