"""Lead photos moderators picked on the site -> data/feedback/site.json.

Two sources in D1: ``hero_picks`` (a moderator chose a gallery photo) and
``view_suggestions`` a moderator made that have been rendered (their Street View
camera becomes the lead with no second click). Per bench the latest wins.

``publish`` runs this first, so a pick made on the site survives the next
publish as an owner pick (``exclude.picked_images``, tier -1). Without wrangler or
network the last synced file stands.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from bench_finder.publish.exclude import FEEDBACK


log = logging.getLogger(__name__)

SITE_FILE = FEEDBACK / "site.json"
WORKER_DIR = Path("worker")
WRANGLER = WORKER_DIR / "wrangler.jsonc"


def admin_uids(config: Path = WRANGLER) -> list[str]:
    """The worker's ADMIN_UIDS (comma-separated) from its wrangler config."""
    m = (
        re.search(r'"ADMIN_UIDS"\s*:\s*"([^"]*)"', config.read_text())
        if config.exists()
        else None
    )
    return [u.strip() for u in m.group(1).split(",") if u.strip()] if m else []


def query(admins: list[str]) -> str:
    picks = "SELECT bench_id, image_id, picked_at AS t FROM hero_picks"
    if not admins:
        return picks
    ids = ", ".join("'" + a.replace("'", "''") + "'" for a in admins)
    return (
        f"{picks} UNION ALL SELECT bench_id, image_id, resolved_at AS t FROM view_suggestions "
        f"WHERE state = 'rendered' AND image_id IS NOT NULL AND user_id IN ({ids})"
    )


def parse(stdout: str) -> dict[str, int]:
    """wrangler ``d1 execute --json`` output -> {bench_id: image_id}; the latest ``t`` per bench."""
    best: dict[str, tuple[str, int]] = {}
    for block in json.loads(stdout):
        for row in block.get("results", []):
            b, t = str(int(row["bench_id"])), str(row.get("t") or "")
            if b not in best or t >= best[b][0]:
                best[b] = (t, int(row["image_id"]))
    return {b: i for b, (_, i) in sorted(best.items())}


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
                query(admin_uids(worker_dir / "wrangler.jsonc")),
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
