"""Run the bake-off's primary detector (YOLO11x-seg, COCO "bench") on aimed views.

    uv run python -m bench_finder.detect_aimed [--bbox amsterdam|all] [--limit N]

Aimed views point at one bench, so the target is the detection that lines up with
the image's centre column (the bake-off's ``horizontal`` hit rule, radius 0.30:
the box spans the centre column or its centre x is within 0.30 x width of it).
The bench usually sits below the image centre, so height is ignored.

One ``detections`` row per image (``model_id = MODEL_ID``, ``source = ULTRALYTICS``):
``has_bench`` = a target hit at >= THRESHOLD, ``max_confidence`` = the best target
hit's confidence (0 if none). Every box >= 0.05 goes to ``detection_items`` with
``is_target`` set. Images that already have a row for MODEL_ID are skipped.
Bake-off result (task 2.7, 882 oracle gold images): P .98 / R .75 at 0.25.

``--model sam3`` runs SAM 3 (text prompt "bench", ~1.8 s/image on MPS) instead,
at threshold 0.6 (bake-off: P .98 / R .84); used to pick hero images. Needs
``uv run --group detect-extra``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from bench_finder.publish.build import AMSTERDAM_BBOX


MODEL_ID = "yolo11x-seg"
THRESHOLD = 0.25
THRESHOLDS = {"yolo11x-seg": 0.25, "sam3": 0.6}
FLOOR = 0.05
RADIUS = 0.30
BENCH_CLASS = 13  # COCO "bench"


def is_target(x1: float, x2: float, width: float, radius: float = RADIUS) -> bool:
    cx = width / 2
    return x1 <= cx <= x2 or abs((x1 + x2) / 2 - cx) <= radius * width


def todo_images(
    conn: sqlite3.Connection,
    bbox: tuple[float, float, float, float] | None,
    model_id: str = MODEL_ID,
) -> list[tuple[int, str]]:
    where = ""
    params: list = [model_id]
    if bbox:
        where = "AND c.lng BETWEEN ? AND ? AND c.lat BETWEEN ? AND ?"
        params += [bbox[0], bbox[2], bbox[1], bbox[3]]
    # SAM 3 leaves views yolo11x-seg already confirmed (same precision, 0.98).
    skip = (
        "AND NOT EXISTS (SELECT 1 FROM detections y JOIN detection_items yi "
        "ON yi.detection_id = y.id WHERE y.image_id = i.id AND y.model_id = "
        f"'{MODEL_ID}' AND yi.is_target = 1 AND yi.confidence >= {THRESHOLDS[MODEL_ID]})"
        if model_id == "sam3"
        else ""
    )
    return conn.execute(
        f"""SELECT i.id, i.filepath FROM images i
            JOIN bench_candidates c ON c.id = i.bench_candidate_id
            WHERE i.kind = 'aimed' AND i.capture_success = 1 AND i.filepath IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM detections d WHERE d.image_id = i.id AND d.model_id = ?)
              {skip}
              {where}
            ORDER BY i.id""",
        params,
    ).fetchall()


def verify_images(
    conn: sqlite3.Connection,
    bbox: tuple[float, float, float, float] | None,
    per_bench: int = 3,
) -> list[tuple[int, str]]:
    """Views yolo11x-seg alone calls a target, for SAM 3 to confirm: the best
    ``per_bench`` per bench, only for benches without a SAM 3-confirmed view.
    yolo11x-seg alone may not pick a hero (it reads the camera car's roof
    rack, gratings and planters as benches in wide views)."""
    where, params = "", []
    if bbox:
        where = "AND c.lng BETWEEN ? AND ? AND c.lat BETWEEN ? AND ?"
        params = [bbox[0], bbox[2], bbox[1], bbox[3]]
    return conn.execute(
        f"""WITH y AS (
              SELECT i.id, i.filepath, i.bench_candidate_id b, MAX(yi.confidence) conf
              FROM images i JOIN bench_candidates c ON c.id = i.bench_candidate_id
              JOIN detections d ON d.image_id = i.id AND d.model_id = '{MODEL_ID}'
              JOIN detection_items yi ON yi.detection_id = d.id AND yi.is_target = 1
                   AND yi.confidence >= {THRESHOLDS[MODEL_ID]}
              WHERE i.kind = 'aimed' AND i.capture_success = 1 {where}
                AND NOT EXISTS (SELECT 1 FROM detections s
                                WHERE s.image_id = i.id AND s.model_id = 'sam3')
              GROUP BY i.id),
            ok AS (
              SELECT DISTINCT i.bench_candidate_id b FROM images i
              JOIN detections d ON d.image_id = i.id AND d.model_id = 'sam3'
              JOIN detection_items si ON si.detection_id = d.id AND si.is_target = 1
                   AND si.confidence >= {THRESHOLDS["sam3"]}),
            r AS (SELECT y.*, ROW_NUMBER() OVER (PARTITION BY b ORDER BY conf DESC) rn
                  FROM y WHERE b NOT IN (SELECT b FROM ok))
            SELECT id, filepath FROM r WHERE rn <= ? ORDER BY b, rn""",
        [*params, per_bench],
    ).fetchall()


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    ap.add_argument("--weights", default="models/yolo11x-seg.pt")
    ap.add_argument("--bbox", default="amsterdam")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--model", choices=sorted(THRESHOLDS), default=MODEL_ID)
    ap.add_argument(
        "--verify-only",
        action="store_true",
        help="only SAM 3 on yolo-only target views",
    )
    a = ap.parse_args()

    model_id = a.model
    bbox = AMSTERDAM_BBOX if a.bbox == "amsterdam" else None
    conn = sqlite3.connect(a.db, timeout=120)  # other jobs write too
    if a.verify_only:
        a.model = "sam3"
        _detect(conn, verify_images(conn, bbox)[: a.limit], "sam3", a)
        return
    if model_id == "sam3":
        # Easy views first: yolo11x-seg (14x faster) on views it hasn't seen;
        # SAM 3 then skips views where it already found the target bench.
        _detect(conn, todo_images(conn, bbox, MODEL_ID)[: a.limit], MODEL_ID, a)
    _detect(conn, todo_images(conn, bbox, model_id)[: a.limit], model_id, a)
    if model_id == "sam3":
        # yolo11x-seg alone can't pick a hero: SAM 3 checks its best views.
        _detect(conn, verify_images(conn, bbox)[: a.limit], model_id, a)


def _detect(conn: sqlite3.Connection, rows: list, model_id: str, a) -> None:
    threshold = THRESHOLDS[model_id]
    if model_id == "sam3":
        from bench_finder.bakeoff.detectors import MODELS

        sam = MODELS["sam3"]
        sam.load(Path(a.weights).parent, a.device)
        a.batch = 1
    else:
        from ultralytics import YOLO

        model = YOLO(a.weights)
    t0, hits, done = time.time(), 0, 0
    for start in range(0, len(rows), a.batch):
        chunk = []
        for iid, fp in rows[start : start + a.batch]:
            p = Path(fp)
            p = p if p.is_absolute() else (Path.cwd() / p)
            if not p.is_file():
                p = a.images_root / Path(fp).name
            if p.is_file():
                chunk.append((iid, p))
        if not chunk:
            continue
        if model_id == "sam3":
            from PIL import Image

            iid, p = chunk[0]
            with Image.open(p) as im:
                w = im.width
            dets = [d for d in sam.detect(p) if d.conf >= FLOOR]
            results = [
                (
                    w,
                    [(d.conf, [d.x1, d.y1, d.x2, d.y2]) for d in dets],
                    [d.poly for d in dets],
                )
            ]
        else:
            results = [
                (
                    res.orig_shape[1],
                    [
                        (float(b.conf), [float(v) for v in b.xyxy[0].tolist()])
                        for b in res.boxes
                    ],
                    # yolo11x-seg outlines too (0..1), kept for the hero fade
                    [
                        [(round(float(x), 4), round(float(y), 4)) for x, y in xy]
                        for xy in res.masks.xyn
                    ]
                    if res.masks is not None
                    else [None] * len(res.boxes),
                )
                for res in model.predict(
                    [str(p) for _, p in chunk],
                    conf=FLOOR,
                    classes=[BENCH_CLASS],
                    device=a.device,
                    verbose=False,
                )
            ]
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
        for (iid, _), (width, boxes, polys) in zip(chunk, results, strict=True):
            targets = [c for c, (x1, _, x2, _) in boxes if is_target(x1, x2, width)]
            best = max(targets, default=0.0)
            has = best >= threshold
            hits += has
            cur = conn.execute(
                "INSERT INTO detections (image_id, has_bench, bench_count, max_confidence, detections, "
                "detection_success, model_id, confidence_threshold, source, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'ULTRALYTICS', ?)",
                (
                    iid,
                    has,
                    sum(c >= threshold for c, _ in boxes),
                    best,
                    json.dumps([{"conf": c, "xyxy": xy} for c, xy in boxes]),
                    model_id,
                    threshold,
                    now,
                ),
            )
            # Outlines (SAM 3 and yolo11x-seg, 0..1 coordinates) are kept for the hero fade.
            conn.executemany(
                "INSERT INTO detection_items (detection_id, confidence, bbox, class_name, created_at, "
                "is_target, polygon) VALUES (?, ?, ?, 'bench', ?, ?, ?)",
                [
                    (
                        cur.lastrowid,
                        c,
                        json.dumps(
                            dict(zip(("x1", "y1", "x2", "y2"), xy, strict=True))
                        ),
                        now,
                        is_target(xy[0], xy[2], width),
                        json.dumps(polys[k]) if polys and polys[k] else None,
                    )
                    for k, (c, xy) in enumerate(boxes)
                ],
            )
            done += 1
        conn.commit()
        if (start // a.batch) % (50 if a.batch > 1 else 200) == 0:
            print(
                f"{done}/{len(rows)} images, {hits} with target, {time.time() - t0:.0f}s",
                flush=True,
            )
    print(f"done: {done} images, {hits} with target bench, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
