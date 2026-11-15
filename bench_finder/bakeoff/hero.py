"""Hero-photo bake-off: can a cheap model pick "the bench + what it looks at"?

    uv run python -m bench_finder.bakeoff.hero run --model gemini-3.1-flash-lite --max-usd 1
    uv run python -m bench_finder.bakeoff.hero score

The owner wants each bench's main photo to show the bench *and the view a sitter
has*, i.e. a photo taken from behind (or behind-and-to-the-side of) the bench.
Instead of the 8-way ``view_relation`` question, this asks one focused question per
image and gets a 0-10 ``sitter_view`` score plus what the bench looks at.

Gold: oracle labels (``image_annotations`` annotator ``oracle:%``). An image is a
gold hero when the bench is present and ``view_relation`` is back/back-left/back-right.
``score`` reports image-level precision/recall at several thresholds and the
bench-level hit rate: for benches that have at least one gold hero image, how often
the model's top-scored image is one of them (vs. picking at random).
Answers are cached as JSON under ``data/bakeoff_cache/hero/<model>/<image_id>.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from bench_finder.clients.view_classifier import (
    PRICES,
    Usage,
    prepare_image,
    require_key,
)
from bench_finder.labeling import store


BACK = {"back", "back-left", "back-right"}
CACHE = Path("data/bakeoff_cache/hero")
LOOKS_AT = [
    "water",
    "park",
    "residential street",
    "busy street",
    "square",
    "courtyard",
    "playground",
    "other",
]

PROMPT = """This is a street-level photo aimed at a public bench in Amsterdam.

We want photos that show the bench AND what a person sitting on it would look at:
the camera is behind the bench (or behind and to one side), so the seat/backrest is
in the foreground and the view the bench faces fills the background.
A photo of the bench's front (looking at the seat, with whatever is behind the
bench as background) is NOT what we want, nor is a side-on view where you cannot
tell what it faces.

Answer as JSON:
- bench_visible: is a bench clearly visible in the photo?
- sitter_view: 0-10, how well the photo shows the bench together with the view
  someone sitting on it would have (10 = taken from right behind the bench, the
  bench and its whole view in frame; 0 = no bench, or the bench is seen from the front).
- looks_at: what someone sitting on the bench looks at, one of: """ + ", ".join(
    LOOKS_AT
)

SCHEMA = {
    "type": "object",
    "properties": {
        "bench_visible": {"type": "boolean"},
        "sitter_view": {"type": "integer"},
        "looks_at": {"type": "string", "enum": LOOKS_AT},
    },
    "required": ["bench_visible", "sitter_view", "looks_at"],
}


def gold_images(conn) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for iid, lt, v in conn.execute(
        "SELECT image_id, label_type, value FROM image_annotations WHERE annotator LIKE 'oracle:%'"
    ):
        out.setdefault(iid, {})[lt] = json.loads(v)
    return out


def is_gold_hero(g: dict) -> bool:
    return g.get("bench_present") == "yes" and g.get("view_relation") in BACK


def run(
    db: str,
    model: str,
    max_usd: float,
    workers: int,
    images_root: Path,
    thinking: str | None,
) -> dict:
    from google import genai

    conn = store.connect(db)
    g = gold_images(conn)
    out_dir = CACHE / model
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [i for i in sorted(g) if not (out_dir / f"{i}.json").exists()]
    paths = {i: store.image_path(conn, i, images_root) for i in todo}
    usage, local = Usage(), threading.local()
    pin, pout = PRICES[model]

    def spent() -> float:
        return (usage.input_tokens * pin + usage.output_tokens * pout) / 1e6

    def one(iid: int) -> int:
        if spent() >= max_usd:
            return -1
        if not hasattr(local, "c"):
            local.c = genai.Client(api_key=require_key("GEMINI_API_KEY", None))
        data, mime, _ = prepare_image(paths[iid])
        cfg: dict = {
            "response_mime_type": "application/json",
            "response_json_schema": SCHEMA,
            "temperature": 0.0,
        }
        if thinking:
            cfg["thinking_config"] = {"thinking_level": thinking}
        for attempt in range(8):
            try:
                resp = local.c.models.generate_content(
                    model=model,
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {"inline_data": {"mime_type": mime, "data": data}},
                                {"text": PROMPT},
                            ],
                        }
                    ],
                    config=cfg,
                )
                break
            except Exception as e:
                code = getattr(e, "code", None)
                if (
                    not ((code == 429 and "PerDay" not in str(e)) or code == 503)
                    or attempt == 7
                ):
                    raise
                m = re.search(r"retry in ([0-9.]+)s", str(e))
                time.sleep(float(m.group(1)) + 1 if m else 15.0)
        um = resp.usage_metadata
        usage.add(
            int(um.prompt_token_count or 0),
            int(um.candidates_token_count or 0)
            + int(getattr(um, "thoughts_token_count", 0) or 0),
        )
        (out_dir / f"{iid}.json").write_text(resp.text)
        return iid

    ok = err = skipped = 0
    with ThreadPoolExecutor(workers) as pool:
        for f in as_completed(
            [pool.submit(one, i) for i in todo if paths[i] is not None]
        ):
            try:
                ok += f.result() >= 0
                skipped += f.result() < 0
            except Exception as e:
                err += 1
                if err <= 3:
                    print(f"error: {e!r}"[:300])
    return {
        "model": model,
        "classified": ok,
        "errors": err,
        "skipped_budget": skipped,
        "usd": round(spent(), 4),
        "usd_per_image": round(spent() / ok, 5) if ok else None,
    }


def score(db: str) -> None:
    conn = store.connect(db)
    g = gold_images(conn)
    bench_of = dict(conn.execute("SELECT id, bench_candidate_id FROM images"))
    for d in sorted(p for p in CACHE.iterdir() if p.is_dir()):
        pred = {int(f.stem): json.loads(f.read_text()) for f in d.glob("*.json")}
        ids = [i for i in pred if i in g]
        if not ids:
            continue
        print(f"\n{d.name}: {len(ids)} images")
        for t in (5, 6, 7, 8):
            tp = sum(
                1
                for i in ids
                if is_gold_hero(g[i])
                and pred[i]["bench_visible"]
                and pred[i]["sitter_view"] >= t
            )
            pp = sum(
                1
                for i in ids
                if pred[i]["bench_visible"] and pred[i]["sitter_view"] >= t
            )
            gp = sum(1 for i in ids if is_gold_hero(g[i]))
            print(
                f"  sitter_view>={t}: precision {tp / max(pp, 1):.2f} recall {tp / max(gp, 1):.2f} ({pp} flagged)"
            )
        benches: dict[int, list[int]] = {}
        for i in ids:
            benches.setdefault(bench_of[i], []).append(i)
        hit = rand = n = 0
        for imgs in benches.values():
            if not any(is_gold_hero(g[i]) for i in imgs):
                continue
            n += 1
            top = max(
                imgs, key=lambda i: (pred[i]["bench_visible"], pred[i]["sitter_view"])
            )
            hit += is_gold_hero(g[top])
            rand += sum(is_gold_hero(g[i]) for i in imgs) / len(imgs)
        print(
            f"  bench-level top pick is a gold hero: {hit}/{n} = {hit / max(n, 1):.2f} (random pick {rand / max(n, 1):.2f})"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", default="gemini-3.1-flash-lite")
    r.add_argument("--max-usd", type=float, default=1.0)
    r.add_argument("--workers", type=int, default=6)
    r.add_argument("--thinking", help="thinking_level (e.g. low)")
    r.add_argument("--images-root", type=Path, default=Path("images"))
    sub.add_parser("score")
    a = ap.parse_args()
    if a.cmd == "run":
        print(run(a.db, a.model, a.max_usd, a.workers, a.images_root, a.thinking))
    else:
        score(a.db)


if __name__ == "__main__":
    main()
