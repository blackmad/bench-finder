"""Render the Street View cameras people suggested on the site ("Find a better view").

Pulls pending rows from D1 ``view_suggestions``, renders each with the hero
explorer (images.kind = 'suggested', 1024 square + 2048 hi-res) and marks the
row rendered (with the image id) or failed. After the next publish the photo is
in the bench's gallery, where a moderator can make it the lead.

    python -m bench_finder.view_suggestions            # all pending
    python -m bench_finder.view_suggestions --dry-run  # list them
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path


log = logging.getLogger(__name__)

WORKER_DIR = Path("worker")
SEARCH_M = 120  # how far from the bench a suggested panorama may stand


def d1(sql: str, worker_dir: Path = WORKER_DIR) -> list[dict]:
    """Run one statement on the live D1; its rows."""
    res = subprocess.run(
        [
            "npx",
            "wrangler",
            "d1",
            "execute",
            "bench-finder",
            "--remote",
            "--json",
            "--command",
            sql,
        ],
        cwd=worker_dir,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return [row for block in json.loads(res.stdout) for row in block.get("results", [])]


def sql_text(s: str) -> str:
    return "'" + s.replace("'", "''")[:300] + "'"


def mark(sid: int, *, image_id: int | None = None, error: str | None = None) -> None:
    t = sql_text(datetime.now(UTC).isoformat())
    if image_id is not None:
        d1(
            f"UPDATE view_suggestions SET state = 'rendered', image_id = {int(image_id)}, "
            f"error = NULL, resolved_at = {t} WHERE id = {int(sid)}"
        )
    else:
        d1(
            f"UPDATE view_suggestions SET state = 'failed', error = {sql_text(error or 'failed')}, "
            f"resolved_at = {t} WHERE id = {int(sid)}"
        )


def render_one(ex, row: dict, images_dir: str) -> int:
    """The image id of the rendered view; raises with a short reason."""
    bid = int(row["bench_id"])
    key = f"google:{row['pano_id']}"
    ex.bench(bid, SEARCH_M)
    try:
        ex._cand(bid, key)
    except KeyError:
        raise ValueError(f"panorama not within {SEARCH_M} m of the bench") from None
    # Street View's pitch is up-positive; the renderer's tilt is down-positive.
    return ex.run(
        ex._save(
            bid,
            key,
            float(row["heading"]),
            float(row["fov"]),
            -float(row["pitch"]),
            images_dir,
            kind="suggested",
        )
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Render suggested Street View cameras")
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images", default="images")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    rows = d1(
        "SELECT id, bench_id, pano_id, heading, pitch, fov FROM view_suggestions "
        "WHERE state = 'pending' ORDER BY created_at"
    )
    log.info("pending suggested views: %d", len(rows))
    if args.dry_run:
        for r in rows:
            log.info("%s", r)
        return

    from bench_finder.explore import Explorer

    ex = Explorer(args.db)
    for r in rows:
        try:
            image_id = render_one(ex, r, args.images)
            mark(r["id"], image_id=image_id)
            log.info(
                "suggestion %s (bench %s) -> image %d", r["id"], r["bench_id"], image_id
            )
        except Exception as e:  # one bad suggestion never stops the run
            log.warning(
                "suggestion %s (bench %s) failed: %s", r["id"], r["bench_id"], e
            )
            mark(r["id"], error=str(e))
        finally:
            ex.cands.clear()


if __name__ == "__main__":
    main()
