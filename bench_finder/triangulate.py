"""Where a bench really is: intersect the rays from panoramas that saw it.

Each aimed view with a confident SAM 3 target gives a ray: from the panorama,
along the view's aim plus the box centre's offset in the frame. Rays from two
or more panoramas that see the bench from different directions cross at the
bench. OSM/BGT pins are often 3-5 m off (Prinsengracht 370, 2026-11-18), which
swings a view aimed from 4 m away by 30-45 degrees.

Robust: every pair of rays at least ``MIN_SPREAD_DEG`` apart proposes a point;
the point that the most rays pass within ``INLIER_M`` of wins (rows of benches
give competing points), then a weighted least-squares fit on its inliers.

    uv run python -m bench_finder.triangulate measure            # dry run, stats
    uv run python -m bench_finder.triangulate apply              # bench_positions table
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np


M_PER_DEG_LAT = 111_320.0
SAM3_MIN = 0.6
MIN_SPREAD_DEG = 20.0  # two rays this close to parallel cannot fix a point
INLIER_M = 1.2  # a ray passing this close to the point agrees with it
MAX_SHIFT_M = 20.0  # farther than this from the pin it is probably another bench
MIN_RAYS = 2
MAX_ERR_M = 1.0  # the fitted point may slide this far along its weakest direction
VIEW_PX = 1024  # aimed views are square renders this wide


@dataclass
class Ray:
    x: float  # panorama position, metres east of the pin
    y: float  # metres north of the pin
    bearing: float  # degrees, compass
    w: float  # weight (SAM 3 confidence)
    pano: str

    @property
    def d(self) -> tuple[float, float]:
        b = math.radians(self.bearing)
        return math.sin(b), math.cos(b)


def load_rays(db: str) -> tuple[dict[int, tuple[float, float]], dict[int, list[Ray]]]:
    """(pins, rays) for every bench with a confident SAM 3 target in an aimed view."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    pins = {
        i: (lat, lng)
        for i, lat, lng in conn.execute("SELECT id, lat, lng FROM bench_candidates")
    }
    rows = conn.execute(
        "SELECT i.bench_candidate_id, i.pano_id, i.panorama_lat, i.panorama_lng, "
        "coalesce(i.camera_bearing_deg, i.heading), i.fov_deg, di.confidence, di.bbox "
        "FROM images i JOIN detections d ON d.image_id = i.id AND d.model_id = 'sam3' "
        "JOIN detection_items di ON di.detection_id = d.id AND di.is_target = 1 "
        "WHERE i.kind = 'aimed' AND i.capture_success = 1 AND i.panorama_lat IS NOT NULL "
        "AND i.fov_deg IS NOT NULL AND di.confidence >= ?",
        (SAM3_MIN,),
    ).fetchall()
    conn.close()
    best: dict[tuple[int, str], tuple] = {}
    for bid, pano, plat, plng, aim, fov, conf, bbox in rows:
        key = (bid, pano or f"{plat},{plng}")
        if key not in best or conf > best[key][4]:
            best[key] = (plat, plng, aim, fov, conf, bbox)
    rays: dict[int, list[Ray]] = defaultdict(list)
    for (bid, pano), (plat, plng, aim, fov, conf, bbox) in best.items():
        if bid not in pins or not bbox:
            continue
        b = json.loads(bbox)
        cx = (b["x1"] + b["x2"]) / 2 / VIEW_PX - 0.5  # -0.5..0.5 across the frame
        off = math.degrees(math.atan(2 * cx * math.tan(math.radians(fov) / 2)))
        lat0, lng0 = pins[bid]
        k = M_PER_DEG_LAT * math.cos(math.radians(lat0))
        rays[bid].append(
            Ray((plng - lng0) * k, (plat - lat0) * M_PER_DEG_LAT, aim + off, conf, pano)
        )
    return pins, rays


def _cross(a: Ray, b: Ray) -> tuple[float, float] | None:
    """Where two rays meet, if in front of both cameras."""
    (dx1, dy1), (dx2, dy2) = a.d, b.d
    det = dx1 * (-dy2) - dy1 * (-dx2)
    if abs(det) < 1e-9:
        return None
    rx, ry = b.x - a.x, b.y - a.y
    t = (rx * (-dy2) - ry * (-dx2)) / det
    s = (dx1 * ry - dy1 * rx) / det
    if t <= 0 or s <= 0:
        return None
    return a.x + t * dx1, a.y + t * dy1


def _dist(p: tuple[float, float], r: Ray) -> float:
    """Perpendicular distance from p to the ray (inf if behind the camera)."""
    dx, dy = r.d
    vx, vy = p[0] - r.x, p[1] - r.y
    if vx * dx + vy * dy <= 0:
        return math.inf
    return abs(vx * dy - vy * dx)


RAY_SD_M = 0.5  # how far a good ray misses the bench (box centre vs bench centre)


def _fit(rays: list[Ray]) -> tuple[float, float, float]:
    """Weighted least-squares point nearest to all the lines, and its error (m)
    along the worst direction: rays that are nearly parallel leave the point
    free to slide along them."""
    a = np.zeros((2, 2))
    v = np.zeros(2)
    for r in rays:
        dx, dy = r.d
        p = np.eye(2) - np.outer((dx, dy), (dx, dy))
        a += r.w * p
        v += r.w * p @ np.array((r.x, r.y))
    x, y = np.linalg.solve(a, v)
    lam = float(np.linalg.eigvalsh(a)[0])
    err = RAY_SD_M / math.sqrt(lam) if lam > 1e-9 else math.inf
    return float(x), float(y), err


def _angle(a: float, b: float) -> float:
    """Angle between the lines (not rays): opposite rays are parallel too, and
    cameras facing each other across a canal cannot fix a point between them."""
    d = abs(a - b) % 180
    return min(d, 180 - d)


def solve(rays: list[Ray]) -> dict | None:
    """The consensus point of the rays, or None when they do not agree."""
    if len(rays) < MIN_RAYS:
        return None
    best: tuple[int, float, list[Ray]] | None = None
    for a, b in itertools.combinations(rays, 2):
        if a.pano == b.pano or _angle(a.bearing, b.bearing) < MIN_SPREAD_DEG:
            continue
        p = _cross(a, b)
        if p is None or math.hypot(*p) > MAX_SHIFT_M:
            continue
        inl = [r for r in rays if _dist(p, r) <= INLIER_M]
        score = sum(r.w for r in inl)
        # more agreeing rays wins; on a tie the point nearer the pin
        key = (len(inl), -math.hypot(*p))
        if best is None or key > (best[0], best[1]):
            best = (key[0], key[1], inl)
        del score
    if best is None or best[0] < MIN_RAYS:
        return None
    inl = best[2]
    try:
        x, y, err = _fit(inl)
    except np.linalg.LinAlgError:
        return None
    if math.hypot(x, y) > MAX_SHIFT_M or err > MAX_ERR_M:
        return None
    resid = math.sqrt(sum(_dist((x, y), r) ** 2 for r in inl) / len(inl))
    bearings = [r.bearing for r in inl]
    spread = max(_angle(a, b) for a, b in itertools.combinations(bearings, 2))
    return {
        "dx": x,
        "dy": y,
        "shift_m": math.hypot(x, y),
        "rays": len(inl),
        "of": len(rays),
        "resid_m": resid,
        "spread_deg": spread,
        "err_m": err,
    }


def measure(db: str) -> dict:
    _, rays = load_rays(db)
    shifts = []
    stats = {"benches_with_rays": len(rays), "two_plus_panos": 0, "solved": 0}
    for rs in rays.values():
        if len({r.pano for r in rs}) >= 2:
            stats["two_plus_panos"] += 1
        s = solve(rs)
        if s:
            stats["solved"] += 1
            shifts.append(s["shift_m"])
    shifts.sort()
    q = lambda f: round(shifts[int(f * (len(shifts) - 1))], 1) if shifts else None  # noqa: E731
    stats["shift_m_p25_p50_p75_p90"] = [q(0.25), q(0.5), q(0.75), q(0.9)]
    stats["over_3m"] = sum(s > 3 for s in shifts)
    stats["over_6m"] = sum(s > 6 for s in shifts)
    return stats


def apply(db: str) -> dict:
    pins, rays = load_rays(db)
    conn = sqlite3.connect(db, timeout=120)
    conn.execute("DROP TABLE IF EXISTS bench_positions")  # derived; rebuilt whole
    conn.execute(
        "CREATE TABLE bench_positions (bench_candidate_id INTEGER PRIMARY KEY, "
        "lat REAL, lng REAL, shift_m REAL, rays INTEGER, of_rays INTEGER, resid_m REAL, "
        "spread_deg REAL, err_m REAL, created_at TEXT)"
    )
    now = datetime.now(UTC).isoformat()
    n = 0
    for bid, rs in rays.items():
        s = solve(rs)
        if not s:
            continue
        lat0, lng0 = pins[bid]
        k = M_PER_DEG_LAT * math.cos(math.radians(lat0))
        conn.execute(
            "INSERT OR REPLACE INTO bench_positions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                bid,
                lat0 + s["dy"] / M_PER_DEG_LAT,
                lng0 + s["dx"] / k,
                round(s["shift_m"], 2),
                s["rays"],
                s["of"],
                round(s["resid_m"], 2),
                round(s["spread_deg"], 1),
                round(s["err_m"], 2),
                now,
            ),
        )
        n += 1
    conn.commit()
    conn.close()
    return {"written": n}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("cmd", choices=["measure", "apply"])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--ids", help="print the solution for these bench ids")
    a = ap.parse_args()
    if a.ids:
        _, rays = load_rays(a.db)
        for i in (int(x) for x in a.ids.split(",")):
            print(i, len(rays.get(i, [])), solve(rays.get(i, [])))
        return
    print(measure(a.db) if a.cmd == "measure" else apply(a.db))


if __name__ == "__main__":
    main()
