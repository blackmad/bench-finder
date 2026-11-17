"""Fade each hero photo slightly outside the bench, using SAM 3's outline.

``masks`` runs SAM 3 on every published hero exactly as it is published (the
re-aimed render where one exists), picks the bench the photo is aimed at (sure,
and near where the framing puts it), and keeps its outline in ``hero_masks``.
``fade`` writes ``images/faded/<name>``: outside the (slightly grown, feathered)
outline the photo is mixed a little towards the paper colour and desaturated.
Publish prefers ``faded/`` over every other source, so a re-publish ships it.

    uv run --group detect-extra python -m bench_finder.hero_fade masks
    uv run python -m bench_finder.hero_fade fade
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from bench_finder import recut
from bench_finder.publish.images import FADED_DIRNAME, render_source


EXPECT = (0.5, 0.62)  # where the framing usually puts the bench (0..1)
MIN_CONF = 0.3
GROW = 0.012  # grow the outline by this share of the width
FEATHER = 0.022  # blur radius of the edge, share of the width
PAPER = (251, 248, 241)
MIX = 0.32  # how far outside pixels move towards paper
DESAT = 0.55  # saturation kept outside

SCHEMA = """CREATE TABLE IF NOT EXISTS hero_masks (
  image_id INTEGER PRIMARY KEY, source TEXT NOT NULL, polygon TEXT NOT NULL,
  confidence REAL, created_at TEXT)"""


def pick(dets) -> object | None:
    """The aimed-at bench: confidence weighted by nearness to EXPECT."""
    best, score = None, 0.0
    for d in dets:
        if d.conf < MIN_CONF or not d.poly:
            continue
        xs = [p[0] for p in d.poly]
        ys = [p[1] for p in d.poly]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        dist2 = (cx - EXPECT[0]) ** 2 + (cy - EXPECT[1]) ** 2
        s = d.conf * math.exp(-dist2 / (2 * 0.22**2))
        if s > score:
            best, score = d, s
    return best


def _heroes(db: str, images_root: Path) -> list[tuple[int, Path]]:
    conn = recut.connect_ro(db)
    ids = recut.hero_image_ids(conn, images_root, include_unclassified=True)
    rows = recut.load_rows(conn, ids)
    conn.close()  # an open read transaction would block this job's own writes
    out = []
    for r in rows:
        original = images_root / Path(r["filepath"]).name
        src = render_source(original, faded=False)
        if src.is_file():
            out.append((r["id"], src))
    return out


def masks(db: str, images_root: Path, limit: int | None) -> dict:
    import sqlite3

    from bench_finder.bakeoff.detectors import MODELS

    todo = _heroes(db, images_root)
    conn = sqlite3.connect(db, timeout=120)
    conn.execute(SCHEMA)
    # Done unless the image was re-rendered since (recentre's edge fix rewrites heroes).
    done = {
        (i, s): datetime.fromisoformat(t).timestamp()
        for i, s, t in conn.execute(
            "SELECT image_id, source, created_at FROM hero_masks"
        )
    }
    todo = [
        (i, p)
        for i, p in todo
        if (i, str(p)) not in done or p.stat().st_mtime > done[(i, str(p))]
    ][:limit]
    from types import SimpleNamespace

    from ultralytics import YOLO

    yolo = YOLO("models/yolo11x-seg.pt")
    sam = None  # loaded only when YOLO finds nothing: it is ~14x slower

    def yolo_dets(src: Path) -> list:
        res = yolo.predict(
            str(src), conf=0.05, classes=[13], device="mps", verbose=False
        )[0]
        if res.masks is None:
            return []
        return [
            SimpleNamespace(
                conf=float(b.conf), poly=[(float(x), float(y)) for x, y in xy]
            )
            for b, xy in zip(res.boxes, res.masks.xyn, strict=True)
        ]

    t0, found, by_sam = time.time(), 0, 0
    for n, (iid, src) in enumerate(todo, 1):
        d = pick(yolo_dets(src))
        if d is None:
            if sam is None:
                sam = MODELS["sam3"]
                sam.load(Path("models"), "mps")
            d = pick(sam.detect(src))
            by_sam += d is not None
        if d is not None:
            found += 1
            conn.execute(
                "INSERT OR REPLACE INTO hero_masks VALUES (?,?,?,?,?)",
                (
                    iid,
                    str(src),
                    json.dumps(d.poly),
                    d.conf,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        if n % 100 == 0:
            print(f"{n}/{len(todo)} {(time.time() - t0) / n:.1f}s/img", flush=True)
    return {"heroes": len(todo), "with_outline": found, "from_sam3": by_sam}


MASK_PX = 512  # the soft mask is built at this width, then scaled up


def fade_image(src: Path, poly: list, dst: Path) -> None:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    # Grow and feather at MASK_PX: a MaxFilter's cost grows with the square of
    # its size, and at 2048 px this took ~3 s an image. The edge is soft anyway.
    k = min(1.0, MASK_PX / w)
    mw, mh = max(1, round(w * k)), max(1, round(h * k))
    m = Image.new("L", (mw, mh), 0)
    ImageDraw.Draw(m).polygon([(x * mw, y * mh) for x, y in poly], fill=255)
    grow = max(1, int(GROW * mw)) | 1
    m = m.filter(ImageFilter.MaxFilter(min(grow * 2 + 1, 31)))
    m = m.filter(ImageFilter.GaussianBlur(FEATHER * mw))
    if (mw, mh) != (w, h):
        m = m.resize((w, h), Image.BILINEAR)
    outside = ImageEnhance.Color(im).enhance(DESAT)
    outside = Image.blend(outside, Image.new("RGB", (w, h), PAPER), MIX)
    out = Image.composite(im, outside, m)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, quality=92)


def _fade_one(job: tuple[str, str, str]) -> bool:
    source, poly, dst = job
    fade_image(Path(source), json.loads(poly), Path(dst))
    return True


def fade(db: str, images_root: Path) -> dict:
    """Fade every hero with an outline, in parallel; skips ones already faded
    after both the image and its outline were last written."""
    from concurrent.futures import ProcessPoolExecutor

    conn = recut.connect_ro(db)
    rows = conn.execute("SELECT source, polygon, created_at FROM hero_masks").fetchall()
    conn.close()
    jobs = []
    for source, poly, created in rows:
        src = Path(source)
        if not src.is_file():
            continue
        dst = images_root / FADED_DIRNAME / src.name
        newest = max(src.stat().st_mtime, datetime.fromisoformat(created).timestamp())
        if dst.is_file() and dst.stat().st_mtime > newest:
            continue
        jobs.append((source, poly, str(dst)))
    with ProcessPoolExecutor() as pool:
        n = sum(pool.map(_fade_one, jobs, chunksize=16))
    return {"faded": n, "already": len(rows) - len(jobs)}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("masks")
    m.add_argument("--limit", type=int)
    sub.add_parser("fade")
    a = ap.parse_args()
    if a.cmd == "masks":
        print(masks(a.db, a.images_root, a.limit))
    else:
        print(fade(a.db, a.images_root))


if __name__ == "__main__":
    main()
