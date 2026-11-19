"""Write the bench data out as CSV under export/ for the GitHub repo.

  export/benches.csv          one row per published bench (what the site shows)
  export/tables/<table>.csv   the pipeline tables from data/benches.db; any file
                              over 20 MB is gzipped (<table>.csv.gz) so every file
                              stays well under GitHub's 100 MB limit.

Tables written by site visitors (ratings, comments, reports, statuses) are left
out: they can hold user ids and free text. So are SQLite's index internals and
detection_items (per-box polygons, ~100 MB gzipped).

Run after `bench-finder publish`:  uv run python tools/export_csv.py
"""

from __future__ import annotations

import csv
import gzip
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "benches.db"
PUBLISHED = ROOT / "dist-data"
OUT = ROOT / "export"
SITE = "https://bench.blackmad.com"
DATA_BASE = "https://bench-data.blackmad.com"
GZIP_OVER = 20 * 1024 * 1024

PRIVATE = {
    "bench_comments",
    "bench_ratings",
    "bench_reports",
    "bench_user_status",
    "missing_bench_reports",
}
# Too big for git (one row per detected box with its polygon: ~100 MB gzipped),
# and empty legacy tables.
SKIP = {"detection_items", "processed_benches"}

BENCH_COLUMNS = [
    "id",
    "lat",
    "lng",
    "address",
    "source",
    "osm_id",
    "osm_url",
    "facing_deg",
    "facing_confidence",
    "facing_method",
    "axis_only",
    "bench_type",
    "backrest",
    "faces_category",
    "faces_text",
    "material",
    "seats",
    "lit",
    "place_id",
    "photo_url",
    "photo_date",
    "page_url",
    "osm_tags",
]


def _cell(v: object) -> object:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    return v


def export_benches(con: sqlite3.Connection) -> int:
    manifest = json.loads((PUBLISHED / "manifest.json").read_text())
    bench_dir = PUBLISHED / manifest["data_base"] / manifest["bench_dir"]
    sources = {
        r[0]: (r[1], r[2])
        for r in con.execute("SELECT id, source, external_id FROM bench_candidates")
    }
    rows = []
    for f in bench_dir.glob("*.json"):
        b = json.loads(f.read_text())
        source, ext = sources.get(b["id"], (None, None))
        osm_id = ext if (source or "").lower() == "osm" and ext else None
        hero = b.get("hero_urls") or {}
        lead = (b.get("gallery") or [{}])[0]
        rows.append(
            {
                "id": b["id"],
                "lat": b["lat"],
                "lng": b["lng"],
                "address": b.get("address"),
                "source": source,
                "osm_id": osm_id,
                "osm_url": f"https://www.openstreetmap.org/node/{osm_id}"
                if osm_id
                else None,
                "facing_deg": b.get("facing"),
                "facing_confidence": b.get("facing_confidence"),
                "facing_method": b.get("facing_method"),
                "axis_only": b.get("axis_only"),
                "bench_type": b.get("bench_type"),
                "backrest": b.get("backrest"),
                "faces_category": b.get("faces_category"),
                "faces_text": b.get("faces_text"),
                "material": b.get("material"),
                "seats": b.get("seats"),
                "lit": b.get("lit"),
                "place_id": (b.get("place") or {}).get("id"),
                "photo_url": f"{DATA_BASE}/{hero['800']}" if hero.get("800") else None,
                "photo_date": lead.get("pano_date") if hero else None,
                "page_url": f"{SITE}/bench/{b['id']}",
                "osm_tags": b.get("tags"),
            }
        )
    rows.sort(key=lambda r: r["id"])
    with (OUT / "benches.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, BENCH_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: _cell(r[k]) for k in BENCH_COLUMNS})
    return len(rows)


def export_tables(con: sqlite3.Connection) -> list[tuple[str, int, str]]:
    tables_dir = OUT / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for old in tables_dir.glob("*.csv*"):
        old.unlink()
    names = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'rtree_%' AND name != 'schema_migrations' ORDER BY name"
        )
    ]
    done = []
    for name in names:
        if name in PRIVATE or name in SKIP:
            continue
        cur = con.execute(f'SELECT * FROM "{name}"')
        cols = [d[0] for d in cur.description]
        path = tables_dir / f"{name}.csv"
        n = 0
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for row in cur:
                w.writerow(["" if v is None else v for v in row])
                n += 1
        if path.stat().st_size > GZIP_OVER:
            gz = path.with_suffix(".csv.gz")
            with path.open("rb") as src, gzip.GzipFile(gz, "wb", mtime=0) as dst:
                dst.writelines(src)
            path.unlink()
            path = gz
        done.append((name, n, path.name))
    return done


def main() -> None:
    if not DB.exists():
        sys.exit(f"no database at {DB}")
    OUT.mkdir(exist_ok=True)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    n = export_benches(con)
    print(f"benches.csv: {n} benches")
    for _name, rows, file in export_tables(con):
        size = (OUT / "tables" / file).stat().st_size / 1e6
        print(f"tables/{file}: {rows} rows, {size:.1f} MB")


if __name__ == "__main__":
    main()
