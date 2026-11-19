"""Benches by the water face the water: snap their facing to the nearest edge.

Per-photo facing estimates are noisy (often 45 degrees off), but a bench on a
quay looks straight out over the canal. For benches within ``NEAR_M`` of a water
area from OpenStreetMap whose facing came from the vision model (never an OSM
``direction`` tag or a visitor) and which look at water (``faces_category`` =
water) or roughly towards it, set the facing to point at the nearest water edge.
The old value is kept in ``water_facing`` so the change can be undone.

    uv run python -m bench_finder.water_facing fetch   # OSM water -> data/osm_water.json
    uv run python -m bench_finder.water_facing apply [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from bench_finder.publish.build import AMSTERDAM_BBOX


NEAR_M = 20.0
ROUGHLY_DEG = 100.0  # a non-water bench is snapped only if it already faces this close
CACHE = Path("data/osm_water.json")
OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
M_PER_DEG_LAT = 111_320.0


def fetch(cache: Path = CACHE) -> dict:
    w, s, e, n = AMSTERDAM_BBOX
    q = f"""[out:json][timeout:180];
(
  way["natural"="water"]({s},{w},{n},{e});
  relation["natural"="water"]({s},{w},{n},{e});
  way["waterway"="riverbank"]({s},{w},{n},{e});
);
out geom;"""
    data, err = None, None
    for url in OVERPASS:
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode({"data": q}).encode(),
            headers={"User-Agent": "bench-finder (water facing)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
            break
        except OSError as e:
            err = e
    if data is None:
        raise RuntimeError(f"every Overpass server failed: {err}")
    polys = []
    for el in data["elements"]:
        rings = []
        if el["type"] == "way" and el.get("geometry"):
            rings = [el["geometry"]]
        elif el["type"] == "relation":
            rings = [
                m["geometry"]
                for m in el.get("members", [])
                if m.get("role") == "outer" and m.get("geometry")
            ]
        for ring in rings:
            pts = [(p["lon"], p["lat"]) for p in ring]
            if len(pts) >= 4:
                polys.append(pts)
    cache.write_text(json.dumps(polys))
    return {"water_polygons": len(polys)}


def _local(lat0: float):
    k = math.cos(math.radians(lat0))
    return lambda lng, lat: ((lng * k) * M_PER_DEG_LAT, lat * M_PER_DEG_LAT)


def bearing(dx: float, dy: float) -> float:
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def angle(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def into_water(edge, poly, q, step: float = 1.5) -> float | None:
    """Bearing of the edge normal at ``q`` that points into ``poly`` (water)."""
    t = edge.project(q)
    a, b = edge.interpolate(max(t - 1, 0)), edge.interpolate(t + 1)
    dx, dy = b.x - a.x, b.y - a.y
    n = math.hypot(dx, dy)
    if n == 0:
        return None
    for nx, ny in ((-dy / n, dx / n), (dy / n, -dx / n)):
        if poly.contains(Point(q.x + nx * step, q.y + ny * step)):
            return bearing(nx, ny)
    return None


def apply(db: str, dry_run: bool, cache: Path = CACHE) -> dict:
    lat0 = (AMSTERDAM_BBOX[1] + AMSTERDAM_BBOX[3]) / 2
    to = _local(lat0)
    shapes, polys = [], []
    for ring in json.loads(cache.read_text()):
        p = Polygon([to(x, y) for x, y in ring])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            shapes.append(p.boundary)
            polys.append(p)
    tree = STRtree(shapes)
    conn = sqlite3.connect(db, timeout=120)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS water_facing (bench_candidate_id INTEGER PRIMARY KEY, "
        "old_facing REAL, old_method TEXT, new_facing REAL, distance_m REAL, created_at TEXT)"
    )
    rows = conn.execute(
        # Triangulated pins where publish uses them (bench_finder.triangulate).
        "SELECT a.bench_candidate_id, coalesce(m.lat, c.lat), coalesce(m.lng, c.lng), "
        "a.facing_deg, a.facing_method, a.faces_category "
        "FROM bench_attributes a JOIN bench_candidates c ON c.id = a.bench_candidate_id "
        "LEFT JOIN bench_positions m ON m.bench_candidate_id = c.id "
        "AND m.rays >= 3 AND m.shift_m > 2 AND m.err_m <= 1 "
        "WHERE a.facing_method = 'vlm' OR a.facing_method = 'water_edge'"
    ).fetchall()
    changed, near, moved = 0, 0, []
    now = datetime.now(UTC).isoformat()
    from bench_finder.water_back import behind  # Opus: water at the bench's back

    backs = behind()
    for bid, lat, lng, facing, method, cat in rows:
        if bid in backs:
            continue
        here = Point(to(lng, lat))
        i = tree.nearest(here)
        edge = shapes[i]
        d = here.distance(edge)
        if d > NEAR_M:
            continue
        near += 1
        _, q = nearest_points(here, edge)
        to_water = bearing(q.x - here.x, q.y - here.y)
        if d < 0.5:  # on the edge: face along the edge normal into the water
            to_water = into_water(edge, polys[i], q)
            if to_water is None:
                continue
        if cat != "water" and (facing is None or angle(facing, to_water) > ROUGHLY_DEG):
            continue
        old = conn.execute(
            "SELECT old_facing, old_method FROM water_facing WHERE bench_candidate_id = ?",
            (bid,),
        ).fetchone()
        old_f, old_m = old if old else (facing, method)
        moved.append(angle(old_f, to_water) if old_f is not None else 0)
        changed += 1
        if dry_run:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO water_facing VALUES (?,?,?,?,?,?)",
            (bid, old_f, old_m, round(to_water, 1), round(d, 1), now),
        )
        conn.execute(
            "UPDATE bench_attributes SET facing_deg = ?, facing_method = 'water_edge' "
            "WHERE bench_candidate_id = ?",
            (round(to_water, 1), bid),
        )
    conn.commit()
    moved.sort()
    return {
        "near_water": near,
        "snapped": changed,
        "median_turn_deg": round(moved[len(moved) // 2], 1) if moved else None,
        "dry_run": dry_run,
    }


QUAY_M = 6.0  # a bench without any facing this close to the water faces it


def apply_unfaced(db: str, dry_run: bool, cache: Path = CACHE) -> dict:
    """Benches with no facing at all (no estimate, no OSM ``direction``) within
    ``QUAY_M`` of a water edge: face the water, as an estimate (method
    ``water_edge``, confidence 0.5). Recorded in ``water_facing`` with no old value."""
    w, s_, e, n = AMSTERDAM_BBOX
    to = _local((s_ + n) / 2)
    shapes = []
    for ring in json.loads(cache.read_text()):
        p = Polygon([to(x, y) for x, y in ring])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            shapes.append(p.boundary)
    tree = STRtree(shapes)
    conn = sqlite3.connect(db, timeout=120)
    rows = conn.execute(
        "SELECT c.id, c.lat, c.lng, c.tags FROM bench_candidates c "
        "LEFT JOIN bench_attributes a ON a.bench_candidate_id = c.id "
        "WHERE a.facing_deg IS NULL AND c.lat BETWEEN ? AND ? AND c.lng BETWEEN ? AND ?",
        (s_, n, w, e),
    ).fetchall()
    now = datetime.now(UTC).isoformat()
    done = 0
    for bid, lat, lng, tags in rows:
        if (json.loads(tags) if tags else {}).get("direction"):
            continue
        here = Point(to(lng, lat))
        edge = shapes[tree.nearest(here)]
        d = here.distance(edge)
        if not 0.5 <= d <= QUAY_M:
            continue
        _, q = nearest_points(here, edge)
        f = round(bearing(q.x - here.x, q.y - here.y), 1)
        done += 1
        if dry_run:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO water_facing VALUES (?,?,?,?,?,?)",
            (bid, None, None, f, round(d, 1), now),
        )
        if (
            conn.execute(
                "UPDATE bench_attributes SET facing_deg = ?, facing_confidence = 0.5, "
                "facing_method = 'water_edge', updated_at = ? WHERE bench_candidate_id = ?",
                (f, now, bid),
            ).rowcount
            == 0
        ):
            conn.execute(
                "INSERT INTO bench_attributes (bench_candidate_id, facing_deg, "
                "facing_confidence, facing_method, axis_only, updated_at) "
                "VALUES (?, ?, 0.5, 'water_edge', 0, ?)",
                (bid, f, now),
            )
    conn.commit()
    conn.close()
    return {"unfaced": len(rows), "faced_water": done}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    p = sub.add_parser("apply")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser(
        "unfaced", help="benches with no facing on a quay face the water"
    )
    p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "fetch":
        print(fetch())
    elif a.cmd == "unfaced":
        print(apply_unfaced(a.db, a.dry_run))
    else:
        print(apply(a.db, a.dry_run))


if __name__ == "__main__":
    main()
