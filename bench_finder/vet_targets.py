"""Second opinion on hero photos: is the box SAM 3 called the bench really a bench?

SAM 3 at >= 0.6 is right ~98% of the time, but the misses become hero photos: the
camera car's roof rack, gratings, railings, utility boxes.

NOT IN USE (2026-11-17). Gold views (10 SAM 3 false positives, 80 real benches):
Flash-Lite full frame caught 5/10, vetoed 0/40; zoomed 1/10 and 2/80; 3.8 Flash
full 5/10 and 2/80, zoomed 1/10 and 3/80. But on production heroes Flash-Lite
vetoed 6 of 70 (9%) where ~2% are wrong, so most vetoes would drop real benches.
Next to try: a Claude model (the gold labels are Claude Opus's); needs
ANTHROPIC_API_KEY. Don't ``apply`` without a precision check on production views.

``run`` vets each bench's current hero (as ``publish`` would choose it), caching
verdicts in ``data/vet_targets.jsonl`` (no database writes, so it can run beside
the pipeline). Rerun after ``apply`` to vet the heroes that replace vetoed ones.
``apply`` stores the verdicts as ``image_annotations`` (``target_is_bench``),
which ``publish`` reads: a vetoed view is never the hero.

    uv run python -m bench_finder.vet_targets run --max-usd 8
    uv run python -m bench_finder.vet_targets apply
"""

from __future__ import annotations

import argparse
import io
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw

from bench_finder.clients.view_classifier import Usage
from bench_finder.publish.build import AMSTERDAM_BBOX, select_images


MODEL = "gemini-3.1-flash-lite"
ANNOTATOR = f"{MODEL}@box1"
CACHE = Path("data/vet_targets.jsonl")
PROMPT = """The red rectangle marks what a detector thinks is a bench. The photo comes from a street-level camera on a car or boat, so the camera vehicle's own roof, bonnet, roof rack or deck can appear at the bottom.
Is the object inside the red rectangle really a bench (a seat for people: park bench, street bench, picnic table bench, seating block)?
Answer JSON {"is_bench": true|false, "what": "<two or three words>"}"""


def _cached(cache: Path = CACHE) -> dict[int, dict]:
    if not cache.exists():
        return {}
    out = {}
    for line in cache.read_text().splitlines():
        r = json.loads(line)
        out[r["image_id"]] = r
    return out


def heroes(db: str, images_root: Path) -> list[tuple[int, int, Path, dict]]:
    """(bench id, image id, path, box) of each bench's hero as publish picks it."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        _, _, chosen = select_images(
            conn,
            images_root,
            include_unclassified=True,
            bbox=AMSTERDAM_BBOX,
            gallery_size=1,
        )
        paths = dict(
            conn.execute("SELECT id, filepath FROM images WHERE kind = 'aimed'")
        )
    finally:
        conn.close()
    out = []
    for bid, (imgs, has_hero) in chosen.items():
        if not has_hero:
            continue
        img = imgs[0]
        t = (img.get("targets") or {}).get("sam3")
        if t and t[1] and paths.get(img["id"]):
            out.append((bid, img["id"], Path(paths[img["id"]]), t[1]))
    return out


def _ask(
    client, path: Path, box: dict, usage: Usage, model: str = MODEL, zoom: bool = False
) -> dict:
    im = Image.open(path).convert("RGB")
    x1, y1, x2, y2 = (float(box[k]) for k in ("x1", "y1", "x2", "y2"))
    # Zoom in: a box a few pixels wide in the whole frame is a guess. Keep
    # context round it (3x the box, at least a third of the frame).
    side = max(3 * max(x2 - x1, y2 - y1), im.width / 3) if zoom else max(im.size)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    left = min(max(0.0, cx - side / 2), max(0.0, im.width - side))
    top = min(max(0.0, cy - side / 2), max(0.0, im.height - side))
    crop = (left, top, min(im.width, left + side), min(im.height, top + side))
    im = im.crop(crop)
    k = 768 / max(im.size)
    im = im.resize((round(im.width * k), round(im.height * k)))
    ImageDraw.Draw(im).rectangle(
        [(x1 - left) * k, (y1 - top) * k, (x2 - left) * k, (y2 - top) * k],
        outline=(255, 0, 0),
        width=4,
    )
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    resp = client.models.generate_content(
        model=model,
        contents=[
            {
                "role": "user",
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": buf.getvalue(),
                        }
                    },
                    {"text": PROMPT},
                ],
            }
        ],
        config={"response_mime_type": "application/json", "temperature": 0.0},
    )
    um = resp.usage_metadata
    usage.add(um.prompt_token_count or 0, um.candidates_token_count or 0)
    a = json.loads(resp.text)
    return a[0] if isinstance(a, list) else a


def run(db: str, images_root: Path, max_usd: float, workers: int = 8) -> dict:
    from google import genai

    import bench_finder.config  # noqa: F401 - loads .env

    done = _cached()
    todo = [h for h in heroes(db, images_root) if h[1] not in done]
    client, usage, lock = genai.Client(), Usage(), threading.Lock()
    stats = {"todo": len(todo), "vetted": 0, "not_bench": 0, "failed": 0}

    def one(h):
        bid, iid, path, box = h
        if usage.usd(MODEL) >= max_usd:
            return
        try:
            a = _ask(client, path, box, usage)
        except Exception:
            with lock:
                stats["failed"] += 1
            return
        rec = {
            "image_id": iid,
            "bench_id": bid,
            "is_bench": a.get("is_bench") is not False,
            "what": a.get("what"),
        }
        with lock:
            with CACHE.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            stats["vetted"] += 1
            stats["not_bench"] += not rec["is_bench"]
            if stats["vetted"] % 500 == 0:
                print(
                    f"{stats['vetted']}/{len(todo)} ${usage.usd(MODEL):.2f}", flush=True
                )

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    return {**stats, "usd": round(usage.usd(MODEL), 3)}


def apply(db: str) -> dict:
    conn = sqlite3.connect(db, timeout=120)
    now = datetime.now(UTC).isoformat()
    n = 0
    for iid, r in _cached().items():
        conn.execute(
            "DELETE FROM image_annotations WHERE image_id = ? AND annotator = ? "
            "AND label_type = 'target_is_bench'",
            (iid, ANNOTATOR),
        )
        conn.execute(
            "INSERT INTO image_annotations (image_id, annotator, label_type, value, "
            "confidence, created_at) VALUES (?, ?, 'target_is_bench', ?, NULL, ?)",
            (iid, ANNOTATOR, json.dumps("yes" if r["is_bench"] else "no"), now),
        )
        n += 1
    conn.commit()
    conn.close()
    return {"applied": n}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-usd", type=float, default=8.0)
    r.add_argument("--workers", type=int, default=8)
    sub.add_parser("apply")
    a = ap.parse_args()
    if a.cmd == "run":
        print(run(a.db, a.images_root, a.max_usd, a.workers))
    else:
        print(apply(a.db))


if __name__ == "__main__":
    main()
