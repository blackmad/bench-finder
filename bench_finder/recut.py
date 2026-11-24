"""Re-cut aimed views at higher resolution from the same source panorama (free).

Aimed views were rendered at 1024 px, so the site's hero photos top out there. This
re-renders chosen images at ``HIRES_PX`` (2048) with the same framing: the same
panorama, aim bearing and FOV as the original row, only fetched at a panorama zoom
level that has enough pixels for the bigger output. Outputs go to
``<images-root>/hires/<same file name>``; the 1024 px original is never touched.
``bench_finder.publish`` cuts renditions from the hi-res file when it exists.

    uv run python -m bench_finder.recut --image-ids 46563,46570
    uv run python -m bench_finder.recut --heroes [--bbox amsterdam|all|w,s,e,n] [--limit N]

``--heroes`` picks the hero of every published bench with the publish ranking
(``bench_finder.publish.build.select_images``), one image per bench. Existing outputs
are skipped, so a run can be interrupted and restarted. Failures are logged and the
run continues. The database is only read.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
from PIL import Image as PILImage

from bench_finder.core.pano_geometry import (
    apple_center_compass,
    choose_zoom,
    fov_for_distance,
    google_center_compass,
    render_aimed_view,
)
from bench_finder.publish.images import HIRES_DIRNAME


logger = logging.getLogger("bench_finder.recut")

HIRES_PX = 2048
JPEG_QUALITY = 90
DEFAULT_CONCURRENCY = 2  # panoramas in memory at once (a zoom-5 Google pano is ~400 MB)
APPLE_STITCH_CONCURRENCY = 1  # torch reprojection is CPU heavy
# Stitched Look Around equirect width per zoom (0 = highest). Measured from face 0
# widths (5632 / 4128 / 2208 / 1568 px) with streetlevel's own width formula.
APPLE_EQUIRECT_WIDTHS = {0: 16384, 1: 12016, 2: 6416, 3: 4560}
# Pose drift (radians) between the stored metadata and today's panorama that is worth
# a warning: the framing would no longer match the original exactly.
POSE_DRIFT_WARN_RAD = 1e-3

SOURCES = {
    "STREETVIEW_STREETLEVEL": "google",
    "APPLE_STREETLEVEL": "apple",
    "AMSTERDAM_PANORAMA": "amsterdam",
}

_IMAGE_COLS = (
    "id, bench_candidate_id, filename, filepath, image_source, kind, pano_id, "
    "camera_bearing_deg, camera_distance_m, fov_deg, panorama_lat, panorama_lng, "
    "panorama_metadata"
)


# --------------------------------------------------------------------------- pure parts


@dataclass(frozen=True)
class RecutJob:
    """Everything needed to reproduce one aimed view, read from its ``images`` row."""

    image_id: int
    bench_id: int
    source: str  # "google" | "apple"
    pano_id: str
    filename: str
    aim_bearing_deg: float
    fov_deg: float
    pano_lat: float | None = None
    pano_lng: float | None = None
    # Pose stored at capture time (radians, streetlevel conventions); None if unknown.
    stored_heading: float | None = None
    stored_pitch: float | None = None
    stored_roll: float | None = None
    # Camera look-down in degrees (``recentre`` frames the bench low in the view).
    tilt_deg: float = 0.0


def job_from_row(row: dict[str, Any]) -> RecutJob:
    """Build a job from an ``images`` row; ``ValueError`` says why it cannot be re-cut."""
    if row.get("kind") not in ("aimed", "framed"):
        raise ValueError(f"kind is {row.get('kind')!r}, not an aimed view")
    source = SOURCES.get(row.get("image_source") or "")
    if source is None:
        raise ValueError(f"unsupported image_source {row.get('image_source')!r}")
    if not row.get("pano_id"):
        raise ValueError("no pano_id")
    if row.get("camera_bearing_deg") is None:
        raise ValueError("no camera_bearing_deg")
    name = row.get("filename") or (
        Path(row["filepath"]).name if row.get("filepath") else None
    )
    if not name:
        raise ValueError("no filename")
    fov = row.get("fov_deg")
    if fov is None:
        if row.get("camera_distance_m") is None:
            raise ValueError("no fov_deg and no camera_distance_m")
        fov = fov_for_distance(float(row["camera_distance_m"]))
    meta: dict[str, Any] = {}
    if row.get("panorama_metadata"):
        try:
            meta = json.loads(row["panorama_metadata"]) or {}
        except ValueError:
            meta = {}
    return RecutJob(
        image_id=int(row["id"]),
        bench_id=int(row["bench_candidate_id"]),
        source=source,
        pano_id=str(row["pano_id"]),
        filename=name,
        aim_bearing_deg=float(row["camera_bearing_deg"]),
        fov_deg=float(fov),
        pano_lat=row.get("panorama_lat") or meta.get("panorama_lat"),
        pano_lng=row.get("panorama_lng") or meta.get("panorama_lng"),
        stored_heading=meta.get("panorama_heading"),
        stored_pitch=meta.get("pitch"),
        stored_roll=meta.get("roll"),
        # The hero explorer saves a downward look as a negative view pitch.
        tilt_deg=-float(row.get("pitch_deg") or 0.0),
    )


def output_path(out_dir: Path, job: RecutJob) -> Path:
    """Hi-res file for a job: same base name as the original, in ``out_dir``."""
    return out_dir / Path(job.filename).name


def google_zoom(
    widths_by_zoom: list[int], fov_deg: float, out_px: int = HIRES_PX
) -> int:
    """Lowest Google zoom (index into ``image_sizes``) with enough pixels for ``out_px``."""
    return choose_zoom(widths_by_zoom, fov_deg, out_px=out_px)


def apple_zoom(fov_deg: float, out_px: int = HIRES_PX) -> int:
    """Look Around zoom (0 = highest) with enough pixels for ``out_px`` across the FOV."""
    zooms = sorted(APPLE_EQUIRECT_WIDTHS, reverse=True)  # lowest resolution first
    idx = choose_zoom([APPLE_EQUIRECT_WIDTHS[z] for z in zooms], fov_deg, out_px=out_px)
    return zooms[idx]


def _wrap(rad: float | None) -> float:
    """Wrap to (-pi, pi]; None -> 0 (as the original capture did)."""
    if rad is None:
        return 0.0
    return (rad + math.pi) % (2 * math.pi) - math.pi


def render_params(
    job: RecutJob,
    heading: float | None,
    pitch: float | None,
    roll: float | None,
    out_px: int = HIRES_PX,
) -> dict[str, Any]:
    """Keyword arguments for ``render_aimed_view``, matching the original capture.

    ``heading``/``pitch``/``roll`` are the panorama's pose as streetlevel reports it
    today (radians); they describe the pixels being downloaded, so they win over the
    stored copy. The aim bearing and FOV come from the row.
    """
    center = (
        google_center_compass(heading)
        if job.source == "google"
        else apple_center_compass(heading)
    )
    return {
        "center_compass_deg": center,
        "aim_bearing_deg": job.aim_bearing_deg,
        "fov_deg": job.fov_deg,
        "out_size": out_px,
        "pitch_rad": _wrap(pitch),
        "roll_rad": _wrap(roll),
        "tilt_deg": job.tilt_deg,
    }


def pose_drift(
    job: RecutJob, heading: float | None, pitch: float | None, roll: float | None
) -> float | None:
    """Largest angular difference (rad) between stored and current pose; None if unknown."""
    pairs = [
        (job.stored_heading, heading),
        (job.stored_pitch, pitch),
        (job.stored_roll, roll),
    ]
    diffs = [abs(_wrap(a - b)) for a, b in pairs if a is not None and b is not None]
    return max(diffs) if diffs else None


# --------------------------------------------------------------------------- job sources


def connect_ro(db: str | Path) -> sqlite3.Connection:
    """Read-only connection that waits for other writers instead of failing."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    conn.execute("PRAGMA busy_timeout = 120000")
    conn.row_factory = sqlite3.Row
    return conn


def load_rows(conn: sqlite3.Connection, image_ids: list[int]) -> list[dict]:
    if not image_ids:
        return []
    marks = ",".join("?" * len(image_ids))
    rows = conn.execute(
        f"SELECT {_IMAGE_COLS} FROM images WHERE id IN ({marks}) ORDER BY id",
        image_ids,
    ).fetchall()
    return [dict(r) for r in rows]


def hero_image_ids(
    conn: sqlite3.Connection,
    images_root: Path,
    *,
    include_unclassified: bool = False,
    limit: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[int]:
    """The published hero of each bench (publish ranking), one per bench."""
    from bench_finder.publish.build import select_images

    _, _, chosen = select_images(
        conn, images_root, include_unclassified, limit, bbox, gallery_size=1
    )
    return sorted(imgs[0]["id"] for imgs, has_hero in chosen.values() if has_hero)


# --------------------------------------------------------------------------- rendering


@dataclass
class _State:
    panos: asyncio.Semaphore
    apple_stitch: asyncio.Semaphore
    apple_auth: Any = None


@dataclass
class RecutResult:
    job: RecutJob
    status: str  # "done" | "skipped" | "failed"
    path: Path | None = None
    zoom: int | None = None
    seconds: float = 0.0
    error: str | None = None


def _save_jpeg(view: Any, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    PILImage.fromarray(view).save(tmp, "JPEG", quality=JPEG_QUALITY)
    tmp.replace(dest)
    return dest.stat().st_size


def _check_drift(job: RecutJob, heading: Any, pitch: Any, roll: Any) -> None:
    drift = pose_drift(job, heading, pitch, roll)
    if drift is not None and drift > POSE_DRIFT_WARN_RAD:
        logger.warning(
            "image %s: panorama pose changed by %.4f rad since capture; framing may differ",
            job.image_id,
            drift,
        )


async def _render_google(
    job: RecutJob, session: aiohttp.ClientSession, out_px: int
) -> tuple[Any, int]:
    from streetlevel import streetview as sl_streetview

    from bench_finder.core.streetview import _to_rgb_array, with_retries

    @with_retries()
    async def meta() -> Any:
        return await sl_streetview.find_panorama_by_id_async(job.pano_id, session)

    @with_retries()
    async def download(pano: Any, zoom: int) -> Any:
        return await sl_streetview.get_panorama_async(pano, session, zoom=zoom)

    pano = await meta()
    if pano is None:
        raise RuntimeError("panorama no longer exists")
    _check_drift(job, pano.heading, pano.pitch, pano.roll)
    zoom = google_zoom([s.x for s in pano.image_sizes], job.fov_deg, out_px)
    equirect = await download(pano, zoom)
    arr = await asyncio.to_thread(_to_rgb_array, equirect)
    del equirect
    params = render_params(job, pano.heading, pano.pitch, pano.roll, out_px)
    return await asyncio.to_thread(render_aimed_view, arr, **params), zoom


async def _render_apple(
    job: RecutJob, session: aiohttp.ClientSession, state: _State, out_px: int
) -> tuple[Any, int]:
    from streetlevel import lookaround

    from bench_finder.core.streetview import _decode_faces, _to_rgb_array, with_retries

    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except ImportError:
        pass

    if job.pano_lat is None or job.pano_lng is None:
        raise RuntimeError("no panorama position to find its coverage tile")

    @with_retries()
    async def tile() -> Any:
        return await lookaround.get_coverage_tile_by_latlon_async(
            job.pano_lat, job.pano_lng, session
        )

    @with_retries(max_tries=3)
    async def face(pano: Any, i: int, zoom: int) -> bytes:
        try:
            return await asyncio.to_thread(
                lookaround.get_panorama_face, pano, i, zoom, state.apple_auth
            )
        except Exception as e:
            raise ConnectionError(f"look around face {i}: {e}") from e

    cov = await tile()
    pano = next((p for p in cov.panos or [] if str(p.id) == job.pano_id), None)
    if pano is None:
        raise RuntimeError("panorama no longer in Look Around coverage")
    _check_drift(job, pano.heading, pano.pitch, pano.roll)
    if state.apple_auth is None:
        state.apple_auth = lookaround.Authenticator()
    zoom = apple_zoom(job.fov_deg, out_px)
    blobs = await asyncio.gather(*[face(pano, i, zoom) for i in range(6)])
    faces = await asyncio.to_thread(_decode_faces, blobs)
    del blobs
    async with state.apple_stitch:
        equirect = await asyncio.to_thread(
            lookaround.to_equirectangular, faces, pano.camera_metadata
        )
    del faces
    arr = await asyncio.to_thread(_to_rgb_array, equirect)
    del equirect
    params = render_params(job, pano.heading, pano.pitch, pano.roll, out_px)
    return await asyncio.to_thread(render_aimed_view, arr, **params), zoom


async def _render_amsterdam(
    job: RecutJob, session: aiohttp.ClientSession, out_px: int
) -> tuple[Any, int]:
    """City panoramas: one 8000 px equirectangular, centre column north, level."""
    from bench_finder.vantage import amsterdam_equirect

    arr = await amsterdam_equirect(job.pano_id, session)
    view = await asyncio.to_thread(
        render_aimed_view,
        arr,
        center_compass_deg=0.0,
        aim_bearing_deg=job.aim_bearing_deg,
        fov_deg=job.fov_deg,
        out_size=out_px,
        tilt_deg=job.tilt_deg,
    )
    return view, 0


async def recut_one(
    job: RecutJob,
    out_dir: Path,
    session: aiohttp.ClientSession,
    state: _State,
    out_px: int = HIRES_PX,
) -> RecutResult:
    dest = output_path(out_dir, job)
    if dest.is_file() and dest.stat().st_size > 0:
        return RecutResult(job, "skipped", dest)
    t0 = time.monotonic()
    try:
        async with state.panos:
            if job.source == "google":
                view, zoom = await _render_google(job, session, out_px)
            elif job.source == "amsterdam":
                view, zoom = await _render_amsterdam(job, session, out_px)
            else:
                view, zoom = await _render_apple(job, session, state, out_px)
            await asyncio.to_thread(_save_jpeg, view, dest)
        return RecutResult(job, "done", dest, zoom, time.monotonic() - t0)
    except Exception as e:
        return RecutResult(
            job, "failed", None, None, time.monotonic() - t0, f"{type(e).__name__}: {e}"
        )


async def run(
    jobs: list[RecutJob],
    out_dir: Path,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    out_px: int = HIRES_PX,
) -> list[RecutResult]:
    state = _State(
        panos=asyncio.Semaphore(concurrency),
        apple_stitch=asyncio.Semaphore(APPLE_STITCH_CONCURRENCY),
    )
    results: list[RecutResult] = []
    timeout = aiohttp.ClientTimeout(total=600, connect=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [
            asyncio.ensure_future(recut_one(j, out_dir, session, state, out_px))
            for j in jobs
        ]
        for n, fut in enumerate(asyncio.as_completed(tasks), 1):
            r = await fut
            results.append(r)
            j = r.job
            if r.status == "failed":
                logger.error(
                    "[%d/%d] image %s (%s %s) failed: %s",
                    n,
                    len(jobs),
                    j.image_id,
                    j.source,
                    j.pano_id,
                    r.error,
                )
            elif r.status == "done":
                logger.info(
                    "[%d/%d] image %s (%s, zoom %s, fov %.1f) -> %s in %.1fs",
                    n,
                    len(jobs),
                    j.image_id,
                    j.source,
                    r.zoom,
                    j.fov_deg,
                    r.path,
                    r.seconds,
                )
            else:
                logger.debug(
                    "[%d/%d] image %s exists, skipped", n, len(jobs), j.image_id
                )
    return results


# --------------------------------------------------------------------------- CLI


def _parse_bbox(value: str) -> tuple[float, float, float, float] | None:
    from bench_finder.coverage import parse_bbox

    return parse_bbox(value)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    pick = ap.add_mutually_exclusive_group(required=True)
    pick.add_argument("--image-ids", help="Comma-separated images.id values")
    pick.add_argument(
        "--heroes", action="store_true", help="The published hero of each bench"
    )
    ap.add_argument("--db", default=os.getenv("DATABASE_PATH", "data/benches.db"))
    ap.add_argument(
        "--images-root", type=Path, default=Path(os.getenv("IMAGES_DIR", "images"))
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        help=f"Where re-cuts go (default <images-root>/{HIRES_DIRNAME}; publish only reads that)",
    )
    ap.add_argument("--bbox", default="amsterdam", help="--heroes coverage, as publish")
    ap.add_argument("--include-unclassified", action="store_true")
    ap.add_argument("--limit", type=int, help="Re-cut at most N images")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--size", type=int, default=HIRES_PX, help="Output size in px")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    for noisy in ("backoff", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    out_dir = a.out_dir or a.images_root / HIRES_DIRNAME
    conn = connect_ro(a.db)
    try:
        if a.heroes:
            ids = hero_image_ids(
                conn,
                a.images_root,
                include_unclassified=a.include_unclassified,
                bbox=_parse_bbox(a.bbox),
            )
            logger.info("%d benches have a hero image", len(ids))
        else:
            ids = [int(x) for x in a.image_ids.split(",") if x.strip()]
        rows = load_rows(conn, ids)
    finally:
        conn.close()

    missing = set(ids) - {r["id"] for r in rows}
    for i in sorted(missing):
        logger.error("image %s: not in the database", i)
    jobs: list[RecutJob] = []
    for r in rows:
        try:
            jobs.append(job_from_row(r))
        except ValueError as e:
            logger.warning("image %s: cannot re-cut (%s)", r["id"], e)
    todo = [j for j in jobs if not output_path(out_dir, j).is_file()]
    already = len(jobs) - len(todo)
    if a.limit is not None:
        todo = todo[: a.limit]
    logger.info(
        "%d re-cuttable, %d already done, %d to render into %s",
        len(jobs),
        already,
        len(todo),
        out_dir,
    )
    t0 = time.monotonic()
    results = asyncio.run(run(todo, out_dir, concurrency=a.concurrency, out_px=a.size))
    done = [r for r in results if r.status == "done"]
    failed = [r for r in results if r.status == "failed"]
    wall = time.monotonic() - t0
    logger.info(
        "done %d, failed %d, skipped %d in %.0fs (%.1fs/image wall)",
        len(done),
        len(failed),
        len(results) - len(done) - len(failed),
        wall,
        wall / max(1, len(done)),
    )
    if failed:
        logger.info(
            "failed image ids: %s", ",".join(str(r.job.image_id) for r in failed)
        )
    return 1 if failed or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
