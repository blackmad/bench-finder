"""
Aimed bench views from Google Street View and Apple Look Around panoramas.

For each bench we enumerate every panorama within 30 m, keep up to six that look at
the bench from different bearing sectors, fetch only the panorama resolution the
output needs, cut a 1024 px rectilinear view aimed at the bench, and throw the
panorama away. Only the aimed views are written to disk.

All panorama traffic goes through the ``streetlevel`` library (free). The paid Google
Street View Static *image* API is never called. The Street View *metadata* endpoint
(``get_street_view_metadata``) is free and kept for availability checks.

Geometry and selection rules live in :mod:`bench_finder.core.pano_geometry` so they
can be tested without a network.
"""

import asyncio
import io
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp
import backoff
import numpy as np
import requests
from aiohttp import ClientSession
from PIL import Image as PILImage


# Panoramas can be 16384x8192; the default PIL limit is ~89 MP.
PILImage.MAX_IMAGE_PIXELS = 300_000_000

from streetlevel import lookaround  # noqa: E402
from streetlevel import streetview as sl_streetview  # noqa: E402

from bench_finder.config import GOOGLE_MAPS_API_KEY, IMAGES_DIR  # noqa: E402
from bench_finder.core.indoor import IndoorFilter  # noqa: E402
from bench_finder.core.pano_geometry import (  # noqa: E402
    MAX_PANO_DISTANCE_M,
    MIN_PANO_DISTANCE_M,
    OUTPUT_SIZE_PX,
    PanoCandidate,
    apple_center_compass,
    bearing_deg,
    ccw_to_cw_heading,
    choose_zoom,
    filter_candidates,
    fov_for_distance,
    google_center_compass,
    haversine_m,
    render_aimed_view,
    select_views,
)
from bench_finder.models.enums import ImageKind, ImageSource  # noqa: E402
from bench_finder.models.streetview_models import (  # noqa: E402
    PanoramaMetadata,
    StreetViewBatchCaptureResult,
    StreetViewCleanupResult,
    StreetViewImageCapture,
    StreetViewImageCaptureError,
    StreetViewImageCaptureSuccess,
    StreetViewLocation,
    StreetViewMetadata,
    StreetViewMetadataResponse,
)


logger = logging.getLogger(__name__)

# Concurrency limits shared by every bench processed through one client.
NETWORK_CONCURRENCY = 8  # simultaneous metadata / tile requests
PANO_IMAGE_CONCURRENCY = 3  # panoramas held in memory at once
APPLE_STITCH_CONCURRENCY = 1  # torch reprojection is CPU heavy
MAX_METADATA_FETCHES_PER_BENCH = 24
# Try Apple Look Around when Google gave fewer successful views than this.
APPLE_FALLBACK_BELOW = 3
APPLE_MAX_VIEWS = 2
APPLE_ZOOM = 2
JPEG_QUALITY = 90

RETRYABLE_ERRORS = (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError)


def with_retries(max_tries: int = 4):
    """Decorator: async exponential backoff (``asyncio.sleep``, never blocking)."""
    return backoff.on_exception(
        backoff.expo,
        RETRYABLE_ERRORS,
        max_tries=max_tries,
        max_time=90,
        jitter=backoff.full_jitter,
        logger=logger,
    )


def _wrap_angle(rad: float | None) -> float:
    """Wrap an angle to (-pi, pi]; None -> 0."""
    if rad is None:
        return 0.0
    return (rad + math.pi) % (2 * math.pi) - math.pi


def _tiles_around(
    lat: float, lng: float, radius_m: float = MAX_PANO_DISTANCE_M
) -> list[tuple[int, int]]:
    """Zoom-17 coverage tiles that overlap a circle of ``radius_m`` around a point."""
    dlat = radius_m / 111_320.0
    dlng = radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))
    tiles = {
        tuple(sl_streetview.wgs84_to_tile_coord(la, lo, 17))
        for la in (lat - dlat, lat + dlat)
        for lo in (lng - dlng, lng + dlng)
    }
    return sorted(tiles)  # type: ignore[arg-type]


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value))


@dataclass
class _LoopState:
    """Per-event-loop caches and semaphores (created lazily inside the loop)."""

    network: asyncio.Semaphore
    pano_images: asyncio.Semaphore
    apple_stitch: asyncio.Semaphore
    tiles: dict[tuple[str, int, int], asyncio.Future] = field(default_factory=dict)
    metas: dict[str, asyncio.Future] = field(default_factory=dict)


class StreetViewClient:
    """Captures aimed bench views from panoramas (Google Street View, Apple Look Around)."""

    def __init__(self, images_dir: str | None = None) -> None:
        self.api_key = GOOGLE_MAPS_API_KEY  # only used by the free metadata endpoint
        self.images_dir = images_dir or IMAGES_DIR
        os.makedirs(self.images_dir, exist_ok=True)
        self.indoor_filter: IndoorFilter | None = IndoorFilter()
        self._state: _LoopState | None = None
        self._state_loop: asyncio.AbstractEventLoop | None = None
        self._apple_auth: Any = None

    # ------------------------------------------------------------------ helpers

    def _get_state(self) -> _LoopState:
        loop = asyncio.get_running_loop()
        if self._state is None or self._state_loop is not loop:
            self._state = _LoopState(
                network=asyncio.Semaphore(NETWORK_CONCURRENCY),
                pano_images=asyncio.Semaphore(PANO_IMAGE_CONCURRENCY),
                apple_stitch=asyncio.Semaphore(APPLE_STITCH_CONCURRENCY),
            )
            self._state_loop = loop
        return self._state

    def _calculate_bearing(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Bearing from point 1 to point 2, degrees clockwise from north."""
        return bearing_deg(lat1, lon1, lat2, lon2)

    def _ccw_to_cw_heading(self, ccw_heading_deg: float) -> float:
        """Convert a heading measured counter-clockwise from north to clockwise."""
        return ccw_to_cw_heading(ccw_heading_deg)

    def _view_filename(self, bench_id: str, pano_id: str, suffix: str) -> str:
        return f"aimed_{_safe_name(bench_id)}_{_safe_name(pano_id)}_{suffix}.jpg"

    # -------------------------------------------------------- Google enumeration

    @with_retries()
    async def _fetch_google_tile(self, x: int, y: int, session: ClientSession) -> list:
        async with self._get_state().network:
            return await sl_streetview.get_coverage_tile_async(x, y, session)

    @with_retries()
    async def _fetch_google_meta(self, pano_id: str, session: ClientSession) -> Any:
        async with self._get_state().network:
            return await sl_streetview.find_panorama_by_id_async(pano_id, session)

    async def _google_tile(self, x: int, y: int, session: ClientSession) -> list:
        state = self._get_state()
        if (("g", x, y)) not in state.tiles:
            state.tiles[("g", x, y)] = asyncio.ensure_future(
                self._fetch_google_tile(x, y, session)
            )
        return await asyncio.shield(state.tiles[("g", x, y)])

    async def _google_meta(self, pano_id: str, session: ClientSession) -> Any:
        state = self._get_state()
        if pano_id not in state.metas:
            state.metas[pano_id] = asyncio.ensure_future(
                self._fetch_google_meta(pano_id, session)
            )
        return await asyncio.shield(state.metas[pano_id])

    async def enumerate_google_panoramas(
        self, lat: float, lng: float, session: ClientSession
    ) -> tuple[list[PanoCandidate], list[str]]:
        """All official Google panoramas 4-30 m from the point, with dates and tilt.

        Returns (candidates, errors). Free: coverage tiles plus per-pano metadata.
        """
        errors: list[str] = []
        tile_results = await asyncio.gather(
            *[self._google_tile(x, y, session) for x, y in _tiles_around(lat, lng)],
            return_exceptions=True,
        )
        near: dict[str, float] = {}
        for res in tile_results:
            if isinstance(res, BaseException):
                errors.append(f"coverage tile: {res}")
                continue
            for p in res:
                if (
                    p.lat is None
                    or p.lon is None
                    or sl_streetview.is_third_party_panoid(p.id)
                ):
                    continue
                d = haversine_m(p.lat, p.lon, lat, lng)
                if MIN_PANO_DISTANCE_M <= d <= MAX_PANO_DISTANCE_M:
                    near[p.id] = d
        ids = sorted(near, key=near.__getitem__)[:MAX_METADATA_FETCHES_PER_BENCH]

        metas = await asyncio.gather(
            *[self._google_meta(i, session) for i in ids], return_exceptions=True
        )
        cands: list[PanoCandidate] = []
        for pano_id, meta in zip(ids, metas, strict=True):
            if isinstance(meta, BaseException):
                errors.append(f"pano metadata {pano_id}: {meta}")
                continue
            if meta is None:
                continue
            date = meta.date
            year = getattr(date, "year", None)
            month = getattr(date, "month", None)
            cands.append(
                PanoCandidate(
                    pano_id=meta.id,
                    lat=meta.lat,
                    lon=meta.lon,
                    distance_m=haversine_m(meta.lat, meta.lon, lat, lng),
                    bearing_deg=bearing_deg(meta.lat, meta.lon, lat, lng),
                    source="google",
                    year=year,
                    month=month,
                    date_str=str(date) if date else None,
                    is_third_party=bool(meta.is_third_party),
                    is_indoor_meta=meta.building_level is not None
                    or bool(meta.building_levels),
                    raw=meta,
                )
            )
        return cands, errors

    # --------------------------------------------------------- Apple enumeration

    @with_retries()
    async def _fetch_apple_tile(self, x: int, y: int, session: ClientSession) -> Any:
        async with self._get_state().network:
            return await lookaround.get_coverage_tile_async(x, y, session)

    async def _apple_tile(self, x: int, y: int, session: ClientSession) -> Any:
        state = self._get_state()
        if ("a", x, y) not in state.tiles:
            state.tiles[("a", x, y)] = asyncio.ensure_future(
                self._fetch_apple_tile(x, y, session)
            )
        return await asyncio.shield(state.tiles[("a", x, y)])

    async def enumerate_apple_panoramas(
        self, lat: float, lng: float, session: ClientSession
    ) -> tuple[list[PanoCandidate], list[str]]:
        """Apple Look Around panoramas 4-30 m from the point."""
        errors: list[str] = []
        tile_results = await asyncio.gather(
            *[self._apple_tile(x, y, session) for x, y in _tiles_around(lat, lng)],
            return_exceptions=True,
        )
        cands: dict[str, PanoCandidate] = {}
        for res in tile_results:
            if isinstance(res, BaseException):
                errors.append(f"look around tile: {res}")
                continue
            for p in res.panos or []:
                d = haversine_m(p.lat, p.lon, lat, lng)
                if not MIN_PANO_DISTANCE_M <= d <= MAX_PANO_DISTANCE_M:
                    continue
                date = p.date
                cands[str(p.id)] = PanoCandidate(
                    pano_id=str(p.id),
                    lat=p.lat,
                    lon=p.lon,
                    distance_m=d,
                    bearing_deg=bearing_deg(p.lat, p.lon, lat, lng),
                    source="apple",
                    year=date.year if isinstance(date, datetime) else None,
                    month=date.month if isinstance(date, datetime) else None,
                    date_str=date.isoformat() if isinstance(date, datetime) else None,
                    raw=p,
                )
        return list(cands.values()), errors

    # ------------------------------------------------------------- Google render

    @with_retries()
    async def _download_google_pano(
        self, pano: Any, zoom: int, session: ClientSession
    ) -> PILImage.Image:
        return await sl_streetview.get_panorama_async(pano, session, zoom=zoom)

    async def _render_google(
        self,
        cand: PanoCandidate,
        bench_id: str,
        lat: float,
        lng: float,
        session: ClientSession,
    ) -> StreetViewImageCapture:
        pano = cand.raw
        fov = fov_for_distance(cand.distance_m)
        filename = self._view_filename(bench_id, cand.pano_id, "streetview")
        filepath = os.path.join(self.images_dir, filename)
        common = self._common_fields(
            cand, bench_id, lat, lng, fov, filename, ImageSource.STREETVIEW_STREETLEVEL
        )
        common["panorama_metadata"] = PanoramaMetadata.from_streetview_pano(pano)
        try:
            cached = self._load_cached(filepath)
            if cached:
                return StreetViewImageCaptureSuccess(
                    filepath=filepath,
                    file_size=os.path.getsize(filepath),
                    cached=True,
                    width=cached[0],
                    height=cached[1],
                    **common,
                )

            zoom = choose_zoom([s.x for s in pano.image_sizes], fov)
            state = self._get_state()
            async with state.pano_images:
                equirect = await self._download_google_pano(pano, zoom, session)
                arr = np.asarray(equirect.convert("RGB"))
                view = await asyncio.to_thread(
                    render_aimed_view,
                    arr,
                    center_compass_deg=google_center_compass(pano.heading),
                    aim_bearing_deg=cand.bearing_deg,
                    fov_deg=fov,
                    pitch_rad=_wrap_angle(pano.pitch),
                    roll_rad=_wrap_angle(pano.roll),
                )
                del arr, equirect  # the panorama is never kept
            return await self._finish_view(view, filepath, common)
        except Exception as e:
            logger.debug(f"Google view failed for {bench_id} pano {cand.pano_id}: {e}")
            return StreetViewImageCaptureError(
                error=f"google render failed: {e}", **common
            )

    # -------------------------------------------------------------- Apple render

    def _auth(self) -> Any:
        if self._apple_auth is None:
            self._apple_auth = lookaround.Authenticator()
        return self._apple_auth

    @with_retries(max_tries=3)
    async def _fetch_apple_face(self, pano: Any, face: int, zoom: int) -> bytes:
        # streetlevel's async face download is disabled upstream (403), so the sync
        # call runs in a worker thread; failures are retried via asyncio.sleep.
        async with self._get_state().network:
            try:
                return await asyncio.to_thread(
                    lookaround.get_panorama_face, pano, face, zoom, self._auth()
                )
            except Exception as e:
                raise ConnectionError(f"look around face {face}: {e}") from e

    async def _render_apple(
        self,
        cand: PanoCandidate,
        bench_id: str,
        lat: float,
        lng: float,
        session: ClientSession,
    ) -> StreetViewImageCapture:
        pano = cand.raw
        fov = fov_for_distance(cand.distance_m)
        filename = self._view_filename(bench_id, cand.pano_id, "lookaround")
        filepath = os.path.join(self.images_dir, filename)
        common = self._common_fields(
            cand, bench_id, lat, lng, fov, filename, ImageSource.APPLE_STREETLEVEL
        )
        common["panorama_metadata"] = PanoramaMetadata.from_lookaround_pano(pano)
        try:
            cached = self._load_cached(filepath)
            if cached:
                return StreetViewImageCaptureSuccess(
                    filepath=filepath,
                    file_size=os.path.getsize(filepath),
                    cached=True,
                    width=cached[0],
                    height=cached[1],
                    **common,
                )

            try:
                from pillow_heif import register_heif_opener

                register_heif_opener()
            except ImportError:
                pass

            # Zoom 2 stitches to ~6400 px wide in ~20 s on CPU; zoom 1 would be 4x
            # slower, zoom 3 too soft for narrow FOVs.
            zoom = APPLE_ZOOM
            state = self._get_state()
            async with state.pano_images:
                blobs = await asyncio.gather(
                    *[self._fetch_apple_face(pano, i, zoom) for i in range(6)]
                )
                faces = [PILImage.open(io.BytesIO(b)).convert("RGB") for b in blobs]
                async with state.apple_stitch:
                    equirect = await asyncio.to_thread(
                        lookaround.to_equirectangular, faces, pano.camera_metadata
                    )
                arr = np.asarray(equirect.convert("RGB"))
                view = await asyncio.to_thread(
                    render_aimed_view,
                    arr,
                    center_compass_deg=apple_center_compass(pano.heading),
                    aim_bearing_deg=cand.bearing_deg,
                    fov_deg=fov,
                    pitch_rad=_wrap_angle(pano.pitch),
                    roll_rad=_wrap_angle(pano.roll),
                )
                del arr, equirect, faces
            return await self._finish_view(view, filepath, common)
        except Exception as e:
            logger.debug(f"Apple view failed for {bench_id} pano {cand.pano_id}: {e}")
            return StreetViewImageCaptureError(
                error=f"look around render failed: {e}", **common
            )

    # ------------------------------------------------------------ shared pieces

    @staticmethod
    def _load_cached(filepath: str) -> tuple[int, int] | None:
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            try:
                with PILImage.open(filepath) as img:
                    return img.size
            except Exception:
                return None
        return None

    @staticmethod
    def _common_fields(
        cand: PanoCandidate,
        bench_id: str,
        lat: float,
        lng: float,
        fov: float,
        filename: str,
        source: ImageSource,
    ) -> dict[str, Any]:
        return {
            "bench_id": bench_id,
            "lat": lat,
            "lng": lng,
            "heading": round(cand.bearing_deg) % 360,
            "filename": filename,
            "image_source": source.value,
            "panorama_lat": cand.lat,
            "panorama_lng": cand.lon,
            "pano_id": cand.pano_id,
            "pano_date": cand.date_str,
            "camera_bearing_deg": cand.bearing_deg,
            "camera_distance_m": cand.distance_m,
            "fov_deg": fov,
            "pitch_deg": 0.0,
            "kind": ImageKind.AIMED.value,
        }

    async def _finish_view(
        self, view: np.ndarray, filepath: str, common: dict[str, Any]
    ) -> StreetViewImageCapture:
        """Indoor check, then save the aimed view."""
        img = PILImage.fromarray(view)
        if self.indoor_filter is not None:
            indoor, category, conf = await asyncio.to_thread(
                self.indoor_filter.is_indoor, img
            )
            if indoor:
                return StreetViewImageCaptureError(
                    error=f"indoor view dropped ({category}, {conf:.2f})", **common
                )
        await asyncio.to_thread(img.save, filepath, "JPEG", quality=JPEG_QUALITY)
        return StreetViewImageCaptureSuccess(
            filepath=filepath,
            file_size=os.path.getsize(filepath),
            cached=False,
            width=img.width,
            height=img.height,
            **common,
        )

    # --------------------------------------------------------------- public API

    def capture_bench_images(
        self, lat: float, lng: float, bench_id: str
    ) -> StreetViewBatchCaptureResult:
        """Synchronous convenience wrapper around :meth:`capture_bench_views_async`.

        Starts its own event loop; batch callers should use the async method instead.
        """
        return asyncio.run(self.capture_bench_views_async(lat, lng, bench_id))

    async def capture_bench_views_async(
        self,
        lat: float,
        lng: float,
        bench_id: str,
        session: ClientSession | None = None,
    ) -> StreetViewBatchCaptureResult:
        """Capture up to six aimed views of a bench from panoramas within 30 m."""
        own_session = session is None
        if session is None:
            session = ClientSession(
                timeout=aiohttp.ClientTimeout(total=120, connect=15)
            )
        try:
            captures: list[StreetViewImageCapture] = []
            errors: list[str] = []

            g_cands, g_errors = await self.enumerate_google_panoramas(lat, lng, session)
            errors += g_errors
            selected = select_views(filter_candidates(g_cands))
            captures += await asyncio.gather(
                *[self._render_google(c, bench_id, lat, lng, session) for c in selected]
            )

            if sum(1 for c in captures if c.success) < APPLE_FALLBACK_BELOW:
                a_cands, a_errors = await self.enumerate_apple_panoramas(
                    lat, lng, session
                )
                errors += a_errors
                a_selected = select_views(
                    filter_candidates(a_cands), max_views=APPLE_MAX_VIEWS
                )
                for c in a_selected:  # sequential: stitching is heavy
                    captures.append(
                        await self._render_apple(c, bench_id, lat, lng, session)
                    )

            if not captures:
                detail = f" ({'; '.join(errors[:3])})" if errors else ""
                captures.append(
                    StreetViewImageCaptureError(
                        bench_id=bench_id,
                        lat=lat,
                        lng=lng,
                        heading=0,
                        filename=self._view_filename(bench_id, "none", "streetview"),
                        error=f"no usable panorama within {MAX_PANO_DISTANCE_M:.0f} m{detail}",
                        image_source=ImageSource.STREETVIEW_STREETLEVEL.value,
                        kind=ImageKind.AIMED.value,
                    )
                )
            return StreetViewBatchCaptureResult.from_capture_results(
                bench_id, lat, lng, captures
            )
        finally:
            if own_session:
                await session.close()

    def get_street_view_metadata(
        self, lat: float, lng: float
    ) -> StreetViewMetadataResponse:
        """Street View availability at a location (free metadata endpoint)."""
        requested_location = StreetViewLocation(lat=lat, lng=lng)
        try:
            response = requests.get(
                "https://maps.googleapis.com/maps/api/streetview/metadata",
                params={
                    "location": f"{lat},{lng}",
                    "source": "outdoor",
                    "key": self.api_key,
                },
                timeout=10,
            )
            response.raise_for_status()
            raw = response.json()
            status = raw.get("status")
            if status != "OK":
                metadata = StreetViewMetadata(
                    status=status,
                    location=None,
                    pano_id=None,
                    date=None,
                    copyright=None,
                )
            else:
                loc = raw.get("location") or {}
                metadata = StreetViewMetadata(
                    status=status,
                    location=StreetViewLocation(lat=loc["lat"], lng=loc["lng"])
                    if loc
                    else None,
                    pano_id=raw.get("pano_id"),
                    date=raw.get("date"),
                    copyright=raw.get("copyright"),
                )
            return StreetViewMetadataResponse(
                requested_location=requested_location, metadata=metadata
            )
        except Exception:
            logger.exception("Error getting street view metadata")
            return StreetViewMetadataResponse(
                requested_location=requested_location,
                metadata=StreetViewMetadata(
                    status="ERROR",
                    location=None,
                    pano_id=None,
                    date=None,
                    copyright=None,
                ),
            )

    def cleanup_images(self, filepaths: list[str]) -> StreetViewCleanupResult:
        """Delete image files and report what happened."""
        removed_count = 0
        failed_count = 0
        errors = []
        for filepath in filepaths:
            try:
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
                    removed_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Could not remove image file {filepath}: {e}")
                logger.warning(errors[-1])
        return StreetViewCleanupResult(
            filepaths=filepaths,
            removed_count=removed_count,
            failed_count=failed_count,
            errors=errors,
        )


__all__ = ["OUTPUT_SIZE_PX", "StreetViewClient"]
