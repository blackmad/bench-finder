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
from bench_finder.publish.images import FADED_DIRNAME, FRAMED_DIRNAME, render_source


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


FRAME_MIN_SHARE = 0.4  # zoom until the bench spans this share of the crop's width
FRAME_MIN_SIDE = 0.45  # but never crop below this share of the image (pixelation)
FRAME_RECUT_MIN_SIDE = 0.85  # a re-aimed cut is zoomed already: re-centre only
FRAME_OUT_PX = 800  # crops are scaled up to at least this (the largest rendition)


def frame_box(poly: list, recut: bool = False) -> tuple[float, float, float] | None:
    """(cx, cy, side) of a square crop, in shares of the image width/height, that
    centres the bench and zooms in on a small one; None when the full frame will do.

    ``recut``: the image is a ``recentre`` cut, which already zoomed in as far as
    the panorama's resolution allows; zooming again blurs it (Marnixstraat 256),
    so only a slight crop to centre the bench is allowed."""
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    bw, bh = max(xs) - min(xs), max(ys) - min(ys)
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    # Zoom for a small bench; tighten further so an off-centre bench can sit
    # mid-frame, but always keep the whole bench in.
    zoom = 1.0 if recut else bw / FRAME_MIN_SHARE
    want = min(1.0, zoom, 2 * min(mx, 1 - mx), 2 * min(my, 1 - my))
    floor = FRAME_RECUT_MIN_SIDE if recut else FRAME_MIN_SIDE
    side = min(1.0, max(floor, want, bw * 1.15, bh * 1.3))
    cx = min(max(mx, side / 2), 1 - side / 2)
    cy = min(max(my, side / 2), 1 - side / 2)
    if side >= 0.98 and abs(cx - 0.5) < 0.03 and abs(cy - 0.5) < 0.03:
        return None
    return cx, cy, side


def focus(poly: list, recut: bool = False) -> tuple[float, float]:
    """Where the bench's centre lands in the published (framed) hero, 0..1."""
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    fb = frame_box(poly, recut)
    if fb is None:
        return round(mx, 3), round(my, 3)
    cx, cy, side = fb
    return (
        round(min(1, max(0, (mx - cx) / side + 0.5)), 3),
        round(min(1, max(0, (my - cy) / side + 0.5)), 3),
    )


def is_recut(source: str) -> bool:
    """Is the outlined image a ``recentre`` cut (``images/centred/``)?"""
    return "/centred/" in source


def frame_image(src: Path, poly: list, dst: Path, recut_src: bool = False) -> bool:
    fb = frame_box(poly, recut_src)
    if fb is None:
        return False
    cx, cy, side = fb
    im = Image.open(src).convert("RGB")
    w, h = im.size
    s = side * min(w, h)
    box = (
        round(cx * w - s / 2),
        round(cy * h - s / 2),
        round(cx * w + s / 2),
        round(cy * h + s / 2),
    )
    out = im.crop(box)
    if out.width < FRAME_OUT_PX:
        out = out.resize((FRAME_OUT_PX, FRAME_OUT_PX), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, quality=92)
    return True


def _frame_one(job: tuple[str, str, str, bool]) -> bool:
    src, poly, dst, rc = job
    return frame_image(Path(src), json.loads(poly), Path(dst), rc)


def frame(db: str, images_root: Path) -> dict:
    """Crop every outlined hero (the faded one when there is one) around its bench."""
    from concurrent.futures import ProcessPoolExecutor

    conn = recut.connect_ro(db)
    rows = conn.execute("SELECT source, polygon FROM hero_masks").fetchall()
    conn.close()
    jobs = []
    for source, poly in rows:
        src = Path(source)
        faded = images_root / FADED_DIRNAME / src.name
        base = faded if faded.is_file() else src
        if not base.is_file():
            continue
        dst = images_root / FRAMED_DIRNAME / src.name
        if dst.is_file() and dst.stat().st_mtime > base.stat().st_mtime:
            continue
        dst.unlink(missing_ok=True)
        jobs.append((str(base), poly, str(dst), is_recut(source)))
    with ProcessPoolExecutor() as pool:
        n = sum(pool.map(_frame_one, jobs, chunksize=16))
    return {"framed": n, "full_frame": len(jobs) - n, "already": len(rows) - len(jobs)}


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
    sub.add_parser("frame")
    a = ap.parse_args()
    if a.cmd == "masks":
        print(masks(a.db, a.images_root, a.limit))
    elif a.cmd == "frame":
        print(frame(a.db, a.images_root))
    else:
        print(fade(a.db, a.images_root))


if __name__ == "__main__":
    main()
