"""Wide views for benches that still have no photo (pins a few metres off).

Aimed views point at the OSM pin with a narrow field of view, so a pin a few
metres off the bench leaves it at the edge of the frame or outside it, and views
from panoramas closer than 4 m are never taken (the aim swings too much). For
every Amsterdam bench without a hero this renders a 100° view towards the pin
from the two nearest city panoramas (separate spots, 1.5-20 m away). The view
is saved as an ``aimed`` image, so ``detect_aimed --model sam3`` judges it (its
centre-column rule covers about ±35° here), and ``recentre`` re-aims a hero
found in it at the bench.

    uv run python -m bench_finder.wide_views [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sqlite3
from collections import Counter
from pathlib import Path

import aiohttp

from bench_finder.core.pano_geometry import haversine_m, render_aimed_view
from bench_finder.models.enums import ImageSource
from bench_finder.publish.build import AMSTERDAM_BBOX, select_images
from bench_finder.vantage import SPREAD_M, amsterdam_candidates, amsterdam_equirect


logger = logging.getLogger(__name__)
WIDE_FOV = 100.0
MIN_M, MAX_M = 1.5, 20.0
PER_BENCH = 2
SUFFIX = "amsterdam_wide"


def benches_without_hero(db: str, images_root: Path) -> list[tuple[int, float, float]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    conn.row_factory = sqlite3.Row
    try:
        rows, _, chosen = select_images(
            conn, images_root, include_unclassified=True, bbox=AMSTERDAM_BBOX
        )
        return [(r["id"], r["lat"], r["lng"]) for r in rows if not chosen[r["id"]][1]]
    finally:
        conn.close()  # an open read transaction would block this job's own writes


def pick(cands: list, n: int = PER_BENCH) -> list:
    """Nearest first, newest per spot, spots at least ``SPREAD_M`` apart."""
    cands = [c for c in cands if MIN_M <= c.distance_m <= MAX_M]
    cands.sort(key=lambda c: (round(c.distance_m), -(c.year or 0)))
    out: list = []
    for c in cands:
        if all(haversine_m(c.lat, c.lon, o.lat, o.lon) >= SPREAD_M for o in out):
            out.append(c)
        if len(out) == n:
            break
    return out


async def _run(db: str, images_root: Path, limit: int | None, dry: bool) -> dict:
    from bench_finder.core.streetview import StreetViewClient
    from bench_finder.models.streetview_models import StreetViewImageCaptureError
    from bench_finder.services.database import BenchDatabase
    from bench_finder.services.image_download_service import image_base_from_capture

    benches = benches_without_hero(db, images_root)[:limit]
    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    have = {
        f
        for (f,) in ro.execute(
            f"SELECT filename FROM images WHERE filename LIKE '%_{SUFFIX}.jpg'"
        )
    }
    ro.close()
    client = StreetViewClient()
    database = None if dry else BenchDatabase(db_path=db)
    stats: Counter[str] = Counter(benches=len(benches))
    sem = asyncio.Semaphore(3)  # be gentle with the city's servers
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=300)
    ) as session:

        async def one(bid: int, lat: float, lng: float) -> None:
            async with sem:
                try:
                    picked = pick(await amsterdam_candidates(lat, lng, MAX_M, session))
                except Exception as e:
                    stats["enumerate_failed"] += 1
                    logger.warning("bench %s: %s", bid, e)
                    return
                stats["with_pano"] += bool(picked)
                for c in picked:
                    filename = client._view_filename(str(bid), c.pano_id, SUFFIX)
                    filepath = os.path.join(client.images_dir, filename)
                    if dry or filename in have:  # a file with no row is redone
                        stats["skipped" if not dry else "planned"] += 1
                        continue
                    common = client._common_fields(
                        c,
                        str(bid),
                        lat,
                        lng,
                        WIDE_FOV,
                        filename,
                        ImageSource.AMSTERDAM_PANORAMA,
                    )
                    try:
                        arr = await amsterdam_equirect(c.pano_id, session, "medium")
                        view = await asyncio.to_thread(
                            render_aimed_view,
                            arr,
                            center_compass_deg=0.0,
                            aim_bearing_deg=c.bearing_deg,
                            fov_deg=WIDE_FOV,
                        )
                        del arr
                        cap = await client._finish_view(view, filepath, common)
                    except Exception as e:
                        cap = StreetViewImageCaptureError(
                            error=f"wide render failed: {e}", **common
                        )
                    stats["rendered" if cap.success else "failed"] += 1
                    assert database is not None
                    await asyncio.to_thread(
                        database.add_image, image_base_from_capture(cap), bid
                    )
                if sum(stats[k] for k in ("with_pano", "enumerate_failed")) % 100 == 0:
                    logger.info("%s", dict(stats))

        await asyncio.gather(*(one(*b) for b in benches))
    return dict(stats)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(asyncio.run(_run(a.db, a.images_root, a.limit, a.dry_run)))


if __name__ == "__main__":
    main()
