"""Benches publish leaves out: seats at bus/tram stops and owner "no bench" marks.

Stops come from OSM (``data/osm/stops.json``: highway=bus_stop,
public_transport=platform, railway=tram_stop, public-transport shelters; fetch
with ``python -m bench_finder.publish.exclude fetch``). The city register (BGT)
counts the seat inside a bus shelter as a bench; the owner does not (2026-11-18).

Feedback files (``data/feedback/*.json``) are the what's-new page's export; a
bench whose latest marks include "no bench" is hidden.
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
    """Latest marks per bench across the exports (later files win)."""
    marks: dict[int, list[str]] = {}
    for f in sorted(folder.glob("*.json")) if folder.exists() else []:
        for k, v in json.loads(f.read_text()).get("feedback", {}).items():
            marks[int(k)] = v
    return marks


def excluded(benches: list[tuple[int, float, float]]) -> dict[str, set[int]]:
    marks = feedback()
    return {
        "bus_stop": at_stops(benches, stop_points()),
        "no_bench": {b for b, v in marks.items() if "no bench" in v},
    }


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
