"""Scenic views: a wide 4:3 render that shows what a bench looks at.

The automatic views aim straight at the bench with a narrow field of view, then
recentre, fade and crop square around it (bench 1743: a close, washed-out shot
of a bench by the Amstel). A scenic view takes the same camera, turns it from
the bench toward the bench's facing, widens to ~90 degrees and keeps a 4:3
landscape, so the bench sits low in the frame with the water, square or park
it faces beyond.

One per bench (images.kind = 'scenic', replaced on re-run), from the best
camera already behind or beside the bench whose view SAM 3 confirmed. Publish
puts it second in the gallery; it leads only when someone picks it.

    python -m bench_finder.scenic --limit 50          # a sample
    python -m bench_finder.scenic --bench 1743
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image


if TYPE_CHECKING:
    import numpy as np


log = logging.getLogger(__name__)

FOV_DEG = 90.0
TILT_DEG = 0.0  # looking down brings the camera car's roof into frame
CROP_TOP = 0.4  # where the 4:3 window sits in the square render (0 top, 1 bottom)
MAX_TURN_DEG = 25.0  # how far the aim turns from the bench toward its facing
MAX_OFF_FACING_DEG = 100.0  # camera behind or beside the bench, not in front
SAVE_W, HIRES_W = 1024, 2048
SOURCE_KEY = {
    "STREETVIEW_STREETLEVEL": "google",
    "APPLE_STREETLEVEL": "apple",
    "AMSTERDAM_PANORAMA": "amsterdam",
}


def _signed(a: float, b: float) -> float:
    """b - a in (-180, 180]."""
    return (b - a + 180.0) % 360.0 - 180.0


def scenic_aim(camera_to_bench: float, facing: float) -> float:
    """Turn from the bench toward the facing by up to MAX_TURN_DEG.

    The bench stays in a 90-degree frame (it is at most 25 degrees off centre)
    while the view swings toward what it looks at."""
    d = _signed(camera_to_bench, facing)
    turn = max(-MAX_TURN_DEG, min(MAX_TURN_DEG, d))
    return (camera_to_bench + turn) % 360.0


NEAR_M, FAR_M = 8.0, 25.0  # closer looks down at the bench; farther loses it


def scenic_score(off: float, dist: float | None, year: int, now: int = 2026) -> float:
    """Lower is better. One point each: 30 degrees off the facing, 2 m closer
    than NEAR_M (a camera right behind the bench sees paving, bench 5768),
    10 m beyond FAR_M, 6 years of age."""
    s = off / 30.0
    if dist is not None:
        s += max(0.0, NEAR_M - dist) / 2.0 + max(0.0, dist - FAR_M) / 10.0
    return s + max(0, now - year) / 6.0 if year else s + 3.0


@dataclass
class Choice:
    bench_id: int
    image_id: int
    key: str  # "<source>:<pano_id>", as the explorer names candidates
    bearing: float
    facing: float
    aim: float


def choose(imgs: list[dict], facing: float | None, bench_id: int) -> Choice | None:
    """The camera for a bench's scenic view, or None.

    Among aimed views with a confirmed target (gate tier 0), unblocked and not
    vetoed, standing behind or beside the bench: the one looking most nearly
    along the facing, newest panorama first on ties."""
    from bench_finder.publish.build import _angle, target_gate

    if facing is None:
        return None
    best: tuple | None = None
    for i in imgs:
        if i.get("kind") != "aimed" or i.get("occluded") or i.get("vetoed"):
            continue
        if target_gate(i)[0] != 0 or i.get("camera_bearing_deg") is None:
            continue
        src = SOURCE_KEY.get(i.get("image_source") or "")
        if not src or not i.get("pano_id"):
            continue
        b = float(i["camera_bearing_deg"])
        off = _angle(b, facing)
        if off > MAX_OFF_FACING_DEG:
            continue
        rank = scenic_score(
            off, i.get("camera_distance_m"), int((i.get("pano_date") or "0")[:4] or 0)
        )
        if best is None or rank < best[0]:
            best = (rank, i, src, b)
    if best is None:
        return None
    _, i, src, b = best
    return Choice(
        bench_id, i["id"], f"{src}:{i['pano_id']}", b, facing, scenic_aim(b, facing)
    )


def to_43(view: np.ndarray, width: int) -> Image.Image:
    """Square render -> 4:3 landscape: trim the sky more than the ground."""
    im = Image.fromarray(view)
    w, h = im.size
    hh = int(w * 3 / 4)
    # Bottom edge ~35 degrees below the horizon: lower shows the city camera
    # car's roof (bench 1743). The 4:3 window sits a little toward the sky.
    top = int((h - hh) * CROP_TOP)
    im = im.crop((0, top, w, top + hh))
    return im.resize((width, width * 3 // 4), Image.LANCZOS) if w != width else im


def plan(db: str, images_root: Path, only: set[int] | None = None) -> list[Choice]:
    """A scenic camera for every published bench that has one."""
    from bench_finder.publish.build import COVERAGE_BBOX, select_images

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows, _, chosen = select_images(conn, images_root, True, bbox=COVERAGE_BBOX)
    facing = {r["id"]: _facing(r) for r in rows}
    source = dict(
        (r[0], r[1:])
        for r in conn.execute(
            "SELECT id, image_source, camera_distance_m FROM images WHERE kind = 'aimed'"
        )
    )
    out = []
    for bid, (imgs, _) in chosen.items():
        if only and bid not in only:
            continue
        for i in imgs:
            src, dist = source.get(i["id"], (None, None))
            i.setdefault("image_source", src)
            i.setdefault("camera_distance_m", dist)
        c = choose(imgs, facing.get(bid), bid)
        if c:
            out.append(c)
    return out


def _facing(r: sqlite3.Row) -> float | None:
    from bench_finder.publish.build import _rank_facing

    return _rank_facing(r)


async def render(ex, c: Choice, images_dir: Path) -> int:
    """Render, save (1024 and 2048 wide) and record one scenic view; its image id."""
    from bench_finder.core.streetview import _safe_name
    from bench_finder.explore import _needed_width
    from bench_finder.publish.images import hires_path

    await ex._bench(c.bench_id, 60)
    bench, cand = ex._cand(c.bench_id, c.key)
    p = await ex._pano(cand, _needed_width(FOV_DEG, HIRES_W))
    view = await asyncio.to_thread(ex._render, p, c.aim, FOV_DEG, TILT_DEG, HIRES_W)
    hires = await asyncio.to_thread(to_43, view, HIRES_W)  # raw: no tone treatment
    name = f"scenic_{c.bench_id}_{_safe_name(cand.pano_id)}.jpg"
    path = images_dir / name
    hp = hires_path(path)
    hp.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(hires.save, hp, "JPEG", quality=90)
    small = hires.resize((SAVE_W, SAVE_W * 3 // 4), Image.LANCZOS)
    await asyncio.to_thread(small.save, path, "JPEG", quality=90)
    return await asyncio.to_thread(_record, ex, bench, cand, c, path)


def _record(ex, bench, cand, c: Choice, path: Path) -> int:
    from bench_finder.core.pano_geometry import haversine_m
    from bench_finder.models.enums import ImageKind, ImageSource
    from bench_finder.models.unified_models import Image as ImageRow
    from bench_finder.services.database import BenchDatabase

    source = {
        "google": ImageSource.STREETVIEW_STREETLEVEL,
        "apple": ImageSource.APPLE_STREETLEVEL,
    }.get(cand.source, ImageSource.AMSTERDAM_PANORAMA)
    db = BenchDatabase(db_url=f"sqlite:///{ex.db}")
    with db.get_session() as s:
        row = (
            s.query(ImageRow)
            .filter(
                ImageRow.bench_candidate_id == c.bench_id,
                ImageRow.kind == ImageKind.SCENIC.value,
            )
            .first()
        ) or ImageRow(bench_candidate_id=c.bench_id)
        row.kind = ImageKind.SCENIC.value
        row.filepath = str(path)
        row.filename = path.name
        row.file_size = path.stat().st_size
        row.capture_success = True
        row.capture_error = None
        row.image_source = source
        row.panorama_lat, row.panorama_lng = cand.lat, cand.lon
        row.pano_id = cand.pano_id
        row.pano_date = cand.date_str
        row.heading = round(c.aim) % 360
        row.camera_bearing_deg = c.aim
        row.camera_distance_m = haversine_m(cand.lat, cand.lon, bench.lat, bench.lng)
        row.fov_deg = FOV_DEG
        row.pitch_deg = -TILT_DEG
        s.add(row)
        s.commit()
        s.refresh(row)
        return int(row.id or 0)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render scenic views")
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images", default="images")
    ap.add_argument("--bench", type=int, action="append")
    ap.add_argument("--limit", type=int)
    ap.add_argument(
        "--skip-done", action="store_true", help="Leave benches that have one"
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    from bench_finder.explore import Explorer

    choices = plan(args.db, Path(args.images), set(args.bench) if args.bench else None)
    if args.skip_done:
        conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        done = {
            r[0]
            for r in conn.execute(
                "SELECT bench_candidate_id FROM images WHERE kind = 'scenic'"
            )
        }
        choices = [c for c in choices if c.bench_id not in done]
    if args.limit:
        choices = choices[: args.limit]
    log.info("scenic views to render: %d", len(choices))
    ex = Explorer(args.db)
    ok = 0
    for n, c in enumerate(choices, 1):
        try:
            image_id = ex.run(render(ex, c, Path(args.images)))
            ok += 1
            log.info(
                "%d/%d bench %d -> image %d (aim %.0f, facing %.0f)",
                n,
                len(choices),
                c.bench_id,
                image_id,
                c.aim,
                c.facing,
            )
        except Exception as e:  # one bad panorama never stops the run
            log.warning("%d/%d bench %d failed: %s", n, len(choices), c.bench_id, e)
        finally:
            ex.cands.clear()
    log.info("done: %d of %d", ok, len(choices))


if __name__ == "__main__":
    main()
