"""Production view labelling with Gemini Flash-Lite, and fusion into bench_attributes.

    uv run python -m bench_finder.label_views run --max-usd 3
    uv run python -m bench_finder.label_views fuse

``run`` labels every photo where the aimed-at bench was detected (sam3 >= 0.6 when
sam3 ran, else yolo11x-seg >= 0.25) with the 8-way view relation, bench type and what
the bench looks at (``faces_category``). Benches are done whole, fewest-labelled first,
so a budget cap leaves complete benches rather than scattered photos. Labels go to
``image_annotations`` under ``ANNOTATOR``.

``fuse`` combines each bench's labels (``bench_finder.facing.fuse_views``) into
``bench_attributes``: looks-at, bench type and the VLM facing (an OSM ``direction``
tag wins). The hero is left to the publish ranking, which reads the same labels.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from bench_finder.clients.view_classifier import (
    Usage,
    ViewContext,
    make_classifier,
    save_view_labels,
)
from bench_finder.facing import ViewInput, fuse_views, write_bench_attributes
from bench_finder.labeling import store


MODEL = "gemini-3.1-flash-lite"
ANNOTATOR = f"{MODEL}@v2"  # v2 = the 8 looks-at categories
SAM3_MIN, YOLO_MIN = 0.6, 0.25

GATED_SQL = """
WITH t AS (
  SELECT d.image_id, d.model_id,
         MAX(CASE WHEN di.is_target = 1 THEN di.confidence ELSE 0 END) AS c
  FROM detections d LEFT JOIN detection_items di ON di.detection_id = d.id
  WHERE d.detection_success = 1 AND d.model_id IN ('sam3', 'yolo11x-seg')
  GROUP BY d.image_id, d.model_id)
SELECT i.id, i.bench_candidate_id FROM images i
WHERE EXISTS (SELECT 1 FROM t WHERE t.image_id = i.id AND t.model_id = 'sam3' AND t.c >= ?)
   OR (NOT EXISTS (SELECT 1 FROM t WHERE t.image_id = i.id AND t.model_id = 'sam3')
       AND EXISTS (SELECT 1 FROM t WHERE t.image_id = i.id
                   AND t.model_id = 'yolo11x-seg' AND t.c >= ?))
ORDER BY i.bench_candidate_id, i.id
"""


class BudgetExceededError(RuntimeError):
    pass


def gated_images(conn, sam3_only: bool = False) -> list[tuple[int, int]]:
    """(image_id, bench_candidate_id) for photos where the target bench was detected.

    ``sam3_only``: only photos sam3 has confirmed (skips yolo-only photos that sam3
    has not reached yet, which it rejects ~40% of the time).
    """
    return conn.execute(
        GATED_SQL, (SAM3_MIN, 2.0 if sam3_only else YOLO_MIN)
    ).fetchall()


def labelled(conn, annotator: str = ANNOTATOR) -> set[int]:
    return {
        r[0]
        for r in conn.execute(
            "SELECT image_id FROM image_annotations WHERE annotator = ? "
            "AND label_type = 'view_relation'",
            (annotator,),
        )
    }


def plan(conn, sam3_only: bool = False) -> list[int]:
    """Unlabelled gated images, whole benches at a time, smallest benches first."""
    done = labelled(conn)
    benches: dict[int, list[int]] = {}
    for iid, cid in gated_images(conn, sam3_only):
        if iid not in done:
            benches.setdefault(cid, []).append(iid)
    return [
        i
        for _, imgs in sorted(benches.items(), key=lambda kv: len(kv[1]))
        for i in imgs
    ]


def hero_plan(conn, db: str, images_root: Path) -> list[int]:
    """Published heroes (publish ranking) that this labeller has not seen yet."""
    from bench_finder.recut import connect_ro, hero_image_ids

    heroes = hero_image_ids(connect_ro(db), images_root, include_unclassified=True)
    done = labelled(conn)
    return [i for i in heroes if i not in done]


def run(
    db: str,
    max_usd: float,
    workers: int,
    images_root: Path,
    limit: int | None,
    sam3_only: bool = False,
    heroes: bool = False,
) -> dict:
    conn = store.connect(db)
    conn.execute("PRAGMA busy_timeout = 120000")  # detection jobs write too
    todo = (hero_plan(conn, db, images_root) if heroes else plan(conn, sam3_only))[
        :limit
    ]
    paths = {i: store.image_path(conn, i, images_root) for i in todo}
    usage, local, lock = Usage(), threading.local(), threading.Lock()

    def one(iid: int):
        if usage.usd(MODEL) >= max_usd:
            raise BudgetExceededError
        if not hasattr(local, "clf"):
            local.clf = make_classifier("google", model=MODEL, usage=usage)
        lab = local.clf.classify(paths[iid], ViewContext(image_id=iid))
        lab.model = ANNOTATOR
        return iid, lab

    ok = err = skipped = 0
    t0 = time.time()
    with ThreadPoolExecutor(workers) as pool:
        futs = [pool.submit(one, i) for i in todo if paths[i] is not None]
        for n, f in enumerate(as_completed(futs), 1):
            try:
                iid, lab = f.result()
                with lock:
                    save_view_labels(conn, iid, lab)
                ok += 1
            except BudgetExceededError:
                skipped += 1
            except Exception as e:
                err += 1
                if err <= 5:
                    print(f"error: {e!r}"[:300], flush=True)
            if n % 250 == 0:
                print(f"{n}/{len(futs)} done, ${usage.usd(MODEL):.2f}", flush=True)
    return {
        "planned": len(todo),
        "classified": ok,
        "errors": err,
        "skipped_budget": skipped,
        "usd": round(usage.usd(MODEL), 3),
        "usd_per_image": round(usage.usd(MODEL) / ok, 5) if ok else None,
        "seconds": round(time.time() - t0),
    }


def _load(v):
    """Stored JSON; numbers come back from SQLite already decoded."""
    return json.loads(v) if isinstance(v, str) and v else v


def fuse(db: str, annotator: str = ANNOTATOR) -> dict:
    conn = store.connect(db)
    conn.execute("PRAGMA busy_timeout = 120000")
    rows = conn.execute(
        "SELECT a.image_id, i.bench_candidate_id, i.camera_bearing_deg, i.pano_id, "
        "a.label_type, a.value, a.confidence FROM image_annotations a "
        "JOIN images i ON i.id = a.image_id WHERE a.annotator = ?",
        (annotator,),
    ).fetchall()
    per: dict[int, dict] = {}
    for iid, cid, bearing, pano, lt, val, conf in rows:
        d = per.setdefault(iid, {"cid": cid, "bearing": bearing, "pano": pano})
        d[lt] = (_load(val), conf)
    views: dict[int, list[ViewInput]] = {}
    for iid, d in per.items():
        g = lambda k, d=d: d.get(k, (None, None))  # noqa: E731
        q = g("quality")[0]
        views.setdefault(d["cid"], []).append(
            ViewInput(
                image_id=iid,
                camera_bearing_deg=d["bearing"],
                view_relation=g("view_relation")[0] or "unknown",
                quality=float(q) if isinstance(q, (int, float)) else 1.0,
                confidence=g("view_relation")[1],
                bench_type=g("bench_type")[0],
                bench_visible=g("bench_present")[0] == "yes",
                occluded=g("occluded")[0] in (True, "yes"),
                faces_category=g("faces_category")[0],
                faces_text=g("faces_text")[0],
                pano_id=d["pano"],
            )
        )
    tags = {
        cid: _load(t) or {}
        for cid, t in conn.execute("SELECT id, tags FROM bench_candidates")
    }
    n = faces = 0
    for cid, vs in views.items():
        fused = fuse_views(vs, osm_direction=tags.get(cid, {}).get("direction"))
        fused.hero_image_id = None  # the publish ranking picks the hero
        write_bench_attributes(conn, cid, fused)
        n += 1
        faces += fused.faces_category is not None
    return {"benches": n, "with_looks_at": faces}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-usd", type=float, required=True)
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--limit", type=int)
    r.add_argument("--images-root", type=Path, default=Path("images"))
    r.add_argument("--sam3-only", action="store_true")
    r.add_argument(
        "--heroes", action="store_true", help="only published heroes not yet labelled"
    )
    p = sub.add_parser("plan", help="how many photos/benches are left to label")
    p.add_argument("--sam3-only", action="store_true")
    sub.add_parser("fuse")
    a = ap.parse_args()
    if a.cmd == "run":
        print(
            run(
                a.db,
                a.max_usd,
                a.workers,
                a.images_root,
                a.limit,
                a.sam3_only,
                a.heroes,
            )
        )
    elif a.cmd == "plan":
        conn = store.connect(a.db)
        todo = set(plan(conn, a.sam3_only))
        cids = {c for i, c in gated_images(conn, a.sam3_only) if i in todo}
        print({"photos": len(todo), "benches": len(cids)})
    else:
        print(fuse(a.db))


if __name__ == "__main__":
    main()
