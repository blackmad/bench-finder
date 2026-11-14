"""View-classifier bake-off (plan task 3.2) against the oracle gold set.

    uv run python -m bench_finder.bakeoff.views run --backend gemini --resolution medium
    uv run python -m bench_finder.bakeoff.views run --backend typesafe
    uv run python -m bench_finder.bakeoff.views score

``run`` classifies every gold image (annotator ``oracle:*``) that the variant has not
labelled yet, saving to ``image_annotations`` under the variant name (e.g.
``gemini-decision-1@medium``). ``score`` compares every variant with the gold labels.

Metrics (view_relation is scored only where gold is a direction, not ``unknown``):
- present_acc: bench_present agreement on all gold images.
- rel_acc: exact 8-way view_relation.
- within45: predicted direction at most one ring step (45 deg) from gold.
- mean_err: mean angular error in degrees (unknown predictions excluded, counted in coverage).
- coverage: share of gold-direction images where the model gave a direction.
- calib: mean stated view_relation confidence minus observed rel_acc (0 = calibrated).
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

from bench_finder.clients.view_classifier import (
    ViewContext,
    make_classifier,
    save_view_labels,
)
from bench_finder.labeling import store


if TYPE_CHECKING:
    import sqlite3

GOLD_LIKE = "oracle:%"
RING = [
    "front",
    "front-right",
    "right",
    "back-right",
    "back",
    "back-left",
    "left",
    "front-left",
]


def ring_steps(a: str, b: str) -> int | None:
    if a not in RING or b not in RING:
        return None
    d = abs(RING.index(a) - RING.index(b)) % 8
    return min(d, 8 - d)


def gold(conn: sqlite3.Connection) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    for r in conn.execute(
        "SELECT image_id, label_type, value FROM image_annotations WHERE annotator LIKE ?",
        (GOLD_LIKE,),
    ):
        out.setdefault(r[0], {})[r[1]] = json.loads(r[2])
    return out


def predictions(conn: sqlite3.Connection, annotator: str) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for r in conn.execute(
        "SELECT image_id, label_type, value, confidence FROM image_annotations WHERE annotator = ?",
        (annotator,),
    ):
        v = json.loads(r[2]) if isinstance(r[2], str) else r[2]
        out.setdefault(r[0], {})[r[1]] = (v, r[3])
    return out


def run(
    db: str,
    backend: str,
    resolution: str | None,
    limit: int | None,
    workers: int,
    images_root: Path,
    model: str | None = None,
) -> dict:
    conn = store.connect(db)
    kw = {"resolution": resolution} if backend == "gemini" and resolution else {}
    if model:
        kw["model"] = model
    clf = make_classifier(backend, **kw)
    local = (
        threading.local()
    )  # one client per thread: the genai client is not thread-safe
    variant = clf.model + (
        f"@{resolution}" if backend == "gemini" and resolution else ""
    )
    done = set(predictions(conn, variant))
    todo = [i for i in sorted(gold(conn)) if i not in done][:limit]
    paths = {i: store.image_path(conn, i, images_root) for i in todo}
    ok = err = 0
    t0 = time.time()

    def one(iid: int):
        if not hasattr(local, "clf"):
            local.clf = make_classifier(backend, **kw)
        lab = local.clf.classify(paths[iid], ViewContext(image_id=iid))
        lab.model = variant
        return iid, lab

    with ThreadPoolExecutor(workers) as pool:
        futs = [pool.submit(one, i) for i in todo if paths[i] is not None]
        for f in as_completed(futs):
            try:
                iid, lab = f.result()
                save_view_labels(conn, iid, lab)
                ok += 1
            except Exception as e:
                err += 1
                if err <= 5:
                    print(f"error: {e!r}"[:300])
    return {
        "variant": variant,
        "classified": ok,
        "errors": err,
        "seconds": round(time.time() - t0, 1),
    }


def score_variant(g: dict[int, dict[str, str]], p: dict[int, dict]) -> dict:
    ids = [i for i in g if i in p]
    present = [
        (g[i].get("bench_present") == "yes")
        == (p[i].get("bench_present", (None,))[0] == "yes")
        for i in ids
        if "bench_present" in g[i]
    ]
    rel = [i for i in ids if g[i].get("view_relation") in RING]
    exact = within = covered = 0
    errs: list[int] = []
    confs: list[float] = []
    for i in rel:
        pv, conf = p[i].get("view_relation", (None, None))
        steps = ring_steps(g[i]["view_relation"], pv) if pv else None
        if steps is None:
            continue
        covered += 1
        exact += steps == 0
        within += steps <= 1
        errs.append(steps * 45)
        if conf is not None:
            confs.append(conf)
    n = len(rel) or 1
    rel_acc = exact / n
    return {
        "n_images": len(ids),
        "present_acc": round(sum(present) / (len(present) or 1), 3),
        "n_dir": len(rel),
        "rel_acc": round(rel_acc, 3),
        "within45": round(within / n, 3),
        "mean_err": round(sum(errs) / (len(errs) or 1), 1),
        "coverage": round(covered / n, 3),
        "calib": round(sum(confs) / len(confs) - rel_acc, 3) if confs else None,
    }


def score(db: str) -> list[dict]:
    conn = store.connect(db)
    g = gold(conn)
    variants = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT annotator FROM image_annotations "
            "WHERE annotator NOT LIKE 'oracle:%' AND annotator NOT LIKE 'human:%'"
        )
    ]
    return [{"variant": v, **score_variant(g, predictions(conn, v))} for v in variants]


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--backend", required=True, choices=["gemini", "typesafe", "claude"])
    r.add_argument("--resolution", choices=["low", "medium", "high", "ultra_high"])
    r.add_argument("--limit", type=int)
    r.add_argument(
        "--model",
        help="claude backend: e.g. anthropic/claude-sonnet-5.5 via OpenRouter",
    )
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--images-root", type=Path, default=Path("images"))
    sub.add_parser("score")
    a = ap.parse_args()
    if a.cmd == "run":
        print(
            run(
                a.db,
                a.backend,
                a.resolution,
                a.limit,
                a.workers,
                a.images_root,
                a.model,
            )
        )
    else:
        for row in score(a.db):
            print(json.dumps(row))


if __name__ == "__main__":
    main()
