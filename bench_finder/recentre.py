"""Re-aim hero photos at the detected bench (plan 6.x, pilot).

Aimed views point at the OSM pin, so the bench is often off to one side and low
in the frame. The target detection box says where it really is; this turns the
virtual camera towards it, tilts down so the bench sits in the lower part of the
frame with what it looks at above, and widens or narrows the view so the bench
fills about ``BOX_SHARE`` of the width. Then it re-renders from the panorama via
``recut`` at 2048 px.

    uv run python -m bench_finder.recentre pilot --n 50
    open data/centring_pilot/index.html
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import math
import random
import shutil
from pathlib import Path

from bench_finder import recut


BOX_SHARE = 0.38  # bench width as a share of the frame width
BOX_Y = 0.64  # where the bench's centre lands, as a share of the height from the top
FOV_MIN, FOV_MAX = 35.0, 90.0
TILT_MIN, TILT_MAX = -5.0, 25.0
DETECTED_PX = 1024  # detections ran on the 1024 px originals

TARGET_SQL = """
SELECT d.image_id, d.model_id, di.bbox, di.confidence FROM detections d
JOIN detection_items di ON di.detection_id = d.id
WHERE di.is_target = 1 AND d.detection_success = 1
  AND d.model_id IN ('sam3', 'yolo11x-seg') AND d.image_id IN ({})
"""


def frame_for_box(
    box: dict, fov_deg: float, size: int = DETECTED_PX
) -> tuple[float, float, float]:
    """(yaw offset °, tilt °, new FOV °) that frame ``box`` (pixels in a ``size`` view)."""
    c = (size - 1) / 2
    f = c / math.tan(math.radians(fov_deg) / 2)
    x1, x2 = sorted((box["x1"], box["x2"]))
    y1, y2 = sorted((box["y1"], box["y2"]))
    yaw = math.degrees(math.atan(((x1 + x2) / 2 - c) / f))
    below = math.degrees(math.atan(((y1 + y2) / 2 - c) / f))  # below the horizon
    width = math.degrees(math.atan((x2 - c) / f) - math.atan((x1 - c) / f))
    fov = min(max(width / BOX_SHARE, FOV_MIN), FOV_MAX)
    # Angle below the new optical axis where BOX_Y puts the bench.
    want = math.degrees(math.atan((2 * BOX_Y - 1) * math.tan(math.radians(fov) / 2)))
    tilt = min(max(below - want, TILT_MIN), TILT_MAX)
    return yaw, tilt, fov


def target_boxes(conn, image_ids: list[int]) -> dict[int, dict]:
    """Best target box per image: sam3 when it has one, else yolo11x-seg."""
    best: dict[int, tuple[tuple[int, float], dict]] = {}
    for i in range(0, len(image_ids), 500):
        chunk = image_ids[i : i + 500]
        q = TARGET_SQL.format(",".join("?" * len(chunk)))
        for iid, model, bbox, conf in conn.execute(q, chunk):
            key = (model == "sam3", conf or 0.0)
            if iid not in best or key > best[iid][0]:
                best[iid] = (key, json.loads(bbox))
    return {iid: b for iid, (_, b) in best.items()}


def recentred_job(job: recut.RecutJob, box: dict) -> recut.RecutJob:
    yaw, tilt, fov = frame_for_box(box, job.fov_deg)
    return dataclasses.replace(
        job,
        aim_bearing_deg=(job.aim_bearing_deg + yaw) % 360,
        fov_deg=fov,
        tilt_deg=tilt,
    )


def pilot(db: str, images_root: Path, out: Path, n: int, seed: int) -> dict:
    conn = recut.connect_ro(db)
    heroes = recut.hero_image_ids(conn, images_root, include_unclassified=True)
    boxes = target_boxes(conn, heroes)
    rows = recut.load_rows(conn, [i for i in heroes if i in boxes])
    jobs = []
    for row in rows:
        try:
            jobs.append(recut.job_from_row(row))
        except ValueError:
            continue
    random.Random(seed).shuffle(jobs)
    jobs = jobs[:n]
    (out / "after").mkdir(parents=True, exist_ok=True)
    (out / "before").mkdir(parents=True, exist_ok=True)
    new = [recentred_job(j, boxes[j.image_id]) for j in jobs]
    results = asyncio.run(recut.run(new, out / "after", concurrency=1))
    ok = {r.job.image_id for r in results if r.status in ("done", "skipped")}
    cards = []
    for old, j in zip(jobs, new, strict=True):
        if j.image_id not in ok:
            continue
        name = Path(j.filename).name
        src = images_root / "hires" / name
        shutil.copyfile(
            src if src.exists() else images_root / name, out / "before" / name
        )
        cards.append(
            f"<figure><div><img src='before/{name}'><img src='after/{name}'></div>"
            f"<figcaption>bench {j.bench_id} · image {j.image_id} · "
            f"turn {((j.aim_bearing_deg - old.aim_bearing_deg + 180) % 360 - 180):+.0f}° · "
            f"tilt {j.tilt_deg:.0f}° · fov {old.fov_deg:.0f}→{j.fov_deg:.0f}°"
            f"</figcaption></figure>"
        )
    (out / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Centring pilot</title><style>"
        "body{font:14px system-ui;margin:16px;background:#eee}"
        "figure{margin:0 0 20px}figure div{display:flex;gap:8px}"
        "img{width:min(48vw,520px);aspect-ratio:1;object-fit:cover}"
        "</style><h1>Centring pilot: before (left) / after (right)</h1>"
        + "".join(cards)
    )
    return {"planned": len(jobs), "rendered": len(ok), "page": str(out / "index.html")}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", type=Path, default=Path("data/centring_pilot"))
    a = ap.parse_args()
    print(pilot(a.db, a.images_root, a.out, a.n, a.seed))


if __name__ == "__main__":
    main()
