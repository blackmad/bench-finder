"""Which city a run covers.

``BENCH_CITY`` (default ``amsterdam``) picks the coverage box that the pipeline
steps select benches in, and the Overpass caches (water, stops, platforms) they
read. Boxes are (west, south, east, north).
"""

from __future__ import annotations

import os
from pathlib import Path


CITIES: dict[str, tuple[float, float, float, float]] = {
    # the municipality, incl. Weesp, Noord, the port
    "amsterdam": (4.62, 52.26, 5.15, 52.53),
    # the municipality, incl. Leidsche Rijn, Vleuten-De Meern and Haarzuilens
    "utrecht": (4.96, 52.02, 5.20, 52.15),
}

CITY = os.getenv("BENCH_CITY", "amsterdam")
if CITY not in CITIES:
    raise SystemExit(f"BENCH_CITY={CITY!r}: expected one of {sorted(CITIES)}")
COVERAGE_BBOX = CITIES[CITY]


def parse_bbox(value: str) -> tuple[float, float, float, float] | None:
    """A city name, 'all' (None), or 'west,south,east,north'."""
    if value in CITIES:
        return CITIES[value]
    if value == "all":
        return None
    w, s, e, n = (float(x) for x in value.split(","))
    return (w, s, e, n)


def city_cache(path: str) -> Path:
    """Amsterdam keeps its original cache names; other cities get a suffix."""
    p = Path(path)
    return p if CITY == "amsterdam" else p.with_name(f"{p.stem}_{CITY}{p.suffix}")
