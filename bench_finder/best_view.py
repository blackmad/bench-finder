"""Opus picks the clearest photo of each bench from its top candidate views.

The ranking rules (target gate, sitter's view, box size) still choose rear views
through advertising columns and benches half hidden by people. Here Opus sees
up to four candidate views side by side (the red box marks the bench SAM 3
found) and names the one that shows the bench best. Picks go to
``data/best_view.jsonl``; publish ranks a picked view first after the owner's
own picks.

    uv run python -m bench_finder.best_view run --limit 40 --max-usd 2   # pilot
    uv run python -m bench_finder.best_view run --max-usd 150
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import random
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bench_finder.publish.build import COVERAGE_BBOX, select_images, target_gate
from bench_finder.vet_targets import Usage


CACHE = Path("data/best_view.jsonl")
MODEL = "claude-opus-5-5"
MAX_VIEWS = 4
TILE = 512
LETTERS = "ABCD"
PROMPT = """These are {n} street-level photos (labelled {letters}) of the same public bench in Amsterdam, taken from different spots. A red rectangle marks where a detector found the bench in each.
Which photo would best show someone what this bench looks like and where it is? Prefer, in order: the whole bench clearly visible and not blocked by people, cars, posts, columns or plants; the bench reasonably large in the frame; a sharp, well-lit photo. Ignore which side the bench is seen from.
If a red rectangle is not on a bench at all, that photo cannot win. If none of the photos shows a bench, answer "none".
Answer JSON {{"best": "<letter or none>", "why": "<six words or fewer>"}}"""


def cached(cache: Path = CACHE) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if cache.exists():
        for line in cache.read_text().splitlines():
            r = json.loads(line)
            out[r["bench_id"]] = r
    return out


def picked_images(cache: Path = CACHE) -> set[int]:
    """Image ids Opus chose, for benches whose pick is still among the candidates."""
    return {r["best"] for r in cached(cache).values() if r.get("best")}


def candidates(db: str, images_root: Path) -> dict[int, list[tuple[int, Path, dict]]]:
    """Bench id -> its top hero-worthy views (id, file, SAM 3 box), best-ranked first."""
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
    for bid, (imgs, has_hero) in chosen.items():
        if not has_hero:
            continue
        views = []
        for img in imgs:
            gate, _, box = target_gate(img)
            if gate < 1 and box and paths.get(img["id"]):
                views.append((img["id"], Path(paths[img["id"]]), box))
            if len(views) == MAX_VIEWS:
                break
        if len(views) > 1:
            out[bid] = views
    return out


def sheet(views: list[tuple[int, Path, dict]]) -> bytes:
    """The views side by side (2x2), each with its box and a big letter."""
    cols = 2
    rows = (len(views) + 1) // 2
    out = Image.new("RGB", (cols * TILE, rows * TILE), "white")
    try:
        font = ImageFont.truetype("Helvetica.ttc", 56)
    except OSError:
        font = ImageFont.load_default()
    for k, (_, path, box) in enumerate(views):
        im = Image.open(path).convert("RGB")
        sx, sy = TILE / im.width, TILE / im.height
        im = im.resize((TILE, TILE))
        d = ImageDraw.Draw(im)
        d.rectangle(
            [box["x1"] * sx, box["y1"] * sy, box["x2"] * sx, box["y2"] * sy],
            outline=(255, 0, 0),
            width=4,
        )
        d.rectangle([0, 0, 70, 70], fill="white")
        d.text((14, 4), LETTERS[k], fill="black", font=font)
        out.paste(im, ((k % cols) * TILE, (k // cols) * TILE))
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def ask(client, views, usage: Usage) -> dict:
    letters = ", ".join(LETTERS[: len(views)])
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
                        "text": PROMPT.format(n=len(views), letters=letters)
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

    done = cached()
    todo = [
        (bid, v)
        for bid, v in candidates(db, images_root).items()
        # redo a bench when its candidate set changed since it was asked
        if bid not in done or done[bid]["images"] != [i for i, _, _ in v]
    ]
    if limit:
        todo = random.Random(11).sample(todo, min(limit, len(todo)))
    client, usage, lock = anthropic.Anthropic(), Usage(), threading.Lock()
    stats = {"todo": len(todo), "asked": 0, "kept": 0, "changed": 0, "none": 0}
    stats["failed"] = 0

    def one(item):
        bid, views = item
        if usage.usd(MODEL) >= max_usd:
            return
        try:
            a = ask(client, views, usage)
        except Exception:
            with lock:
                stats["failed"] += 1
            return
        letter = str(a.get("best", "")).strip().upper()[:1]
        k = LETTERS.find(letter) if letter else -1
        best = views[k][0] if 0 <= k < len(views) else None
        rec = {
            "bench_id": bid,
            "images": [i for i, _, _ in views],
            "best": best,
            "why": a.get("why"),
        }
        with lock:
            with CACHE.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            stats["asked"] += 1
            stats["none" if best is None else "kept" if k == 0 else "changed"] += 1
            if stats["asked"] % 250 == 0:
                print(f"{stats} ${usage.usd(MODEL):.2f}", flush=True)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    return {**stats, "usd": round(usage.usd(MODEL), 2)}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    ap.add_argument("--max-usd", type=float, default=150.0)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    print(run(a.db, a.images_root, a.max_usd, a.limit))


if __name__ == "__main__":
    main()
