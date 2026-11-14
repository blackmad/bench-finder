"""SQLite access for the labeling tool: queue, annotation upsert, export."""

from __future__ import annotations

import json
import math
import random
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ANNOTATOR = "human:owner"
CHOICES: dict[str, set[str]] = {
    "bench_present": {"yes", "no"},
    "target_box": {"yes", "no", "no_box"},
    "view_relation": {
        "front",
        "front-left",
        "left",
        "back-left",
        "back",
        "back-right",
        "right",
        "front-right",
        "unknown",
    },
    "bench_type": {"backrest", "backless", "picnic", "other"},
    "faces_category": {
        "water",
        "street",
        "park",
        "square",
        "wall",
        "playground",
        "other",
    },
}
DISTANCE_BUCKETS = ((8, "<8m"), (15, "8-15m"), (30, "15-30m"))


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def distance_bucket(distance_m: float | None) -> str:
    if distance_m is None:
        return "unknown"
    for limit, name in DISTANCE_BUCKETS:
        if distance_m < limit:
            return name
    return "30m+"


def parse_tags(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        tags = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return tags if isinstance(tags, dict) else {}


def image_distance(row: sqlite3.Row) -> float | None:
    """Camera-to-bench distance: stored value, else panorama position vs bench."""
    if row["camera_distance_m"] is not None:
        return row["camera_distance_m"]
    if row["panorama_lat"] is not None and row["panorama_lng"] is not None:
        return _haversine_m(
            row["lat"], row["lng"], row["panorama_lat"], row["panorama_lng"]
        )
    return None


_IMAGES_SELECT = """
SELECT i.id AS image_id, i.bench_candidate_id, i.filepath, i.heading, i.image_source,
       i.camera_bearing_deg, i.camera_distance_m, i.panorama_lat, i.panorama_lng,
       c.lat, c.lng, c.tags, c.source AS candidate_source,
       (SELECT MAX(d.max_confidence) FROM detections d WHERE d.image_id = i.id) AS best_conf
FROM images i JOIN bench_candidates c ON c.id = i.bench_candidate_id
WHERE i.capture_success = 1 AND i.filepath IS NOT NULL AND i.filepath != ''
"""
_IMAGES_ORDER = " ORDER BY i.bench_candidate_id, best_conf DESC, i.id"


def labeled_candidates(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute(
        "SELECT DISTINCT i.bench_candidate_id FROM image_annotations a "
        "JOIN images i ON i.id = a.image_id WHERE a.annotator = ?",
        (ANNOTATOR,),
    )
    return {r[0] for r in rows}


def build_queue(conn: sqlite3.Connection, seed: int = 0) -> dict[str, Any]:
    """Return ``{"order": [bench ids], "total": n, "labeled": n}``.

    One entry per bench. Benches with an OSM ``direction`` tag come first; within
    each group, benches are bucketed by (distance bucket, image_source) and the
    buckets are interleaved round-robin so any prefix is balanced. Benches that
    already have a human label are left out of ``order`` but counted in ``labeled``.
    """
    reps: dict[int, sqlite3.Row] = {}
    for row in conn.execute(_IMAGES_SELECT + _IMAGES_ORDER):
        reps.setdefault(row["bench_candidate_id"], row)  # first = best detection
    done = labeled_candidates(conn)
    rng = random.Random(seed)

    groups: dict[bool, dict[tuple[str, str], list[int]]] = {
        True: defaultdict(list),
        False: defaultdict(list),
    }
    for cid, row in reps.items():
        if cid in done:
            continue
        has_dir = bool(parse_tags(row["tags"]).get("direction"))
        key = (
            distance_bucket(image_distance(row)),
            row["image_source"] or row["candidate_source"],
        )
        groups[has_dir][key].append(cid)

    order: list[int] = []
    for has_dir in (True, False):
        strata = groups[has_dir]
        for ids in strata.values():
            ids.sort()
            rng.shuffle(ids)
        keys = sorted(strata)
        while any(strata[k] for k in keys):
            order.extend(strata[k].pop() for k in keys if strata[k])
    return {"order": order, "total": len(reps), "labeled": len(done & reps.keys())}


def _label_map(
    conn: sqlite3.Connection, image_ids: list[int]
) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = defaultdict(dict)
    if not image_ids:
        return out
    marks = ",".join("?" * len(image_ids))
    for r in conn.execute(
        "SELECT image_id, label_type, value FROM image_annotations "
        f"WHERE annotator = ? AND image_id IN ({marks})",
        (ANNOTATOR, *image_ids),
    ):
        out[r["image_id"]][r["label_type"]] = json.loads(r["value"])
    return out


def _boxes(conn: sqlite3.Connection, image_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT di.id, di.confidence, di.bbox, di.polygon, di.is_target, di.class_name "
        "FROM detection_items di JOIN detections d ON d.id = di.detection_id "
        "WHERE d.image_id = ? ORDER BY di.confidence DESC",
        (image_id,),
    )
    return [
        {
            "id": r["id"],
            "confidence": r["confidence"],
            "bbox": json.loads(r["bbox"]) if r["bbox"] else None,
            "polygon": json.loads(r["polygon"]) if r["polygon"] else None,
            "is_target": bool(r["is_target"]),
            "class_name": r["class_name"],
        }
        for r in rows
    ]


def get_bench(conn: sqlite3.Connection, candidate_id: int) -> dict[str, Any] | None:
    cand = conn.execute(
        "SELECT * FROM bench_candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    if cand is None:
        return None
    sql = _IMAGES_SELECT + " AND i.bench_candidate_id = ?" + _IMAGES_ORDER
    rows = list(conn.execute(sql, (candidate_id,)))
    labels = _label_map(conn, [r["image_id"] for r in rows])
    tags = parse_tags(cand["tags"])
    return {
        "bench_id": candidate_id,
        "source": cand["source"],
        "tags": {k: v for k, v in tags.items() if v is not None},
        "direction": tags.get("direction"),
        "images": [
            {
                "image_id": r["image_id"],
                "heading": r["heading"],
                "image_source": r["image_source"],
                "camera_bearing_deg": r["camera_bearing_deg"],
                "camera_distance_m": r["camera_distance_m"],
                "distance_m_est": image_distance(r),
                "boxes": _boxes(conn, r["image_id"]),
                "labels": labels.get(r["image_id"], {}),
            }
            for r in rows
        ],
    }


def image_path(
    conn: sqlite3.Connection, image_id: int, images_root: Path
) -> Path | None:
    """Resolve ``images.filepath`` (absolute, repo-relative, or under images_root)."""
    row = conn.execute(
        "SELECT filepath FROM images WHERE id = ?", (image_id,)
    ).fetchone()
    if row is None or not row["filepath"]:
        return None
    raw = Path(row["filepath"])
    root = images_root.resolve()
    candidates = (
        [raw]
        if raw.is_absolute()
        else [root.parent / raw, Path.cwd() / raw, root / raw]
    )
    candidates.append(root / raw.name)
    return next((p for p in candidates if p.is_file()), None)


def save_labels(
    conn: sqlite3.Connection,
    image_id: int,
    labels: dict[str, Any],
    annotator: str = ANNOTATOR,
) -> int:
    """Upsert one ``image_annotations`` row per label type; returns rows written."""
    if (
        conn.execute("SELECT 1 FROM images WHERE id = ?", (image_id,)).fetchone()
        is None
    ):
        raise ValueError(f"unknown image {image_id}")
    for label_type, value in labels.items():
        if label_type not in CHOICES:
            raise ValueError(f"unknown label_type {label_type!r}")
        if value is not None and value not in CHOICES[label_type]:
            raise ValueError(f"bad value {value!r} for {label_type}")
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
    written = 0
    for label_type, value in labels.items():
        if value is None:
            continue
        payload = json.dumps(value)
        cur = conn.execute(
            "UPDATE image_annotations SET value = ?, created_at = ? "
            "WHERE image_id = ? AND annotator = ? AND label_type = ?",
            (payload, now, image_id, annotator, label_type),
        )
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO image_annotations (image_id, annotator, label_type, value, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (image_id, annotator, label_type, payload, now),
            )
        written += 1
    conn.commit()
    return written


def export_gold(
    conn: sqlite3.Connection, out_path: str, annotator_like: str = "human:%"
) -> int:
    """Write one JSON line per labeled image (annotators matching ``annotator_like``)."""
    per_image: dict[tuple[int, str], dict[str, Any]] = {}
    for r in conn.execute(
        "SELECT a.image_id, a.annotator, a.label_type, a.value, a.created_at, "
        "i.bench_candidate_id, i.filepath, i.image_source, i.camera_bearing_deg, "
        "i.camera_distance_m, c.tags "
        "FROM image_annotations a JOIN images i ON i.id = a.image_id "
        "JOIN bench_candidates c ON c.id = i.bench_candidate_id "
        "WHERE a.annotator LIKE ? ORDER BY a.image_id, a.label_type",
        (annotator_like,),
    ):
        rec = per_image.setdefault(
            (r["image_id"], r["annotator"]),
            {
                "image_id": r["image_id"],
                "bench_id": r["bench_candidate_id"],
                "annotator": r["annotator"],
                "filepath": r["filepath"],
                "image_source": r["image_source"],
                "camera_bearing_deg": r["camera_bearing_deg"],
                "camera_distance_m": r["camera_distance_m"],
                "osm_direction": parse_tags(r["tags"]).get("direction"),
                "labels": {},
                "labeled_at": r["created_at"],
            },
        )
        rec["labels"][r["label_type"]] = json.loads(r["value"])
    with open(out_path, "w") as f:
        for rec in per_image.values():
            f.write(json.dumps(rec) + "\n")
    return len(per_image)
