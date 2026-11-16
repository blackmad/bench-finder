"""Import the city's registered benches (BGT/IMGeo straatmeubilair, plusType "bank").

Amsterdam's open-data API lists 3,344 benches, almost all in the outer districts
(Noord, Nieuw-West, the docks, around Zuidoost) and almost none of them in
OpenStreetMap. Each one at least ``DEDUPE_M`` from every existing candidate
becomes a ``bench_candidates`` row (source ``BGT``, status pending, under one new
search), with its address from PDOK's free reverse geocoder. The usual pipeline
then takes over: ``bench-finder fetch-images --search-id N``, detection, labels.

    uv run python -m bench_finder.import_bgt [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime

from pyproj import Transformer


API = "https://api.data.amsterdam.nl/v1/bgt/straatmeubilair/?_format=json&plusType=bank&_pageSize=1000"
PDOK = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/reverse"
DEDUPE_M = 15.0
UA = {"User-Agent": "bench-finder (BGT import)"}


def _get(url: str) -> dict:
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=60
    ) as r:
        return json.loads(r.read())


def fetch_bgt() -> list[tuple[str, float, float]]:
    """(identificatie, lat, lng) for every registered bench point."""
    tr = Transformer.from_crs(28992, 4326, always_xy=True)
    out, url = [], API
    while url:
        d = _get(url)
        for r in d["_embedded"]["straatmeubilair"]:
            g = r.get("geometrie") or {}
            if g.get("type") == "Point":
                lng, lat = tr.transform(*g["coordinates"][:2])
                out.append((r["identificatie"], lat, lng))
        url = (d.get("_links", {}).get("next") or {}).get("href")
    return out


def metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    x = (b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(x, b[0] - a[0]) * 111_320


def address(lat: float, lng: float) -> dict | None:
    q = urllib.parse.urlencode(
        {"lat": lat, "lon": lng, "rows": 1, "type": "adres", "fl": "*"}
    )
    docs = _get(f"{PDOK}?{q}")["response"]["docs"]
    return docs[0] if docs else None


def run(db: str, dry_run: bool) -> dict:
    bgt = fetch_bgt()
    conn = sqlite3.connect(db, timeout=300)
    grid: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for lat, lng in conn.execute("SELECT lat, lng FROM bench_candidates"):
        grid[(round(lat * 1000), round(lng * 1000))].append((lat, lng))
    seen = {
        e
        for (e,) in conn.execute(
            "SELECT external_id FROM bench_candidates WHERE source='BGT'"
        )
    }
    new = []
    for ident, lat, lng in bgt:
        if ident in seen:
            continue
        key = (round(lat * 1000), round(lng * 1000))
        near = any(
            metres((lat, lng), p) < DEDUPE_M
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
            for p in grid.get((key[0] + dy, key[1] + dx), ())
        )
        if not near:
            new.append((ident, lat, lng))
            grid[key].append((lat, lng))  # BGT points closer than 15 m stay one bench
    if dry_run:
        return {"bgt": len(bgt), "new": len(new), "dry_run": True}
    now = datetime.now(UTC).isoformat(sep=" ")
    lat0 = sum(p[1] for p in new) / max(len(new), 1)
    lng0 = sum(p[2] for p in new) / max(len(new), 1)
    cur = conn.execute(
        "INSERT INTO searches (query, start_lat, start_lng, search_radius, created_at, status) "
        "VALUES ('amsterdam-bgt', ?, ?, 0, ?, 'completed')",
        (lat0, lng0, now),
    )
    search_id = cur.lastrowid
    geocoded = 0
    for ident, lat, lng in new:
        c = conn.execute(
            "INSERT INTO bench_candidates (search_id, provider_id, lat, lng, tags, source, "
            "external_id, confidence, created_at, status) VALUES (?,?,?,?,?, 'BGT', ?, 1.0, ?, 'PENDING')",
            (
                search_id,
                f"bgt_{ident}",
                lat,
                lng,
                json.dumps({"amenity": "bench", "source": "BGT Amsterdam"}),
                ident,
                now,
            ),
        )
        try:
            a = address(lat, lng)
        except OSError:
            a = None
        if a:
            geocoded += 1
            conn.execute(
                "INSERT INTO reverse_geocodes (bench_candidate_id, formatted_address, raw_response, "
                "created_at, updated_at, street_number, street_name, city, state, postal_code, country) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    c.lastrowid,
                    a.get("weergavenaam"),
                    json.dumps(a),
                    now,
                    now,
                    str(a.get("huis_nlt") or a.get("huisnummer") or ""),
                    a.get("straatnaam"),
                    a.get("woonplaatsnaam"),
                    a.get("provincienaam"),
                    a.get("postcode"),
                    "Netherlands",
                ),
            )
        conn.commit()
        time.sleep(0.05)  # be gentle with PDOK
    return {
        "bgt": len(bgt),
        "new": len(new),
        "geocoded": geocoded,
        "search_id": search_id,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(run(a.db, a.dry_run))


if __name__ == "__main__":
    main()
