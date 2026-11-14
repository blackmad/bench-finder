"""Aimed views are written to disk for Google and Apple, and panoramas are not (2.2, 2.3).

Network and the Apple stitcher are mocked; the geometry and file writing are real.
"""

import asyncio
import io
import os
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from bench_finder.core import streetview
from bench_finder.core.pano_geometry import PanoCandidate
from bench_finder.core.streetview import StreetViewClient


W, H = 4096, 2048


def stripe_pano(stripe_compass, center_compass):
    rel = (stripe_compass - center_compass + 180.0) % 360.0 - 180.0
    col = round((0.5 + rel / 360.0) * W) % W
    arr = np.full((H, W, 3), 60, dtype=np.uint8)
    arr[:, col - 12 : col + 13] = 255
    return Image.fromarray(arr)


def stripe_columns(path):
    arr = np.asarray(Image.open(path).convert("L"))
    cols = np.where(arr[arr.shape[0] // 2] > 200)[0]
    assert cols.size
    return cols.mean(), arr.shape[1]


@pytest.fixture
def client(tmp_path):
    c = StreetViewClient(images_dir=str(tmp_path))
    c.indoor_filter = None
    return c


def candidate(raw, source):
    return PanoCandidate(
        pano_id="PANO1",
        lat=52.0,
        lon=4.0,
        distance_m=12.0,
        bearing_deg=77.0,
        source=source,
        year=2024,
        month=5,
        date_str="2024-05",
        raw=raw,
    )


def test_google_view_is_written_centred_and_pano_is_not_kept(
    client, tmp_path, monkeypatch
):
    # heading 40 deg => centre column faces compass 40. Bench is at bearing 77.
    pano = SimpleNamespace(
        id="PANO1",
        lat=52.0,
        lon=4.0,
        heading=np.radians(40.0),
        pitch=0.0,
        roll=0.0,
        date=None,
        elevation=None,
        build_id=None,
        coverage_type=None,
        face_filenames=None,
        image_sizes=[SimpleNamespace(x=w) for w in (512, 1024, 2048, 4096, 8192)],
    )
    requested = {}

    async def fake_download(self, p, zoom, session):
        requested["zoom"] = zoom
        return stripe_pano(77.0, 40.0)

    monkeypatch.setattr(StreetViewClient, "_download_google_pano", fake_download)
    result = asyncio.run(
        client._render_google(
            candidate(pano, "google"), "bench1", 52.0, 4.0, session=None
        )
    )

    assert result.success
    assert result.kind == "aimed"
    assert result.pano_id == "PANO1"
    assert result.camera_bearing_deg == 77.0
    assert result.camera_distance_m == 12.0
    assert result.fov_deg == pytest.approx(40.0)  # 12 m -> clamped to the 40 deg floor
    assert (result.width, result.height) == (1024, 1024)
    assert (
        requested["zoom"] == 4
    )  # 8192 px: 0.89 of the ideal 9216 for 40 deg, accepted
    mid, width = stripe_columns(result.filepath)
    assert abs(mid - (width - 1) / 2) < 3
    # Only the aimed view is on disk, no panorama file.
    assert os.listdir(tmp_path) == [os.path.basename(result.filepath)]


def test_google_view_is_cached_on_second_run(client, monkeypatch):
    pano = SimpleNamespace(
        id="PANO1",
        lat=52.0,
        lon=4.0,
        heading=0.0,
        pitch=None,
        roll=None,
        date=None,
        elevation=None,
        build_id=None,
        coverage_type=None,
        face_filenames=None,
        image_sizes=[SimpleNamespace(x=8192)],
    )
    calls = {"n": 0}

    async def fake_download(self, p, zoom, session):
        calls["n"] += 1
        return stripe_pano(77.0, 0.0)

    monkeypatch.setattr(StreetViewClient, "_download_google_pano", fake_download)
    cand = candidate(pano, "google")
    first = asyncio.run(client._render_google(cand, "b", 52.0, 4.0, None))
    second = asyncio.run(client._render_google(cand, "b", 52.0, 4.0, None))
    assert first.success
    assert second.success
    assert second.cached
    assert calls["n"] == 1


def test_apple_view_gets_a_real_file(client, tmp_path, monkeypatch):
    """Task 2.3: Apple candidates produce a file (previously filepath=None)."""
    travel_ccw = np.radians(90.0)  # travelling west => CW heading 270
    pano = SimpleNamespace(
        id=12345,
        lat=52.0,
        lon=4.0,
        heading=travel_ccw,
        pitch=0.0,
        roll=0.0,
        date=None,
        elevation=None,
        build_id=99,
        coverage_type=None,
        camera_metadata=[object()] * 6,
    )
    png = io.BytesIO()
    Image.new("RGB", (8, 8)).save(png, "PNG")

    async def fake_face(self, p, face, zoom):
        return png.getvalue()

    stitched = {}

    def fake_to_equirectangular(faces, camera_metadata):
        stitched["faces"] = len(faces)
        # Image centre looks backwards: compass (270 + 180) % 360 = 90.
        return stripe_pano(77.0, 90.0)

    monkeypatch.setattr(StreetViewClient, "_fetch_apple_face", fake_face)
    monkeypatch.setattr(
        streetview.lookaround, "to_equirectangular", fake_to_equirectangular
    )

    cand = candidate(pano, "apple")
    cand.pano_id = "12345"
    result = asyncio.run(client._render_apple(cand, "bench2", 52.0, 4.0, session=None))

    assert result.success
    assert stitched["faces"] == 6
    assert result.filepath is not None
    assert result.file_size > 0
    assert result.image_source == "apple_streetlevel"
    assert result.kind == "aimed"
    assert (result.width, result.height) == (1024, 1024)
    mid, width = stripe_columns(result.filepath)
    assert abs(mid - (width - 1) / 2) < 3
    assert os.listdir(tmp_path) == [os.path.basename(result.filepath)]


def test_indoor_view_is_dropped_and_not_saved(client, tmp_path, monkeypatch):
    pano = SimpleNamespace(
        id="PANO1",
        lat=52.0,
        lon=4.0,
        heading=0.0,
        pitch=0.0,
        roll=0.0,
        date=None,
        elevation=None,
        build_id=None,
        coverage_type=None,
        face_filenames=None,
        image_sizes=[SimpleNamespace(x=8192)],
    )

    async def fake_download(self, p, zoom, session):
        return stripe_pano(77.0, 0.0)

    monkeypatch.setattr(StreetViewClient, "_download_google_pano", fake_download)
    client.indoor_filter = SimpleNamespace(is_indoor=lambda img: (True, "bedroom", 0.9))
    result = asyncio.run(
        client._render_google(candidate(pano, "google"), "b", 52.0, 4.0, None)
    )
    assert not result.success
    assert "indoor" in result.error
    assert os.listdir(tmp_path) == []
