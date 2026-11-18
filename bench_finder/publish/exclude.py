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


HIDE = ("no bench", "bus stop")


def excluded() -> dict[str, set[int]]:
    marks = feedback()
    return {m: {b for b, v in marks.items() if m in v} for m in HIDE}


def mark_stops(db: str = "data/benches.db") -> int:
    """Write the "bus stop" marks (bench_feedback format) for every bench near a stop."""
    import sqlite3

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT id, lat, lng FROM bench_candidates").fetchall()
    finally:
        conn.close()
    ids = sorted(at_stops(rows, stop_points()))
    out = FEEDBACK / "bus_stops.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "source": f"OSM stops within {STOP_M:.0f} m",
                "feedback": {str(i): ["bus stop"] for i in ids},
            },
            indent=0,
        )
    )
    return len(ids)


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
