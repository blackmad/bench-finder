"""Second opinion on hero photos: is the box SAM 3 called the bench really a bench?

SAM 3 at >= 0.6 is right ~98% of the time, but the misses become hero photos: the
camera car's roof rack, gratings, railings, utility boxes.

The general 'is it a bench?' veto is NOT IN USE (2026-11-17). Gold views (10 SAM 3 false positives, 80 real benches):
Flash-Lite full frame caught 5/10, vetoed 0/40; zoomed 1/10 and 2/80; 3.8 Flash
full 5/10 and 2/80, zoomed 1/10 and 3/80. But on production heroes Flash-Lite
vetoed 6 of 70 (9%) where ~2% are wrong, so most vetoes would drop real benches.
Claude (via ``ant auth login``), same question, full frame: Haiku 5.5 caught 8/10
but vetoed 20/80 real and 18/70 production heroes (people on a bench = "person");
Opus 5.5 (low effort) 3/10, 5/80, 3/70, and its 3 production vetoes, which
Flash-Lite shared, were all real benches (people on them, behind a hedge).
Conclusion: on views SAM 3 already confirmed, no model tried beats it; vetoes
drop more real benches than bad photos. Use visitor/owner feedback instead.

IN USE: ``rig`` asks Opus only whether the box is the camera vehicle (car roof,
roof rack, mount, boat deck), for city-panorama views with a box in the bottom
fifth: 3/5 of the owner's car examples, 0/40 real benches. Of 1,888 views it
flagged 22; the 12 with the box at the bottom edge were all the rig, the rest
mostly real benches, hence ``RIG_LOW`` 0.95. ``apply`` stores both.

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
A bench with people sitting on it, or partly hidden behind a bin or post, still counts as a bench.
Answer JSON {"is_bench": true|false, "what": "<two or three words>"}"""


RIG_CACHE = Path("data/vet_rig.jsonl")
RIG_MODEL = "claude-opus-5-5"
RIG_PROMPT = """This photo comes from a street-level panorama camera mounted on a vehicle (a car or a boat). Parts of that vehicle often show at the bottom of the frame: the car's roof, bonnet, roof rack, camera mast or mount, or the boat's deck and railing.
A detector marked the red rectangle as a bench. Is the object in the red rectangle part of the camera vehicle itself (rather than something out in the street, such as a bench)?
Answer JSON {"is_bench": <true if it is NOT part of the camera vehicle>, "what": "<two or three words>"}"""
RIG_LOW = 0.95  # only a box reaching the bottom edge can be the vehicle; above it Opus
# blames a bench for the camera mast elsewhere in the frame (7 of 22 at 0.8)


def rig_candidates(db: str) -> list[tuple[int, Path, dict]]:
    """City-panorama views with a SAM 3 target >= 0.6 reaching the bottom fifth."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT i.id, i.filepath, di.bbox FROM images i "
            "JOIN detections d ON d.image_id = i.id AND d.model_id = 'sam3' "
            "JOIN detection_items di ON di.detection_id = d.id AND di.is_target = 1 "
            "AND di.confidence >= 0.6 WHERE i.kind = 'aimed' "
            "AND i.image_source = 'AMSTERDAM_PANORAMA' AND i.filepath IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    best: dict[int, tuple[int, Path, dict]] = {}
    for iid, fp, bbox in rows:
        b = json.loads(bbox)
        if float(b["y2"]) >= RIG_LOW * 1024 and iid not in best:
            best[iid] = (iid, Path(fp), b)
    return list(best.values())


def run_rig(db: str, max_usd: float, workers: int = 6) -> dict:
    """Opus on 'is the box part of the camera vehicle?' for city-panorama views
    (2026-11-17: 3/5 of the owner's car/rig examples, 0/40 real benches flagged)."""
    import anthropic

    done = _cached(RIG_CACHE)
    todo = [c for c in rig_candidates(db) if c[0] not in done]
    client, usage, lock = anthropic.Anthropic(), Usage(), threading.Lock()
    stats = {"todo": len(todo), "vetted": 0, "vehicle": 0, "failed": 0}

    def one(c):
        iid, path, box = c
        if usage.usd(RIG_MODEL) >= max_usd:
            return
        try:
            a = _ask(client, path, box, usage, RIG_MODEL, prompt=RIG_PROMPT)
        except Exception:
            with lock:
                stats["failed"] += 1
            return
        rec = {
            "image_id": iid,
            "is_bench": a.get("is_bench") is not False,
            "what": a.get("what"),
        }
        with lock:
            with RIG_CACHE.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            stats["vetted"] += 1
            stats["vehicle"] += not rec["is_bench"]

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    return {**stats, "usd": round(usage.usd(RIG_MODEL), 3)}


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
    client,
    path: Path,
    box: dict,
    usage: Usage,
    model: str = MODEL,
    zoom: bool = False,
    prompt: str = PROMPT,
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
    if model.startswith("claude"):
        return _ask_claude(client, buf.getvalue(), usage, model, prompt)
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
                    {"text": prompt},
                ],
            }
        ],
        config={"response_mime_type": "application/json", "temperature": 0.0},
    )
    um = resp.usage_metadata
    usage.add(um.prompt_token_count or 0, um.candidates_token_count or 0)
    a = json.loads(resp.text)
    return a[0] if isinstance(a, list) else a


def _ask_claude(
    client, jpeg: bytes, usage: Usage, model: str, prompt: str = PROMPT
) -> dict:
    """The same question to a Claude model (``anthropic`` SDK; an ``ant auth login``
    session works without ANTHROPIC_API_KEY)."""
    import base64

    msg = client.messages.create(
        model=model,
        # A yes/no about one box: no thinking where the model allows it, else little.
        **(
            {"max_tokens": 300, "thinking": {"type": "disabled"}}
            if "haiku" in model
            else {
                "max_tokens": 4000,
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": "low"},
            }
        ),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64.b64encode(jpeg).decode(),
                        },
                    },
                    {"type": "text", "text": prompt + "\nReply with the JSON only."},
                ],
            }
        ],
    )
    usage.add(msg.usage.input_tokens, msg.usage.output_tokens)
    text = "".join(b.text for b in msg.content if b.type == "text")
    return json.loads(text[text.index("{") : text.rindex("}") + 1])


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
    verdicts = _cached()
    low = {
        c[0] for c in rig_candidates(db)
    }  # verdicts on boxes at the bottom edge only
    for iid, r in _cached(RIG_CACHE).items():  # the vehicle check wins when it says no
        if iid not in low:
            continue
        if not r["is_bench"] or iid not in verdicts:
            verdicts[iid] = r
    for iid, r in verdicts.items():
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
    rg = sub.add_parser(
        "rig", help="Opus: is the box the camera vehicle? (city panoramas)"
    )
    rg.add_argument("--max-usd", type=float, default=10.0)
    sub.add_parser("apply")
    a = ap.parse_args()
    if a.cmd == "run":
        print(run(a.db, a.images_root, a.max_usd, a.workers))
    elif a.cmd == "rig":
        print(run_rig(a.db, a.max_usd))
    else:
        print(apply(a.db))


if __name__ == "__main__":
    main()
