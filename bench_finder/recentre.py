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
import os
import random
import shutil
from pathlib import Path

from bench_finder import recut
from bench_finder.coverage import COVERAGE_BBOX
from bench_finder.publish.images import CENTRED_DIRNAME


BOX_SHARE = 0.38  # bench width as a share of the frame width
BOX_Y = 0.64  # where the bench's centre lands, as a share of the height from the top
FOV_MIN, FOV_MAX = 35.0, 90.0
TILT_MIN, TILT_MAX = -5.0, 25.0
DETECTED_PX = 1024  # detections ran on the 1024 px originals
EDGE_PX = 6  # a box this close to the left/right edge is probably cut off
EDGE_ROUNDS = 2  # re-renders to try for a bench still cut off

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


def target_boxes(conn, image_ids: list[int], min_conf: float = 0.0) -> dict[int, dict]:
    """Best target box per image: sam3 when it has one, else yolo11x-seg.

    ``min_conf`` drops images whose best box is less sure than that.
    """
    best: dict[int, tuple[tuple[int, float], dict]] = {}
    for i in range(0, len(image_ids), 500):
        chunk = image_ids[i : i + 500]
        q = TARGET_SQL.format(",".join("?" * len(chunk)))
        for iid, model, bbox, conf in conn.execute(q, chunk):
            key = (model == "sam3", conf or 0.0)
            if iid not in best or key > best[iid][0]:
                best[iid] = (key, json.loads(bbox))
    return {iid: b for iid, ((_, c), b) in best.items() if c >= min_conf}


def edge_side(box: dict, size: float = DETECTED_PX) -> int:
    """-1 / +1 when the box touches the left / right edge (both: the wider gap), else 0."""
    x1, x2 = sorted((box["x1"], box["x2"]))
    left, right = (
        x1 <= EDGE_PX * size / DETECTED_PX,
        x2 >= size - EDGE_PX * size / DETECTED_PX,
    )
    if left and right:
        return 0  # wider than the frame already: widening is all we can do
    return -1 if left else (1 if right else 0)


def extend(box: dict, side: int, factor: float) -> dict:
    """The box stretched past the edge it touches by ``factor`` times its width."""
    x1, x2 = sorted((box["x1"], box["x2"]))
    w = (x2 - x1) * factor
    return {**box, "x1": x1 - w if side < 0 else x1, "x2": x2 + w if side > 0 else x2}


def recentred_job(job: recut.RecutJob, box: dict) -> recut.RecutJob:
    yaw, tilt, fov = frame_for_box(box, job.fov_deg)
    return dataclasses.replace(
        job,
        aim_bearing_deg=(job.aim_bearing_deg + yaw) % 360,
        fov_deg=fov,
        tilt_deg=tilt,
    )


def _hero_jobs(
    db: str, images_root: Path, min_conf: float = 0.0
) -> tuple[list[recut.RecutJob], dict[int, dict]]:
    conn = recut.connect_ro(db)
    heroes = recut.hero_image_ids(
        conn, images_root, include_unclassified=True, bbox=COVERAGE_BBOX
    )
    boxes = target_boxes(conn, heroes, min_conf)
    jobs = []
    for row in recut.load_rows(conn, [i for i in heroes if i in boxes]):
        try:
            jobs.append(recut.job_from_row(row))
        except ValueError:
            continue
    return jobs, boxes


def run_all(
    db: str,
    images_root: Path,
    min_conf: float,
    concurrency: int,
    bench: int | None = None,
) -> dict:
    """Re-aim every hero with a sure target box into ``images/centred`` (publish prefers it).

    ``bench``: only that candidate's hero (e.g. a newly reported bench)."""
    jobs, boxes = _hero_jobs(db, images_root, min_conf)
    if bench is not None:
        jobs = [j for j in jobs if j.bench_id == bench]
    out = images_root / CENTRED_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    new = [recentred_job(j, boxes[j.image_id]) for j in jobs]
    results = asyncio.run(recut.run(new, out, concurrency=concurrency))
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {
        "heroes_with_box": len(jobs),
        **counts,
        **fix_edges(jobs, boxes, out, concurrency),
    }


def _target_in(path: Path, yolo) -> dict | None:
    """The bench nearest the centre column of a rendered hero, by YOLO."""
    res = yolo.predict(str(path), conf=0.25, classes=[13], device=os.getenv("TORCH_DEVICE", "mps"), verbose=False)[
        0
    ]
    w = res.orig_shape[1]
    best = None
    for b in res.boxes:
        x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
        d = abs((x1 + x2) / 2 - w / 2)
        if best is None or d < best[0]:
            best = (d, {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": w})
    return best[1] if best else None


def fix_edges(
    jobs: list[recut.RecutJob], boxes: dict[int, dict], out: Path, concurrency: int
) -> dict:
    """Re-render heroes whose bench box touches a side of the frame (cut off):
    stretch the box past that edge, re-aim and widen, check again with YOLO."""
    from ultralytics import YOLO

    yolo = YOLO("models/yolo11x-seg.pt")
    todo = {j.image_id: (j, edge_side(boxes[j.image_id])) for j in jobs}
    todo = {i: js for i, js in todo.items() if js[1]}
    stats = {"edge_cut": len(todo), "edge_fixed": 0}
    for rnd in range(1, EDGE_ROUNDS + 1):
        if not todo:
            break
        new = []
        for j, side in todo.values():
            new.append(recentred_job(j, extend(boxes[j.image_id], side, rnd)))
            recut.output_path(out, j).unlink(missing_ok=True)  # re-render in place
        asyncio.run(recut.run(new, out, concurrency=concurrency))
        still = {}
        for i, (j, side) in todo.items():
            path = recut.output_path(out, j)
            t = _target_in(path, yolo) if path.is_file() else None
            if t and edge_side(t, t["w"]) == 0:
                stats["edge_fixed"] += 1
            else:
                still[i] = (j, side)
        todo = still
    stats["edge_still_cut"] = len(todo)
    return stats


def pilot(db: str, images_root: Path, out: Path, n: int, seed: int) -> dict:
    jobs, boxes = _hero_jobs(db, images_root)
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
    r = sub.add_parser("run", help="re-aim every hero into images/centred")
    r.add_argument("--min-conf", type=float, default=0.5)
    r.add_argument("--concurrency", type=int, default=1)
    r.add_argument("--bench", type=int, help="only this candidate's hero")
    a = ap.parse_args()
    if a.cmd == "run":
        print(run_all(a.db, a.images_root, a.min_conf, a.concurrency, a.bench))
    else:
        print(pilot(a.db, a.images_root, a.out, a.n, a.seed))


if __name__ == "__main__":
    main()
