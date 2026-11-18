"""Is a bench public seating, or part of a café/shop terrace or a private garden?

Opus looks at each published hero (the red box marks the bench) and answers
``public`` / ``business`` / ``private``. Answers go to ``data/terrace.jsonl``
(cached by image id); ``exclude.excluded()`` hides benches marked business or
private (Hugo de Grootplein 8, 2026-11-18).

    uv run python -m bench_finder.terrace run --max-usd 35
"""

from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench_finder.vet_targets import Usage, _ask, _cached, heroes


CACHE = Path("data/terrace.jsonl")
MODEL = "claude-opus-5-5"
PROMPT = """The red rectangle marks a bench in a street-level photo from Amsterdam.
Is it public seating anyone may use (a city bench in a street, park, square or quay), or does it belong to a business (a café, bar, restaurant or shop terrace: their own chairs, tables, benches set out in front of the premises, often with umbrellas, menus or awnings) or a private home (a bench against a house front, in a front garden or behind a gate, clearly someone's own)?
Wooden benches against Amsterdam house fronts are usually the resident's own. Only answer business or private when the photo shows it; when unsure, answer public.
Answer JSON {"use": "public"|"business"|"private", "why": "<five words or fewer>"}"""


def hidden(cache: Path = CACHE) -> dict[int, str]:
    """Bench id -> 'business' or 'private' for benches Opus judged not public."""
    out = {}
    for r in _cached(cache).values():
        if r.get("use") in ("business", "private"):
            out[r["bench_id"]] = r["use"]
    return out


def run(
    db: str,
    images_root: Path,
    max_usd: float,
    ids: set[int] | None = None,
    workers: int = 6,
) -> dict:
    import anthropic

    done = _cached(CACHE)
    todo = [
        h
        for h in heroes(db, images_root)
        if h[1] not in done and (ids is None or h[0] in ids)
    ]
    client, usage, lock = anthropic.Anthropic(), Usage(), threading.Lock()
    stats = {"todo": len(todo), "asked": 0, "business": 0, "private": 0, "failed": 0}

    def one(h):
        bid, iid, path, box = h
        if usage.usd(MODEL) >= max_usd:
            return
        try:
            a = _ask(client, path, box, usage, MODEL, prompt=PROMPT)
        except Exception:
            with lock:
                stats["failed"] += 1
            return
        use = a.get("use") if a.get("use") in ("business", "private") else "public"
        rec = {"image_id": iid, "bench_id": bid, "use": use, "why": a.get("why")}
        with lock:
            with CACHE.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            stats["asked"] += 1
            stats[use] = stats.get(use, 0) + 1
            if stats["asked"] % 250 == 0:
                print(
                    f"{stats['asked']}/{len(todo)} ${usage.usd(MODEL):.2f}", flush=True
                )

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    return {**stats, "usd": round(usage.usd(MODEL), 2)}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    ap.add_argument("--max-usd", type=float, default=35.0)
    ap.add_argument("--ids", help="only these bench ids (a pilot)")
    a = ap.parse_args()
    ids = {int(x) for x in a.ids.split(",")} if a.ids else None
    print(run(a.db, a.images_root, a.max_usd, ids))


if __name__ == "__main__":
    main()
