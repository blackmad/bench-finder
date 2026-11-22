"""Lead photos moderators picked on the site (D1 ``hero_picks``) -> data/feedback/site.json.

``publish`` runs this first, so a pick made on the site survives the next
publish as an owner pick (``exclude.picked_images``, tier -1). Without wrangler or
network the last synced file stands.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path


log = logging.getLogger(__name__)

SITE_FILE = Path("data/feedback/site.json")
WORKER_DIR = Path("worker")
QUERY = "SELECT bench_id, image_id FROM hero_picks ORDER BY bench_id"


def parse(stdout: str) -> dict[str, int]:
    """wrangler ``d1 execute --json`` output -> {bench_id: image_id}."""
    out: dict[str, int] = {}
    for block in json.loads(stdout):
        for row in block.get("results", []):
            out[str(int(row["bench_id"]))] = int(row["image_id"])
    return out


def sync(path: Path = SITE_FILE, worker_dir: Path = WORKER_DIR) -> int | None:
    """Write the live picks to ``path``; the number synced, or None if D1 was unreachable."""
    try:
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
                QUERY,
            ],
            cwd=worker_dir,
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        picks = parse(res.stdout)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as e:
        log.warning("site hero picks not synced (%s); keeping %s", e, path)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hero_pick": picks}, indent=1, sort_keys=True) + "\n")
    return len(picks)


if __name__ == "__main__":
    print(sync())
