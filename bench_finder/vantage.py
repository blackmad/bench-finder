"""Second capture: new views of each bench from better vantage points (plan, Phase 6).

The first capture chose panoramas before facings were known. Now most benches have
one (``bench_attributes.facing_deg`` or an OSM ``direction``), so this looks for
panoramas from Google and Apple (streetlevel) and the City of Amsterdam (open data,
``api.data.amsterdam.nl/panorama``) and prefers, per bench:

- **behind** it (the camera looks the way the bench faces: its back and what it
  looks at), else **in front** (its seat, with what is behind it);
- 5-15 m away; for benches that look at water, front views from across the water
  up to ``WATER_MAX_M`` (a clear far view beats a close one through a hedge);
- newer panoramas; panoramas this bench already has a view from are skipped.

The best ``PER_BENCH`` are rendered aimed at the bench (narrower field of view
far away) and saved as ``kind = 'aimed'`` images, so ``detect_aimed --model sam3``,
``label_views`` and the publish ranking treat them like the first capture.

    uv run python -m bench_finder.vantage plan [--limit N]   # candidates only, free
    uv run python -m bench_finder.vantage run [--limit N]    # render and save views
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import math
import os
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
import numpy as np
from PIL import Image

from bench_finder.core.pano_geometry import (
    MIN_PANO_DISTANCE_M,
    PanoCandidate,
    bearing_deg,
    haversine_m,
    render_aimed_view,
)
from bench_finder.models.enums import ImageSource


logger = logging.getLogger(__name__)

NEAR_MAX_M = 30.0
WATER_MAX_M = 60.0
PER_BENCH = 2
MIN_FACING_COS = 0.34  # within ~70° of straight behind or straight in front
FOV_MIN, FOV_MAX = 18.0, 90.0
SPREAD_M = 3.0  # picks for one bench at least this far apart
BENCH_HALF_SPAN_M = 3.0  # frame about +-3 m around the bench, as the first capture
AMS_API = "https://api.data.amsterdam.nl/panorama/panoramas/"
UA = {"User-Agent": "bench-finder (open data panoramas)"}


@dataclass
class Bench:
    id: int
    lat: float
    lng: float
    facing: float | None  # None: no facing yet, panoramas rank by distance only
    water: bool
    have: frozenset[str]  # pano ids this bench already has a view from


def fov_for(distance_m: float) -> float:
    """``2·atan(3 m / d)`` clamped to [18°, 90°]: narrower than the first capture far away."""
    fov = math.degrees(2 * math.atan(BENCH_HALF_SPAN_M / max(distance_m, 1e-6)))
    return min(max(fov, FOV_MIN), FOV_MAX)


def score(c: PanoCandidate, b: Bench) -> float | None:
    """Higher is better; None when the panorama is no use for this bench."""
    if b.facing is None:  # no side to prefer: any near panorama will do
        d = c.distance_m
        if not MIN_PANO_DISTANCE_M <= d <= NEAR_MAX_M:
            return None
        # Close matters more than new here: without a facing the view is aimed
        # at the pin, and a far view of an unknown side is the weakest shot.
        dist_pen = 0.0 if 5 <= d <= 12 else ((d - 12) / 15 if d > 12 else (5 - d) / 5)
        return 0.6 - 0.5 * dist_pen + 0.01 * ((c.year or 2015) - 2015)
    rel = math.radians((c.bearing_deg - b.facing + 180) % 360 - 180)
    cos = math.cos(rel)  # 1: camera behind the bench, -1: in front of it
    if abs(cos) < MIN_FACING_COS:
        return None
    d = c.distance_m
    max_m = WATER_MAX_M if (b.water and cos < 0) else NEAR_MAX_M
    if not MIN_PANO_DISTANCE_M <= d <= max_m:
        return None
    angle = cos if cos > 0 else 0.8 * -cos
    dist_pen = 0.0 if 5 <= d <= 15 else ((d - 15) / 45 if d > 15 else (5 - d) / 5)
    recency = 0.02 * ((c.year or 2015) - 2015)
    return angle - 0.5 * dist_pen + recency


def choose(
    cands: list[PanoCandidate], b: Bench, n: int = PER_BENCH
) -> list[PanoCandidate]:
    """Best ``n`` new panoramas, one from behind and one from in front when both exist."""
    scored = []
    for c in cands:
        if c.pano_id in b.have:
            continue
        s = score(c, b)
        if s is not None:
            scored.append((s, c))
    scored.sort(key=lambda sc: -sc[0])
    # Two picks from the same spot (another year) show the same thing.
    spread: list[tuple[float, PanoCandidate]] = []
    for sc, c in scored:
        if all(haversine_m(c.lat, c.lon, o.lat, o.lon) >= SPREAD_M for _, o in spread):
            spread.append((sc, c))
    scored = spread
    picked: list[PanoCandidate] = []
    sides: set[bool] = set()
    for _, c in scored:  # first pass: one per side
        if b.facing is None:
            break
        side = math.cos(math.radians(c.bearing_deg - b.facing)) > 0
        if side not in sides:
            picked.append(c)
            sides.add(side)
        if len(picked) == n:
            return picked
    for _, c in scored:
        if c not in picked:
            picked.append(c)
        if len(picked) == n:
            break
    return picked


# ----------------------------------------------------------------- Amsterdam


async def amsterdam_candidates(
    lat: float, lng: float, max_m: float, session: aiohttp.ClientSession
) -> list[PanoCandidate]:
    """City panoramas within ``max_m``, newest per spot first (the API has every year)."""
    params = {"near": f"{lng},{lat}", "radius": str(int(max_m)), "page_size": "1000"}
    async with session.get(AMS_API, params=params, headers=UA) as r:
        r.raise_for_status()
        data = await r.json()
    out = []
    for p in data.get("_embedded", {}).get("panoramas", []):
        plng, plat = p["geometry"]["coordinates"][:2]
        d = haversine_m(plat, plng, lat, lng)
        year = int(p["mission_year"]) if p.get("mission_year") else None
        out.append(
            PanoCandidate(
                pano_id=p["pano_id"],
                lat=plat,
                lon=plng,
                distance_m=d,
                bearing_deg=bearing_deg(plat, plng, lat, lng),
                source="amsterdam",
                year=year,
                month=int(p["timestamp"][5:7]) if p.get("timestamp") else None,
                date_str=p.get("timestamp"),
                raw=p,
            )
        )
    return out


async def amsterdam_equirect(
    pano_id: str, session: aiohttp.ClientSession, size: str = "full"
) -> np.ndarray:
    """The equirectangular (``full`` 8000 px, ``medium`` 4000 px); its centre column
    faces north (verified against Google and across mission years, whatever the
    API's ``heading``)."""
    async with session.get(f"{AMS_API}{pano_id}/", headers=UA) as r:
        r.raise_for_status()
        url = (await r.json())["_links"][f"equirectangular_{size}"]["href"]
    async with session.get(url, headers=UA) as r:
        r.raise_for_status()
        raw = await r.read()
    return np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"))


async def render_amsterdam(client: Any, c: PanoCandidate, b: Bench, session) -> Any:
    from bench_finder.models.streetview_models import StreetViewImageCaptureError

    fov = fov_for(c.distance_m)
    filename = client._view_filename(str(b.id), c.pano_id, "amsterdam")
    filepath = os.path.join(client.images_dir, filename)
    common = client._common_fields(
        c, str(b.id), b.lat, b.lng, fov, filename, ImageSource.AMSTERDAM_PANORAMA
    )
    try:
        # Capture only needs detection quality; hero re-cuts use the full size.
        arr = await amsterdam_equirect(c.pano_id, session, "medium")
        view = await asyncio.to_thread(
            render_aimed_view,
            arr,
            center_compass_deg=0.0,
            aim_bearing_deg=c.bearing_deg,
            fov_deg=fov,
        )
        del arr
        return await client._finish_view(view, filepath, common)
    except Exception as e:
        return StreetViewImageCaptureError(
            error=f"amsterdam render failed: {e}", **common
        )


# ----------------------------------------------------------------- benches


def load_benches(db: str, limit: int | None = None) -> list[Bench]:
    """Amsterdam benches with their facing (VLM/human, else OSM ``direction``, else None)."""
    from bench_finder.publish.build import AMSTERDAM_BBOX, parse_direction

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    w, s, e, n = AMSTERDAM_BBOX
    rows = conn.execute(
        "SELECT c.id, c.lat, c.lng, c.tags, a.facing_deg, a.faces_category "
        "FROM bench_candidates c LEFT JOIN bench_attributes a "
        "ON a.bench_candidate_id = c.id WHERE c.lat BETWEEN ? AND ? "
        "AND c.lng BETWEEN ? AND ? ORDER BY c.id",
        (s, n, w, e),
    ).fetchall()
    have: dict[int, set[str]] = {}
    for cid, pid in conn.execute("SELECT bench_candidate_id, pano_id FROM images"):
        if pid:
            have.setdefault(cid, set()).add(str(pid))
    out = []
    for cid, lat, lng, tags, vlm_facing, faces in rows:
        facing = vlm_facing
        if facing is None:
            facing = parse_direction(
                (json.loads(tags) if tags else {}).get("direction")
            )
        out.append(
            Bench(
                cid,
                lat,
                lng,
                None if facing is None else float(facing),
                faces == "water",
                frozenset(have.get(cid, ())),
            )
        )
    return out[:limit] if limit else out


async def candidates_for(
    client: Any, b: Bench, session
) -> tuple[list[PanoCandidate], list[str]]:
    max_m = WATER_MAX_M if b.water else NEAR_MAX_M
    errors: list[str] = []
    g, e1 = await client.enumerate_google_panoramas(b.lat, b.lng, session, max_m=max_m)
    a, e2 = await client.enumerate_apple_panoramas(b.lat, b.lng, session, max_m=max_m)
    errors += e1 + e2
    try:
        ams = await amsterdam_candidates(b.lat, b.lng, max_m, session)
    except Exception as e:
        ams, errors = [], [*errors, f"amsterdam: {e}"]
    return [c for c in g if not c.is_third_party] + a + ams, errors


async def _run(db: str, limit: int | None, render: bool, concurrency: int) -> dict:
    from bench_finder.core.streetview import StreetViewClient
    from bench_finder.services.database import BenchDatabase
    from bench_finder.services.image_download_service import image_base_from_capture

    # Benches already done (a restart must not add two more views each).
    done_file = Path(db).with_name("vantage_done.txt")
    done = set(done_file.read_text().split()) if done_file.exists() else set()
    benches = [b for b in load_benches(db, limit) if str(b.id) not in done]
    client = StreetViewClient()
    database = BenchDatabase(db_path=db) if render else None
    stats: Counter[str] = Counter()
    sem = asyncio.Semaphore(concurrency)
    apple_lock = asyncio.Lock()  # stitching Apple faces is heavy: one at a time
    timeout = aiohttp.ClientTimeout(total=300, connect=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def one(b: Bench) -> None:
            async with sem:
                try:
                    cands, _ = await candidates_for(client, b, session)
                except Exception as e:
                    stats["enumerate_failed"] += 1
                    logger.warning("bench %s: %s", b.id, e)
                    return
                picked = choose(cands, b)
                stats["benches"] += 1
                stats["with_new_view"] += bool(picked)
                for c in picked:
                    stats[f"picked_{c.source}"] += 1
                    side = (
                        "unknown"
                        if b.facing is None
                        else "behind"
                        if math.cos(math.radians(c.bearing_deg - b.facing)) > 0
                        else "front"
                    )
                    stats[f"picked_{side}"] += 1
                    if not render:
                        continue
                    fov = fov_for(c.distance_m)
                    if c.source == "google":
                        cap = await client._render_google(
                            c, str(b.id), b.lat, b.lng, session, fov_deg=fov
                        )
                    elif c.source == "apple":
                        async with apple_lock:
                            cap = await client._render_apple(
                                c, str(b.id), b.lat, b.lng, session, fov_deg=fov
                            )
                    else:
                        cap = await render_amsterdam(client, c, b, session)
                    stats["rendered" if cap.success else "render_failed"] += 1
                    assert database is not None
                    await asyncio.to_thread(
                        database.add_image, image_base_from_capture(cap), b.id
                    )
                if render:
                    with done_file.open("a") as f:
                        f.write(f"{b.id}\n")
                if stats["benches"] % 100 == 0:
                    logger.info("%s", dict(stats))

        await asyncio.gather(*(one(b) for b in benches))
    return {"benches": len(benches), **stats}


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--limit", type=int)
        p.add_argument("--concurrency", type=int, default=4)
    a = ap.parse_args()
    print(asyncio.run(_run(a.db, a.limit, a.cmd == "run", a.concurrency)))


if __name__ == "__main__":
    main()
