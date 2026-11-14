"""Concurrency, retry and enumeration behaviour of the image fetch path (task 2.4).

Everything is mocked: no test here touches the network.
"""

import asyncio
import time

import aiohttp
import pytest
import requests
from sqlalchemy import func, select

from bench_finder.clients import overpass_client
from bench_finder.core import streetview
from bench_finder.core.pano_geometry import PanoCandidate
from bench_finder.core.streetview import StreetViewClient, with_retries
from bench_finder.generators.bench_generator import CandidateResult
from bench_finder.models.enums import DataSource
from bench_finder.models.streetview_models import (
    StreetViewBatchCaptureResult,
    StreetViewImageCaptureError,
    StreetViewImageCaptureSuccess,
)
from bench_finder.models.unified_models import Image, SearchBase
from bench_finder.services import image_download_service
from bench_finder.services.database import BenchDatabase
from bench_finder.services.image_download_service import ImageDownloadService


@pytest.fixture(autouse=True)
def no_blocking_sleep(monkeypatch):
    """Any time.sleep during these tests is a bug (the old code slept 60 s)."""

    def boom(seconds):
        raise AssertionError(f"blocking time.sleep({seconds}) called")

    monkeypatch.setattr(time, "sleep", boom)


def success(bench_id, pano_id, bearing, distance=10.0):
    return StreetViewImageCaptureSuccess(
        bench_id=bench_id,
        lat=52.0,
        lng=4.0,
        heading=round(bearing),
        filepath=f"/tmp/{pano_id}.jpg",
        filename=f"{pano_id}.jpg",
        file_size=1,
        width=1024,
        height=1024,
        image_source="streetview_streetlevel",
        panorama_lat=52.0,
        panorama_lng=4.0,
        pano_id=pano_id,
        pano_date="2024-05",
        camera_bearing_deg=bearing,
        camera_distance_m=distance,
        fov_deg=40.0,
        pitch_deg=0.0,
        kind="aimed",
    )


class FakeClient:
    """Stands in for StreetViewClient and records how many calls overlap."""

    def __init__(self):
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls = 0

    async def capture_bench_views_async(self, lat, lng, bench_id, session=None):
        self.calls += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.05)
        finally:
            self.in_flight -= 1
        captures = [success(bench_id, f"{bench_id}-p{i}", i * 90.0) for i in range(3)]
        return StreetViewBatchCaptureResult.from_capture_results(
            bench_id, lat, lng, captures
        )


@pytest.fixture
def service_factory(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'svc.db'}"
    fake = FakeClient()
    monkeypatch.setattr(image_download_service, "StreetViewClient", lambda: fake)
    monkeypatch.setattr(
        image_download_service, "BenchDatabase", lambda: BenchDatabase(db_url=db_url)
    )

    def make(**kw):
        service = ImageDownloadService(**kw)
        search_id = service.database.create_search(
            SearchBase(query="q", start_lat=52.0, start_lng=4.0, search_radius=100)
        )
        return service, fake, search_id

    return make


def candidates(n):
    return [
        CandidateResult(
            provider_id=f"{1000 + i}_node",
            lat=52.0 + i * 1e-4,
            lng=4.0,
            source=DataSource.OSM,
            external_id=str(1000 + i),
        )
        for i in range(n)
    ]


# --------------------------------------------------------- bounded concurrency


def test_batch_runs_concurrently_but_bounded(service_factory):
    service, fake, search_id = service_factory(concurrency=3)
    done = []
    results = service.process_candidates(
        [(search_id, c) for c in candidates(12)], on_done=done.append
    )

    assert fake.calls == 12
    assert fake.max_in_flight == 3  # bounded by the semaphore, and actually parallel
    assert all(r is not None and r.images_successful == 3 for r in results)
    assert sorted(done) == list(range(12))


def test_concurrency_one_is_serial(service_factory):
    service, fake, search_id = service_factory(concurrency=1)
    service.process_candidates([(search_id, c) for c in candidates(4)])
    assert fake.max_in_flight == 1


def test_one_failing_bench_does_not_stop_the_batch(service_factory):
    service, fake, search_id = service_factory(concurrency=2)
    original = fake.capture_bench_views_async

    async def flaky(lat, lng, bench_id, session=None):
        if bench_id == "1001_node":
            raise RuntimeError("boom")
        return await original(lat, lng, bench_id, session)

    fake.capture_bench_views_async = flaky
    results = service.process_candidates([(search_id, c) for c in candidates(3)])
    assert results[1] is None
    assert results[0].images_successful == 3
    assert results[2].images_successful == 3


def test_process_benches_returns_stats(service_factory):
    service, _fake, search_id = service_factory(concurrency=4)
    stats = service.process_benches(search_id, candidates(5))
    assert stats.benches_processed == 5
    assert stats.images_successful == 15


def test_aimed_rows_store_bearing_distance_pano_and_rerun_adds_nothing(service_factory):
    service, _fake, search_id = service_factory(concurrency=2)
    items = [(search_id, c) for c in candidates(2)]
    service.process_candidates(items)

    def count():
        with service.database.get_session() as session:
            return session.execute(select(func.count()).select_from(Image)).scalar_one()

    assert count() == 6
    with service.database.get_session() as session:
        row = session.query(Image).filter(Image.pano_id == "1000_node-p1").one()
        assert row.kind == "aimed"
        assert row.camera_bearing_deg == 90.0
        assert row.camera_distance_m == 10.0
        assert row.pano_date == "2024-05"
        assert row.fov_deg == 40.0

    service.process_candidates(items)  # idempotent: same (candidate, pano, kind)
    assert count() == 6


# ------------------------------------------------------------------------ retries


def test_with_retries_retries_then_succeeds(monkeypatch):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    attempts = {"n": 0}

    @with_retries(max_tries=4)
    async def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise aiohttp.ClientConnectionError("reset")
        return "ok"

    assert asyncio.run(flaky()) == "ok"
    assert attempts["n"] == 3
    assert len(sleeps) == 2  # slept via asyncio.sleep, never time.sleep


def test_with_retries_gives_up_after_max_tries(monkeypatch):
    async def fake_sleep(seconds):
        pass

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    attempts = {"n": 0}

    @with_retries(max_tries=3)
    async def always_fails():
        attempts["n"] += 1
        raise TimeoutError

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(always_fails())
    assert attempts["n"] == 3


def test_with_retries_does_not_retry_programming_errors():
    attempts = {"n": 0}

    @with_retries()
    async def bug():
        attempts["n"] += 1
        raise KeyError("x")

    with pytest.raises(KeyError):
        asyncio.run(bug())
    assert attempts["n"] == 1


def test_overpass_retries_transient_errors(monkeypatch):
    sleeps = []
    monkeypatch.setattr("backoff._sync.time.sleep", sleeps.append)
    calls = {"n": 0}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"elements": []}

    def fake_post(url, data=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.ConnectionError("down")
        return Resp()

    monkeypatch.setattr(overpass_client.requests, "post", fake_post)
    assert overpass_client.post_overpass_query("http://x", "q", 5) == {"elements": []}
    assert calls["n"] == 3
    assert len(sleeps) == 2


def test_overpass_does_not_retry_client_errors(monkeypatch):
    monkeypatch.setattr("backoff._sync.time.sleep", lambda s: None)
    calls = {"n": 0}

    def fake_post(url, data=None, timeout=None):
        calls["n"] += 1
        response = requests.Response()
        response.status_code = 400
        return response

    monkeypatch.setattr(overpass_client.requests, "post", fake_post)
    with pytest.raises(requests.exceptions.HTTPError):
        overpass_client.post_overpass_query("http://x", "q", 5)
    assert calls["n"] == 1


def test_overpass_retries_rate_limit(monkeypatch):
    monkeypatch.setattr("backoff._sync.time.sleep", lambda s: None)
    calls = {"n": 0}

    def fake_post(url, data=None, timeout=None):
        calls["n"] += 1
        response = requests.Response()
        response.status_code = 429
        return response

    monkeypatch.setattr(overpass_client.requests, "post", fake_post)
    with pytest.raises(requests.exceptions.HTTPError):
        overpass_client.post_overpass_query("http://x", "q", 5)
    assert calls["n"] == 4


# ------------------------------------------------- enumeration orchestration


def pano_cand(pano_id, bearing, source="google", **kw):
    return PanoCandidate(
        pano_id=pano_id,
        lat=52.0,
        lon=4.0,
        distance_m=kw.pop("distance_m", 12.0),
        bearing_deg=bearing,
        source=source,
        year=kw.pop("year", 2023),
        month=6,
        **kw,
    )


def make_client(tmp_path, google, apple):
    client = StreetViewClient(images_dir=str(tmp_path))
    calls = {"google_render": [], "apple_render": [], "apple_enum": 0}

    async def g_enum(lat, lng, session):
        return google, []

    async def a_enum(lat, lng, session):
        calls["apple_enum"] += 1
        return apple, []

    async def g_render(cand, bench_id, lat, lng, session):
        calls["google_render"].append(cand.pano_id)
        return success(bench_id, cand.pano_id, cand.bearing_deg, cand.distance_m)

    async def a_render(cand, bench_id, lat, lng, session):
        calls["apple_render"].append(cand.pano_id)
        return success(bench_id, cand.pano_id, cand.bearing_deg, cand.distance_m)

    client.enumerate_google_panoramas = g_enum
    client.enumerate_apple_panoramas = a_enum
    client._render_google = g_render
    client._render_apple = a_render
    return client, calls


def test_capture_applies_filters_and_selection(tmp_path):
    google = [pano_cand(f"g{i}", i * 40.0) for i in range(9)]  # 9 bearings, 6 sectors
    google.append(pano_cand("too_close", 5.0, distance_m=2.0))
    google.append(pano_cand("third", 6.0, is_third_party=True))
    client, calls = make_client(tmp_path, google, [])
    result = asyncio.run(
        client.capture_bench_views_async(52.0, 4.0, "b1", session=object())
    )
    assert len(calls["google_render"]) == 6
    assert "too_close" not in calls["google_render"]
    assert "third" not in calls["google_render"]
    assert result.successful_images == 6
    assert calls["apple_enum"] == 0  # enough Google views: Apple not consulted


def test_apple_fallback_only_when_google_is_thin(tmp_path):
    google = [pano_cand("g0", 0), pano_cand("g1", 120)]
    apple = [pano_cand(f"a{i}", i * 90.0, source="apple") for i in range(4)]
    client, calls = make_client(tmp_path, google, apple)
    result = asyncio.run(
        client.capture_bench_views_async(52.0, 4.0, "b1", session=object())
    )
    assert calls["apple_enum"] == 1
    assert 1 <= len(calls["apple_render"]) <= 2
    assert result.successful_images == 2 + len(calls["apple_render"])


def test_apple_only_bench_gets_views(tmp_path):
    apple = [pano_cand(f"a{i}", i * 100.0, source="apple") for i in range(3)]
    client, calls = make_client(tmp_path, [], apple)
    result = asyncio.run(
        client.capture_bench_views_async(52.0, 4.0, "b1", session=object())
    )
    assert result.successful_images == 2  # capped at APPLE_MAX_VIEWS
    assert calls["google_render"] == []


def test_no_coverage_yields_one_error_row(tmp_path):
    client, _calls = make_client(tmp_path, [], [])
    result = asyncio.run(
        client.capture_bench_views_async(52.0, 4.0, "b1", session=object())
    )
    assert result.total_images == 1
    assert result.successful_images == 0
    assert isinstance(result.captures[0], StreetViewImageCaptureError)
    assert "no usable panorama" in result.captures[0].error


def test_tiles_around_covers_bench_near_tile_edge():
    import math

    def tile_corner(x, y, z=17):
        n = 2**z
        lng = x / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        return lat, lng

    # Mid-tile: one tile. On a tile corner: all four neighbours are needed.
    lat0, lng0 = tile_corner(67000.5, 43000.5)
    assert len(streetview._tiles_around(lat0, lng0)) == 1
    lat1, lng1 = tile_corner(67000, 43000)
    assert len(streetview._tiles_around(lat1, lng1)) == 4
