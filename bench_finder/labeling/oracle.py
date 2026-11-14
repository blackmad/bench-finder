"""Model-as-oracle gold labelling: export task files, import the answers.

The owner chose to have a strong model (Claude, run as Claude Code subagents,
not through the API) label the gold set instead of labelling it by hand.

    uv run python -m bench_finder.labeling.oracle export --n 300 --shards 6 --out DIR
    uv run python -m bench_finder.labeling.oracle import DIR/answers-*.jsonl

Export writes ``DIR/shard-K.json``: a list of benches in the labelling tool's
stratified queue order (OSM ``direction`` benches first, then balanced over
distance bucket and source), each with its images' absolute paths and the
metadata a labeller sees. Answers are JSON lines
``{"image_id": int, "labels": {label_type: value}}`` using the store's CHOICES.
They are saved under annotator ``oracle:<model>`` so they never mix with
``human:*`` labels; ``export_gold(conn, path, "oracle:%")`` exports them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_finder.labeling import store


DEFAULT_ANNOTATOR = "oracle:claude-opus-5-5"


def export_tasks(
    db: str,
    images_root: Path,
    n: int,
    shards: int,
    out: Path,
    seed: int = 0,
    per_bench: int = 4,
) -> dict[str, int]:
    """Only aimed views (``images.kind = 'aimed'``), at most ``per_bench`` each."""
    conn = store.connect(db)
    aimed = {r[0] for r in conn.execute("SELECT id FROM images WHERE kind = 'aimed'")}
    order = store.build_queue(conn, seed=seed)["order"]
    benches = []
    for cid in order:
        if len(benches) >= n:
            break
        bench = store.get_bench(conn, cid)
        if bench is None:
            continue
        images = []
        for img in bench["images"]:
            if img["image_id"] not in aimed or len(images) >= per_bench:
                continue
            path = store.image_path(conn, img["image_id"], images_root)
            if path is None:
                continue
            images.append(
                {
                    "image_id": img["image_id"],
                    "path": str(path.resolve()),
                    "image_source": img["image_source"],
                    "camera_bearing_deg": img["camera_bearing_deg"],
                    "distance_m": img["distance_m_est"],
                }
            )
        if images:
            benches.append(
                {
                    "bench_id": cid,
                    "osm_direction": bench["direction"],
                    "tags": bench["tags"],
                    "images": images,
                }
            )
    out.mkdir(parents=True, exist_ok=True)
    for k in range(shards):
        (out / f"shard-{k}.json").write_text(json.dumps(benches[k::shards], indent=1))
    return {"benches": len(benches), "images": sum(len(b["images"]) for b in benches)}


def import_answers(db: str, files: list[Path], annotator: str) -> dict[str, int]:
    conn = store.connect(db)
    counts = {"images": 0, "rows": 0, "errors": 0}
    for f in files:
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                counts["rows"] += store.save_labels(
                    conn, int(rec["image_id"]), rec["labels"], annotator=annotator
                )
                counts["images"] += 1
            except (ValueError, KeyError, TypeError) as e:
                counts["errors"] += 1
                print(f"{f.name}: skipped {line[:80]!r}: {e}")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--images-root", type=Path, default=Path("images"))
    ex.add_argument("--n", type=int, default=300)
    ex.add_argument("--shards", type=int, default=6)
    ex.add_argument("--seed", type=int, default=0)
    ex.add_argument("--per-bench", type=int, default=4)
    ex.add_argument("--out", type=Path, required=True)
    im = sub.add_parser("import")
    im.add_argument("files", type=Path, nargs="+")
    im.add_argument("--annotator", default=DEFAULT_ANNOTATOR)
    a = ap.parse_args()
    if a.cmd == "export":
        print(
            export_tasks(a.db, a.images_root, a.n, a.shards, a.out, a.seed, a.per_bench)
        )
    else:
        print(import_answers(a.db, a.files, a.annotator))


if __name__ == "__main__":
    main()
