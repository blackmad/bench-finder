"""Benches with their back to the water: undo the water snap where Opus sees it.

``water_facing.apply`` turns every bench tagged ``faces_category = water`` toward
the nearest water edge, whatever the vision model's facing said. Where the model
said the opposite (135-180 degrees off) it is often a flipped estimate, but some
benches sit against a quay wall with the canal behind the backrest (Hoofdweg
131, owner report 2026-11-19). A sample of 12 such benches: about half faced
the water, at least one had it behind.

Here Opus sees up to four views of each such bench (red box on the bench) and
says whether a sitter looks out over the water or has it behind them, and if
behind, what they do look at. Verdicts go to ``data/water_back.jsonl``.
``apply`` turns "behind" benches straight away from the water edge (method
``water_back``) and sets what they face; ``water_facing.apply`` skips them.

    uv run python -m bench_finder.water_back run --limit 30 --max-usd 2   # pilot
    uv run python -m bench_finder.water_back run --max-usd 20
    uv run python -m bench_finder.water_back apply [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from bench_finder.best_view import LETTERS, MAX_VIEWS, sheet
from bench_finder.clients.view_classifier import Usage
from bench_finder.publish.build import COVERAGE_BBOX, select_images, target_gate


CACHE = Path("data/water_back.jsonl")
MODEL = "claude-opus-5-5"
FLIP_DEG = 135.0
CATEGORIES = ("street", "park", "square", "wall", "playground", "other")
PROMPT = """These are {n} street-level photos (labelled {letters}) of the same public bench in Amsterdam, by a canal or other water. A red rectangle marks the bench in each.
Picture someone sitting normally on this bench, back against the backrest. Is the water in front of them (they look out over it), behind them (behind the backrest, e.g. the bench stands against a quay wall or railing with the canal at its back), off to one side, or is there no water near the bench in these photos?
If the water is not in front, also say what the sitter does look at: one of street, park, square, wall, playground, other, and a few words.
Answer JSON {{"water": "front|behind|side|none|unclear", "looks_at": "<category or null>", "text": "<four words or fewer, or null>", "why": "<eight words or fewer>"}}"""


def cached(cache: Path = CACHE) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if cache.exists():
        for line in cache.read_text().splitlines():
            r = json.loads(line)
            out[r["bench_id"]] = r
    return out


def behind(cache: Path = CACHE) -> set[int]:
    """Benches Opus says have the water at their back."""
    return {b for b, r in cached(cache).items() if r.get("water") == "behind"}


def flipped(conn: sqlite3.Connection) -> list[tuple[int, float]]:
    """(bench id, the model's own facing) where the water snap reversed it, for
    benches with a backrest (a backless bench can be sat either way)."""
    return conn.execute(
        "SELECT w.bench_candidate_id, w.old_facing FROM water_facing w "
        "JOIN bench_attributes a ON a.bench_candidate_id = w.bench_candidate_id "
        "WHERE w.old_method = 'vlm' AND a.facing_method = 'water_edge' AND NOT a.axis_only "
        "AND abs(((w.new_facing - w.old_facing) % 360 + 540) % 360 - 180) >= ?",
        (FLIP_DEG,),
    ).fetchall()


def views_for(db: str, images_root: Path, ids: set[int]) -> dict[int, list]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        _, _, chosen = select_images(
            conn, images_root, include_unclassified=True, bbox=COVERAGE_BBOX
        )
        paths = dict(conn.execute("SELECT id, filepath FROM images"))
    finally:
        conn.close()
    out = {}
    for bid in ids:
        views = []
        for img in chosen.get(bid, ([], False))[0]:
            gate, _, box = target_gate(img)
            if gate < 1 and box and paths.get(img["id"]):
                views.append((img["id"], Path(paths[img["id"]]), box))
            if len(views) == MAX_VIEWS:
                break
        if views:
            out[bid] = views
    return out


def ask(client, views, usage: Usage) -> dict:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64.b64encode(sheet(views)).decode(),
                        },
                    },
                    {
                        "type": "text",
                        "text": PROMPT.format(
                            n=len(views), letters=", ".join(LETTERS[: len(views)])
                        )
                        + "\nReply with the JSON only.",
                    },
                ],
            }
        ],
    )
    usage.add(msg.usage.input_tokens, msg.usage.output_tokens)
    text = "".join(b.text for b in msg.content if b.type == "text")
    return json.loads(text[text.index("{") : text.rindex("}") + 1])


def run(
    db: str,
    images_root: Path,
    max_usd: float,
    limit: int | None = None,
    workers: int = 6,
) -> dict:
    import anthropic

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    ids = {b for b, _ in flipped(conn)}
    conn.close()
    done = cached()
    views = views_for(db, images_root, ids - set(done))
    todo = sorted(views.items())
    if limit:
        todo = random.Random(5).sample(todo, min(limit, len(todo)))
    client, usage, lock = anthropic.Anthropic(), Usage(), threading.Lock()
    stats = {"flipped": len(ids), "no_views": len(ids - set(done)) - len(views)}
    stats |= {"todo": len(todo), "asked": 0, "failed": 0}

    def one(item):
        bid, vs = item
        if usage.usd(MODEL) >= max_usd:
            return
        try:
            a = ask(client, vs, usage)
        except Exception:
            with lock:
                stats["failed"] += 1
            return
        rec = {"bench_id": bid, "images": [i for i, _, _ in vs]} | {
            k: a.get(k) for k in ("water", "looks_at", "text", "why")
        }
        with lock:
            with CACHE.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            stats["asked"] += 1
            stats[str(rec["water"])] = stats.get(str(rec["water"]), 0) + 1

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    return {**stats, "usd": round(usage.usd(MODEL), 2)}


def apply(db: str, dry_run: bool) -> dict:
    """Behind-the-back benches face straight away from the water edge (the snap
    reversed; method ``water_back``) and get what Opus says they look at. A
    visitor's facing (``human``) is never touched."""
    conn = sqlite3.connect(db, timeout=120)
    snap = dict(
        conn.execute(
            "SELECT w.bench_candidate_id, w.new_facing FROM water_facing w "
            "JOIN bench_attributes a ON a.bench_candidate_id = w.bench_candidate_id "
            "WHERE a.facing_method IN ('vlm', 'water_edge', 'water_back')"
        )
    )
    verdicts = cached()
    now = datetime.now(UTC).isoformat()
    n = 0
    for bid in sorted(behind() & set(snap)):
        v = verdicts[bid]
        cat = v.get("looks_at") if v.get("looks_at") in CATEGORIES else "other"
        n += 1
        if dry_run:
            continue
        conn.execute(
            "UPDATE bench_attributes SET facing_deg = ?, facing_confidence = 0.6, "
            "facing_method = 'water_back', faces_category = ?, faces_text = ?, updated_at = ? "
            "WHERE bench_candidate_id = ?",
            (round((snap[bid] + 180) % 360, 1), cat, v.get("text"), now, bid),
        )
    conn.commit()
    conn.close()
    return {"backs_to_water": n, "dry_run": dry_run}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("cmd", choices=["run", "apply"])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    ap.add_argument("--max-usd", type=float, default=20.0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "run":
        print(run(a.db, a.images_root, a.max_usd, a.limit))
    else:
        print(apply(a.db, a.dry_run))


if __name__ == "__main__":
    main()
