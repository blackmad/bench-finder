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
    out = []
    for r in recut.load_rows(conn, ids):
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
    done = {(i, s) for i, s in conn.execute("SELECT image_id, source FROM hero_masks")}
    todo = [(i, p) for i, p in todo if (i, str(p)) not in done][:limit]
    sam = MODELS["sam3"]
    sam.load(Path("models"), "mps")
    t0, found = time.time(), 0
    for n, (iid, src) in enumerate(todo, 1):
        d = pick(sam.detect(src))
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
    return {"heroes": len(todo), "with_outline": found}


def fade_image(src: Path, poly: list, dst: Path) -> None:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon([(x * w, y * h) for x, y in poly], fill=255)
    grow = max(1, int(GROW * w)) | 1
    m = m.filter(ImageFilter.MaxFilter(min(grow * 2 + 1, 31)))
    m = m.filter(ImageFilter.GaussianBlur(FEATHER * w))
    outside = ImageEnhance.Color(im).enhance(DESAT)
    outside = Image.blend(outside, Image.new("RGB", (w, h), PAPER), MIX)
    out = Image.composite(im, outside, m)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, quality=92)


def fade(db: str, images_root: Path) -> dict:
    conn = recut.connect_ro(db)
    rows = conn.execute("SELECT source, polygon FROM hero_masks").fetchall()
    n = 0
    for source, poly in rows:
        src = Path(source)
        if not src.is_file():
            continue
        fade_image(src, json.loads(poly), images_root / FADED_DIRNAME / src.name)
        n += 1
    return {"faded": n}


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
