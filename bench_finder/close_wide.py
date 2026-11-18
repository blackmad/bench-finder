"""Wide views from the panoramas right next to a bench (Google, Apple, city).

The closest panoramas give the best shots, but a narrow view aimed at an OSM pin
a few metres off misses the bench from there: 3 m of pin error swings the aim
30-45 degrees at 4 m (Prinsengracht 370, 2026-11-18). This renders a 100 degree
view towards the pin from up to ``PER_BENCH`` panoramas 1.5-12 m away, saved as
``aimed`` images with a ``<source>_wide`` suffix; ``detect_aimed --model sam3``
judges them and ``recentre`` re-aims a hero found in one at the bench.

    uv run python -m bench_finder.close_wide --ids 1155,1050 [--dry-run]
    uv run python -m bench_finder.close_wide --weak   # benches whose hero is weak
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
from collections import Counter

import aiohttp

from bench_finder.core.pano_geometry import haversine_m
from bench_finder.vantage import (
    SPREAD_M,
    candidates_for,
    load_benches,
    render_amsterdam,
)


logger = logging.getLogger(__name__)
WIDE_FOV = 100.0
MIN_M, MAX_M = 1.5, 12.0
PER_BENCH = 3


def pick(cands: list, have: set[str], n: int = PER_BENCH) -> list:
    """Nearest first, newest per spot, spots ``SPREAD_M`` apart, not done before."""
    cands = [
        c
        for c in cands
        if MIN_M <= c.distance_m <= MAX_M and f"{c.pano_id}:wide" not in have
    ]
    cands.sort(key=lambda c: (round(c.distance_m), -(c.year or 0)))
    # The nearest of each source first (they differ in date, height and what
    # was parked there), then the rest nearest first.
    firsts = {}
    for c in cands:
        firsts.setdefault(c.source, c)
    cands = list(firsts.values()) + [c for c in cands if c not in firsts.values()]
    out: list = []
    for c in cands:
        if all(haversine_m(c.lat, c.lon, o.lat, o.lon) >= SPREAD_M for o in out):
            out.append(c)
        if len(out) == n:
            break
    return out


def weak_hero_ids(db: str) -> list[int]:
    """Benches whose best SAM 3 score is under 0.8 or whose hero view is blocked."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        best = dict(
            conn.execute(
                "SELECT i.bench_candidate_id, max(di.confidence) FROM images i "
                "JOIN detections d ON d.image_id = i.id AND d.model_id = 'sam3' "
                "JOIN detection_items di ON di.detection_id = d.id AND di.is_target = 1 "
                "GROUP BY i.bench_candidate_id"
            )
        )
    finally:
        conn.close()
    return sorted(b for b, s in best.items() if (s or 0) < 0.8)


async def _run(db: str, ids: list[int], dry: bool) -> dict:
    from bench_finder.core.streetview import StreetViewClient
    from bench_finder.services.database import BenchDatabase
    from bench_finder.services.image_download_service import image_base_from_capture

    want = set(ids)
    benches = [b for b in load_benches(db) if b.id in want]
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    have: dict[int, set[str]] = {}
    for cid, pid in conn.execute(
        "SELECT bench_candidate_id, pano_id FROM images WHERE filename LIKE '%_wide.jpg'"
    ):
        have.setdefault(cid, set()).add(f"{pid}:wide")
    conn.close()
    client = StreetViewClient()
    database = None if dry else BenchDatabase(db_path=db)
    stats: Counter[str] = Counter(benches=len(benches))
    sem, apple_lock = asyncio.Semaphore(4), asyncio.Lock()
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=300)
    ) as session:

        async def one(b) -> None:
            async with sem:
                try:
                    cands, _ = await candidates_for(client, b, session)
                except Exception as e:
                    stats["enumerate_failed"] += 1
                    logger.warning("bench %s: %s", b.id, e)
                    return
                picked = pick(cands, have.get(b.id, set()))
                stats["with_close_pano"] += bool(picked)
                for c in picked:
                    stats[f"picked_{c.source}"] += 1
                    if dry:
                        continue
                    suffix = f"{c.source}_wide"
                    if c.source == "google":
                        cap = await client._render_google(
                            c, str(b.id), b.lat, b.lng, session, WIDE_FOV, suffix
                        )
                    elif c.source == "apple":
                        async with apple_lock:  # stitching is heavy
                            cap = await client._render_apple(
                                c, str(b.id), b.lat, b.lng, session, WIDE_FOV, suffix
                            )
                    else:
                        cap = await render_amsterdam(
                            client, c, b, session, fov=WIDE_FOV, suffix=suffix
                        )
                    stats["rendered" if cap.success else "failed"] += 1
                    assert database is not None
                    await asyncio.to_thread(
                        database.add_image, image_base_from_capture(cap), b.id
                    )

        await asyncio.gather(*(one(b) for b in benches))
    return dict(stats)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--ids", help="comma-separated bench ids")
    ap.add_argument("--weak", action="store_true", help="benches with a weak hero")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ids = [int(x) for x in a.ids.split(",")] if a.ids else []
    if a.weak:
        ids += weak_hero_ids(a.db)
    print(asyncio.run(_run(a.db, ids, a.dry_run)))


if __name__ == "__main__":
    main()
