"""Free, local check: is the bench in a view hidden behind something? (qwen3.5:9b via Ollama)

Asks the user's local Ollama model, per aimed view where SAM 3 found the target
bench and no VLM label exists yet, whether a bench is visible near the middle and
whether a hedge, car, bin, tree or person hides a large part of it. Answers go to
``image_annotations`` (``bench_present``, ``occluded``) under ``ANNOTATOR``; the
publish ranking puts blocked views after clear ones (VLM labels win where both
exist).

Measured against 300 Flash-Lite labels (2026-11-16): flags 63% of the views
Flash-Lite calls blocked, wrongly flags 7% of clear ones, and 85% of its flags
agree. Its view side is no better than chance, so it is not asked.

Needs ``ollama serve`` running with ``qwen3.5:9b`` pulled. Resumable.

    uv run python -m bench_finder.local_occlusion [--limit N]
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from bench_finder.label_views import SAM3_MIN
from bench_finder.labeling import store


MODEL = "qwen3.5:9b"
ANNOTATOR = f"ollama/{MODEL}@occ1"
OLLAMA = "http://localhost:11434/api/chat"
PROMPT = """This street-level photo was aimed at one park bench, near the middle of the image.
Answer in JSON with keys:
"bench_visible": "yes" if a bench is visible near the middle, else "no".
"occluded": true if a hedge, car, bin, pole, tree, person or other object hides a large part of that bench, else false."""

TODO_SQL = """
SELECT DISTINCT i.id FROM images i
JOIN detections d ON d.image_id = i.id AND d.model_id = 'sam3' AND d.detection_success = 1
JOIN detection_items di ON di.detection_id = d.id AND di.is_target = 1 AND di.confidence >= ?
WHERE i.kind = 'aimed'
  AND NOT EXISTS (SELECT 1 FROM image_annotations a WHERE a.image_id = i.id
                  AND a.label_type = 'occluded')
ORDER BY i.id DESC
"""


def ask(path: Path) -> dict:
    im = Image.open(path).convert("RGB")
    im.thumbnail((768, 768))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    body = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0},
        "messages": [
            {
                "role": "user",
                "content": PROMPT,
                "images": [base64.b64encode(buf.getvalue()).decode()],
            }
        ],
    }
    req = urllib.request.Request(
        OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(json.loads(r.read())["message"]["content"])


def run(db: str, images_root: Path, limit: int | None) -> dict:
    conn = store.connect(db)
    conn.execute("PRAGMA busy_timeout = 120000")
    todo = [r[0] for r in conn.execute(TODO_SQL, (SAM3_MIN,))][:limit]
    done = err = 0
    t0 = time.time()
    for n, iid in enumerate(todo, 1):
        path = store.image_path(conn, iid, images_root)
        try:
            a = ask(path)
        except Exception as e:
            err += 1
            if err <= 5:
                print(f"image {iid}: {e!r}"[:200], flush=True)
            continue
        now = datetime.now(UTC).isoformat()
        visible = "yes" if str(a.get("bench_visible")).lower() == "yes" else "no"
        blocked = a.get("occluded") in (True, "true", "yes")
        conn.executemany(
            "INSERT INTO image_annotations (image_id, annotator, label_type, value, "
            "confidence, created_at) VALUES (?,?,?,?,NULL,?)",
            [
                (iid, ANNOTATOR, "bench_present", json.dumps(visible), now),
                (iid, ANNOTATOR, "occluded", json.dumps(blocked), now),
            ],
        )
        conn.commit()
        done += 1
        if n % 100 == 0:
            rate = (time.time() - t0) / n
            print(f"{n}/{len(todo)} {rate:.1f}s/img", flush=True)
    return {"todo": len(todo), "labelled": done, "errors": err}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    print(run(a.db, a.images_root, a.limit))


if __name__ == "__main__":
    main()
