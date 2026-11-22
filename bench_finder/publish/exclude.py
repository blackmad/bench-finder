"""Benches publish leaves out: seats at bus/tram stops and owner "no bench" marks.

Stops come from OSM (``data/osm/stops.json``: highway=bus_stop,
public_transport=platform, railway=tram_stop, public-transport shelters; fetch
with ``python -m bench_finder.publish.exclude fetch``). The city register (BGT)
counts the seat inside a bus shelter as a bench; the owner does not (2026-11-18).

Feedback files (``data/feedback/*.json``) are the what's-new page's export; a
bench whose latest marks include "no bench" or "bus stop" is hidden.
``mark-stops`` records benches within ``STOP_M`` of a stop as "bus stop" in
``data/feedback/bus_stops.json`` (hidden while the owner decides what to do with
them; delete an id there to bring it back).
"""

from __future__ import annotations

import json
import math
import sys
import urllib.parse
import urllib.request
from itertools import pairwise
from pathlib import Path


STOPS = Path("data/osm/stops.json")
FEEDBACK = Path("data/feedback")
STOP_M = 10.0
_BBOX = "52.27,4.72,52.44,5.08"
_QUERY = (
    f'[out:json][timeout:120];(nwr["highway"="bus_stop"]({_BBOX});'
    f'nwr["public_transport"="platform"]({_BBOX});nwr["railway"="tram_stop"]({_BBOX});'
    f'nwr["amenity"="shelter"]["shelter_type"="public_transport"]({_BBOX}););out center tags;'
)


def stop_points(path: Path = STOPS) -> list[tuple[float, float]]:
    if not path.exists():
        return []
    out = []
    for e in json.loads(path.read_text())["elements"]:
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lng = e.get("lon") or e.get("center", {}).get("lon")
        if lat is not None:
            out.append((lat, lng))
    return out


def at_stops(
    benches: list[tuple[int, float, float]],
    stops: list[tuple[float, float]],
    m: float = STOP_M,
) -> set[int]:
    """Ids of benches within ``m`` metres of a stop."""
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for p in stops:
        grid.setdefault((round(p[0] * 1000), round(p[1] * 1000)), []).append(p)
    hit = set()
    for bid, lat, lng in benches:
        k = (round(lat * 1000), round(lng * 1000))
        coslat = math.cos(math.radians(lat))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for a, b in grid.get((k[0] + dx, k[1] + dy), ()):
                    if math.hypot((a - lat) * 111320, (b - lng) * 111320 * coslat) <= m:
                        hit.add(bid)
    return hit


def feedback(folder: Path = FEEDBACK) -> dict[int, list[str]]:
    """Every mark per bench across the exports and mark files."""
    marks: dict[int, list[str]] = {}
    for f in sorted(folder.glob("*.json")) if folder.exists() else []:
        for k, v in json.loads(f.read_text()).get("feedback", {}).items():
            marks.setdefault(int(k), [])
            marks[int(k)] += [m for m in v if m not in marks[int(k)]]
    return marks


HIDE = ("no bench", "bus stop", "train station")
PLATFORMS = Path(
    "data/osm/rail_platforms.json"
)  # railway=platform, train/subway platforms
PLATFORM_M = 8.0


def _seg_m(lat, lng, a, b) -> float:
    """Metres from (lat, lng) to segment a-b (local flat projection)."""
    k = 111320 * math.cos(math.radians(lat))
    ax, ay = (a[1] - lng) * k, (a[0] - lat) * 111320
    bx, by = (b[1] - lng) * k, (b[0] - lat) * 111320
    dx, dy = bx - ax, by - ay
    t = (
        0.0
        if dx == dy == 0
        else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    )
    return math.hypot(ax + t * dx, ay + t * dy)


def _inside(lat, lng, ring) -> bool:
    hit = False
    for (y1, x1), (y2, x2) in zip(ring, ring[1:] + ring[:1], strict=True):
        if (y1 > lat) != (y2 > lat) and lng < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def on_platforms(benches, path: Path = PLATFORMS, m: float = PLATFORM_M) -> set[int]:
    """Ids of benches on or within ``m`` metres of a rail platform's outline."""
    if not path.exists():
        return set()
    lines = []
    for e in json.loads(path.read_text())["elements"]:
        if e.get("tags", {}).get("tram") == "yes":  # tram stops: the bus-stop rule
            continue
        if e["type"] == "node":
            lines.append([(e["lat"], e["lon"])])
        for g in [e.get("geometry")] + [
            mm.get("geometry") for mm in e.get("members", [])
        ]:
            lines.extend([[(q["lat"], q["lon"]) for q in g]] if g else [])
    hit = set()
    for bid, lat, lng in benches:
        for ln in lines:
            ys = [q[0] for q in ln]
            xs = [q[1] for q in ln]
            if not (
                min(ys) - 2e-4 < lat < max(ys) + 2e-4
                and min(xs) - 3e-4 < lng < max(xs) + 3e-4
            ):
                continue
            segs = pairwise(ln) if len(ln) > 1 else [(ln[0], ln[0])]
            if any(_seg_m(lat, lng, a, b) <= m for a, b in segs) or (
                len(ln) > 3 and ln[0] == ln[-1] and _inside(lat, lng, ln)
            ):
                hit.add(bid)
                break
    return hit


def vetoed_images(folder: Path = FEEDBACK) -> set[int]:
    """Images the owner marked as not showing the bench (review's "wrong photo")."""
    out: set[int] = set()
    for f in sorted(folder.glob("*.json")) if folder.exists() else []:
        out |= {int(i) for i in json.loads(f.read_text()).get("wrong_photo", [])}
    return out


def picked_images(folder: Path = FEEDBACK) -> set[int]:
    """Views the owner picked as a bench's hero, whatever SAM 3 said: in review
    (``h``) and on the site (``site.json``, from ``bench_finder.publish.site_picks``).
    One per bench; a later file wins, and ``site.json`` sorts after ``review.json``."""
    per_bench: dict[str, int] = {}
    for f in sorted(folder.glob("*.json")) if folder.exists() else []:
        for bench, image in json.loads(f.read_text()).get("hero_pick", {}).items():
            per_bench[str(bench)] = int(image)
    return set(per_bench.values())


UNDER_M = 9.0  # a panorama this far below the street around it is in a tunnel
NEIGHBOUR_M = 200.0


def underground_images(conn) -> set[int]:
    """Views taken in road tunnels (IJtunnel, Piet Heintunnel...): the panorama's
    elevation is UNDER_M or more below the 90th percentile of the distinct
    panoramas within NEIGHBOUR_M (a tunnel has many in a row; polders are low
    all round, so only the relative drop counts)."""
    by_img: dict[int, tuple] = {}
    panos: dict[tuple, float] = {}
    for iid, lat, lng, md in conn.execute(
        "SELECT id, panorama_lat, panorama_lng, panorama_metadata FROM images "
        "WHERE capture_success = 1 AND panorama_metadata LIKE '%elevation%' "
        "AND panorama_lat IS NOT NULL"
    ):
        try:
            e = json.loads(md).get("elevation")
        except ValueError:
            continue
        if e is not None:
            k = (round(lat, 6), round(lng, 6))
            panos[k] = float(e)
            by_img[iid] = k
    cell = 0.002
    grid: dict[tuple[int, int], list] = {}
    for (lat, lng), e in panos.items():
        grid.setdefault((int(lat / cell), int(lng / cell)), []).append((lat, lng, e))
    low = set()
    for (lat, lng), e in panos.items():
        ci, cj = int(lat / cell), int(lng / cell)
        coslat = math.cos(math.radians(lat))
        near = sorted(
            q[2]
            for di in (-1, 0, 1)
            for dj in (-2, -1, 0, 1, 2)
            for q in grid.get((ci + di, cj + dj), ())
            if math.hypot((q[0] - lat) * 111320, (q[1] - lng) * 111320 * coslat)
            <= NEIGHBOUR_M
        )
        if len(near) >= 5 and e <= near[int(len(near) * 0.9)] - UNDER_M:
            low.add((lat, lng))
    return {i for i, k in by_img.items() if k in low}


def excluded() -> dict[str, set[int]]:
    """Mark -> bench ids to hide: the owner's and the stop marks.

    Opus's terrace verdicts (bench_finder.terrace: "business" / "private") are
    not used: they hid too many public benches (dropped 2026-11-21).
    """
    marks = feedback()
    return {m: {b for b, v in marks.items() if m in v} for m in HIDE}


def mark_stops(db: str = "data/benches.db") -> dict[str, int]:
    """Write the "bus stop" marks (bench_feedback format) for every bench near a stop."""
    import sqlite3

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT id, lat, lng FROM bench_candidates").fetchall()
    finally:
        conn.close()
    FEEDBACK.mkdir(parents=True, exist_ok=True)
    n = {}
    for name, mark, ids, src in (
        (
            "bus_stops",
            "bus stop",
            at_stops(rows, stop_points()),
            f"OSM stops within {STOP_M:.0f} m",
        ),
        (
            "train_stations",
            "train station",
            on_platforms(rows),
            f"OSM rail platforms within {PLATFORM_M:.0f} m",
        ),
    ):
        (FEEDBACK / f"{name}.json").write_text(
            json.dumps(
                {"source": src, "feedback": {str(i): [mark] for i in sorted(ids)}},
                indent=0,
            )
        )
        n[mark] = len(ids)
    return n


def fetch(path: Path = STOPS) -> int:
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=urllib.parse.urlencode({"data": _QUERY}).encode(),
        headers={"User-Agent": "bench-finder"},
    )
    with urllib.request.urlopen(req, timeout=200) as r:
        body = r.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return len(json.loads(body)["elements"])


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        print(fetch())
    elif sys.argv[1:] == ["mark-stops"]:
        print(mark_stops())
