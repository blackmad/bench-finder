"""Import a city's OpenStreetMap benches as candidates, with no paid API.

``generate-candidates`` geocodes its query and reverse-geocodes every bench with
Google (billed per call). This takes the city's coverage box instead
(``bench_finder.coverage``), asks Overpass for ``amenity=bench`` tile by tile
(a ``--grid`` x ``--grid`` split of the box, each tile retried on the mirrors, merged
on the OSM id), and names each from PDOK's free
Locatieserver (as ``import_bgt`` does). Re-running adds only new benches
(``add_bench_candidate`` upserts on the OSM id).

    BENCH_CITY=utrecht uv run python -m bench_finder.import_osm [--limit N]
"""

from __future__ import annotations

import argparse
import time

from bench_finder.coverage import CITIES, CITY
from bench_finder.import_bgt import address


def fetch_tile(box: tuple[float, float, float, float]) -> list[dict]:
    """Raw Overpass elements for the benches in one tile."""
    from bench_finder.clients.overpass_client import post_with_mirrors

    w, s, e, n = box
    q = f'[out:json][timeout:180];(nwr["amenity"="bench"]({s},{w},{n},{e}););out geom;'
    return post_with_mirrors(q)["elements"]


def tiles(
    box: tuple[float, float, float, float], grid: int
) -> list[tuple[float, float, float, float]]:
    w, s, e, n = box
    dx, dy = (e - w) / grid, (n - s) / grid
    return [
        (w + i * dx, s + j * dy, w + (i + 1) * dx, s + (j + 1) * dy)
        for j in range(grid)
        for i in range(grid)
    ]


def fetch(box: tuple[float, float, float, float], grid: int = 3) -> list:
    """Every OSM bench in the box, as generator candidates."""
    from bench_finder.generators.overpass import OverpassBenchGenerator
    from bench_finder.models.overpass_models import OSMBench, OverpassResponse

    elements: dict[tuple[str, int], dict] = {}
    for k, t in enumerate(tiles(box, grid), 1):
        got = fetch_tile(t)
        for el in got:  # a way crossing a tile edge comes back from both tiles
            elements[(el["type"], el["id"])] = el
        print(f"tile {k}/{grid * grid}: {len(got)} benches", flush=True)
        time.sleep(2)  # Overpass rate limits back-to-back queries
    gen = OverpassBenchGenerator()
    out = []
    raw = OverpassResponse(elements=list(elements.values()))
    for el in raw.elements:
        bench = OSMBench.from_osm_element(el)
        if bench:
            out.append(gen._convert_osm_bench_to_candidate(bench))
    return out


def run(db: str, city: str, limit: int | None, grid: int = 3) -> dict:
    from bench_finder.cli import _deduplicate_bench_candidates
    from bench_finder.models.unified_models import SearchBase
    from bench_finder.services.database import BenchDatabase

    w, s, e, n = box = CITIES[city]
    lat, lng = (s + n) / 2, (w + e) / 2
    found = fetch(box, grid)
    inside = [c for c in found if s <= c.lat <= n and w <= c.lng <= e]
    benches = _deduplicate_bench_candidates(inside)
    if limit:  # a sample around the centre, for trying the chain out
        benches.sort(key=lambda c: (c.lat - lat) ** 2 + (c.lng - lng) ** 2)
        benches = benches[:limit]

    database = BenchDatabase(db_path=db)
    search_id = database.create_search(
        SearchBase(query=city, start_lat=lat, start_lng=lng, search_radius=0)
    )
    added = geocoded = 0
    for c in benches:
        cid = database.add_bench_candidate(
            search_id=search_id,
            provider_id=c.provider_id,
            lat=c.lat,
            lng=c.lng,
            tags=c.tags,
            source=c.source,
            external_id=c.external_id,
            confidence=c.confidence,
        )
        if not cid:
            continue
        added += 1
        if database.get_reverse_geocode(cid):
            continue
        try:
            a = address(c.lat, c.lng)
        except OSError:
            a = None
        if a:
            geocoded += 1
            database.add_or_update_reverse_geocode(
                bench_candidate_id=cid,
                formatted_address=a.get("weergavenaam") or "",
                street_number=str(a.get("huis_nlt") or a.get("huisnummer") or ""),
                street_name=a.get("straatnaam"),
                city=a.get("woonplaatsnaam"),
                state=a.get("provincienaam"),
                postal_code=a.get("postcode"),
                country="Netherlands",
                raw_response=a,
            )
        time.sleep(0.05)  # be gentle with PDOK
    return {
        "city": city,
        "osm": len(found),
        "in_box": len(benches),
        "candidates": added,
        "geocoded": geocoded,
        "search_id": search_id,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--city", default=CITY, choices=sorted(CITIES))
    ap.add_argument("--limit", type=int, help="only the N benches nearest the centre")
    ap.add_argument("--grid", type=int, default=3, help="split the box N x N")
    a = ap.parse_args()
    print(run(a.db, a.city, a.limit, a.grid))


if __name__ == "__main__":
    main()
