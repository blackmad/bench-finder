"""Backfill yolo11x-seg outlines for detections stored before outlines were kept.

``detect_aimed`` saved only boxes for yolo11x-seg until 2026-11-17. This re-runs
the same weights on those images (deterministic: same boxes) and writes each
stored box's outline (0..1 polygon) into ``detection_items.polygon``, matching
boxes by IoU. Resumable: only items with no polygon are touched.

    uv run python -m bench_finder.yolo_masks [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

from bench_finder.detect_aimed import BENCH_CLASS, FLOOR


TODO = """SELECT DISTINCT d.image_id, i.filepath FROM detections d
JOIN detection_items di ON di.detection_id = d.id
JOIN images i ON i.id = d.image_id
WHERE d.model_id = 'yolo11x-seg' AND di.polygon IS NULL ORDER BY d.image_id"""
MIN_IOU = 0.9


def iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def main() -> None:
    from ultralytics import YOLO

    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    ap.add_argument("--weights", default="models/yolo11x-seg.pt")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    conn = sqlite3.connect(a.db, timeout=120)
    rows = conn.execute(TODO).fetchall()[: a.limit]
    model = YOLO(a.weights)
    t0, filled, missed = time.time(), 0, 0
    for start in range(0, len(rows), a.batch):
        chunk = []
        for iid, fp in rows[start : start + a.batch]:
            p = Path(fp) if fp else None
            if not (p and p.is_file()) and fp:
                p = a.images_root / Path(fp).name
            if p and p.is_file():
                chunk.append((iid, p))
        if not chunk:
            continue
        preds = model.predict(
            [str(p) for _, p in chunk],
            conf=FLOOR,
            classes=[BENCH_CLASS],
            device=a.device,
            verbose=False,
        )
        updates = []
        for (iid, _), res in zip(chunk, preds, strict=True):
            if res.masks is None:
                continue
            boxes = [[float(v) for v in b.xyxy[0].tolist()] for b in res.boxes]
            polys = [
                [(round(float(x), 4), round(float(y), 4)) for x, y in xy]
                for xy in res.masks.xyn
            ]
            for item_id, bbox in conn.execute(
                "SELECT di.id, di.bbox FROM detection_items di JOIN detections d "
                "ON d.id = di.detection_id WHERE d.image_id = ? AND "
                "d.model_id = 'yolo11x-seg' AND di.polygon IS NULL",
                (iid,),
            ):
                b = json.loads(bbox)
                stored = [b["x1"], b["y1"], b["x2"], b["y2"]]
                best = max(
                    range(len(boxes)), key=lambda k: iou(stored, boxes[k]), default=None
                )
                if (
                    best is not None
                    and iou(stored, boxes[best]) >= MIN_IOU
                    and polys[best]
                ):
                    updates.append((json.dumps(polys[best]), item_id))
                else:
                    missed += 1
        conn.executemany("UPDATE detection_items SET polygon = ? WHERE id = ?", updates)
        conn.commit()
        filled += len(updates)
        if (start // a.batch) % 50 == 0:
            done = start + len(chunk)
            print(
                f"{done}/{len(rows)} images, {filled} outlines, {missed} unmatched, "
                f"{(time.time() - t0) / max(done, 1):.2f}s/img",
                flush=True,
            )
    print(f"done: {filled} outlines, {missed} unmatched, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
