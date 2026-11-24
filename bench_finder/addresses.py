"""Bench addresses from the street they are on (PDOK Locatieserver, Dutch BAG/NWB).

Google's reverse geocode names the nearest building's address point, which on a
corner or a quay is often a building round the corner (Lauriergracht 146 for a
bench on the Elandsgracht, 2026-11-18). Here the street is the nearest named
road (NWB), and the number the nearest BAG address on that street.

    uv run python -m bench_finder.addresses fetch      # cache data/pdok_addresses.jsonl
    uv run python -m bench_finder.addresses compare    # how many differ from Google
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

import aiohttp

from bench_finder.coverage import city_cache


CACHE = city_cache("data/pdok_addresses.jsonl")  # keyed by bench id
API = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/reverse"
NUMBER_MAX_M = 40.0  # farther than this, name the street only ("Vondelpark" paths)


def load(cache: Path = CACHE) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if cache.exists():
        for line in cache.read_text().splitlines():
            r = json.loads(line)
            out[r["id"]] = r
    return out


ON_STREET_M = 25.0  # nearer than this the bench is on the street; else in a park/square


def address(r: dict, google: str | None = None) -> str | None:
    """'Elandsgracht 148', or 'Elandsgracht' when no number on it is close.

    Off the street (a park, a square behind buildings) Google's name is kept
    unless it is a plus code ('9V5F+V2 Amsterdam')."""
    street = r.get("street")
    off_street = r.get("street_m") is None or r["street_m"] > ON_STREET_M
    if google and "+" not in google and (off_street or not street):
        return google
    if not street:
        return None
    for a in r.get("addresses", []):
        n = str(a.get("number") or "")
        # Bridges carry their own register numbers ("Halvemaansbrug 0221").
        if a["street"] == street and a["m"] <= NUMBER_MAX_M and not n.startswith("0"):
            return f"{street} {n}{a.get('letter') or ''}"
    return street


async def _get(session, lat: float, lng: float, kind: str, rows: int) -> list[dict]:
    params = {
        "lat": lat,
        "lon": lng,
        "type": kind,
        "rows": rows,
        "fl": "straatnaam,huisnummer,huisletter,afstand",
    }
    for attempt in range(4):
        try:
            async with session.get(API, params=params) as r:
                r.raise_for_status()
                return (await r.json())["response"]["docs"]
        except (TimeoutError, aiohttp.ClientError):
            await asyncio.sleep(2**attempt)
    raise RuntimeError("PDOK unreachable")


async def _fetch(db: str) -> dict:
    from bench_finder.vantage import load_benches

    done = load()
    todo = [b for b in load_benches(db) if b.id not in done]
    sem = asyncio.Semaphore(6)
    stats = {"todo": len(todo), "fetched": 0, "failed": 0}
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        headers={"User-Agent": "bench-finder"},
    ) as session:

        async def one(b) -> None:
            async with sem:
                try:
                    roads = await _get(session, b.lat, b.lng, "weg", 1)
                    addrs = await _get(session, b.lat, b.lng, "adres", 15)
                except RuntimeError:
                    stats["failed"] += 1
                    return
            rec = {
                "id": b.id,
                "street": roads[0].get("straatnaam") if roads else None,
                "street_m": round(roads[0]["afstand"], 1) if roads else None,
                "addresses": [
                    {
                        "street": a.get("straatnaam"),
                        "number": a.get("huisnummer"),
                        "letter": a.get("huisletter"),
                        "m": round(a["afstand"], 1),
                    }
                    for a in addrs
                ],
            }
            with CACHE.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            stats["fetched"] += 1
            if stats["fetched"] % 500 == 0:
                print(stats, flush=True)

        await asyncio.gather(*(one(b) for b in todo))
    return stats


def compare(db: str) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    google = dict(
        conn.execute("SELECT bench_candidate_id, street_name FROM reverse_geocodes")
    )
    conn.close()
    stats = {"benches": 0, "same_street": 0, "other_street": 0, "no_google": 0}
    examples = []
    import random

    rng = random.Random(2)
    for bid, r in load().items():
        old = google.get(bid)
        new = address(r, old)
        if not new:
            continue
        stats["benches"] += 1
        if not old:
            stats["no_google"] += 1
        elif old == new or old.startswith(new.split(" ")[0] if False else new.rsplit(" ", 1)[0]):
            stats["same_street"] += 1
        else:
            stats["other_street"] += 1
            examples.append((bid, old, new))
    return {**stats, "examples": rng.sample(examples, min(20, len(examples)))}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("cmd", choices=["fetch", "compare"])
    ap.add_argument("--db", default="data/benches.db")
    a = ap.parse_args()
    if a.cmd == "fetch":
        print(asyncio.run(_fetch(a.db)))
    else:
        for k, v in compare(a.db).items():
            print(k, v)


if __name__ == "__main__":
    main()
