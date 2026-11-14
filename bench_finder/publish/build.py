"""Select publishable benches and write the static data set (images, GeoJSON, JSON, manifest).

Output layout under ``out``::

    manifest.json
    data/benches.<hash>.geojson
    data/bench/<id>.json
    img/<hash>-<w>.avif|webp
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bench_finder.publish.images import FORMATS, ImageResult, process_image


if TYPE_CHECKING:
    from collections.abc import Callable

SCHEMA_VERSION = 1
GEOJSON_GZ_LIMIT = 500 * 1000
DEFAULT_BUDGET_BYTES = 9 * 10**9  # under R2's 10 GB free tier
COORD_DECIMALS = 6

_WINDS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]  # fmt: skip
_WIND_DEG = {w: i * 22.5 for i, w in enumerate(_WINDS)}


class CapacityError(RuntimeError):
    """Projected output exceeds the free-tier budget or the GeoJSON size cap."""


@dataclass
class PublishResult:
    out: Path
    benches: int = 0
    with_hero: int = 0
    images: int = 0
    derivatives_written: int = 0
    geojson_name: str = ""
    geojson_bytes: int = 0
    geojson_gz_bytes: int = 0
    image_bytes: int = 0
    json_bytes: int = 0
    file_counts: dict[str, int] = field(default_factory=dict)
    eligible: int = 0
    projected_total_bytes: int = 0
    projected_geojson_gz_bytes: int = 0
    seconds: float = 0.0

    @property
    def total_bytes(self) -> int:
        return self.image_bytes + self.json_bytes + self.geojson_bytes


def parse_direction(value: Any) -> float | None:
    """OSM ``direction`` tag: degrees ("120") or 16-wind letters ("SSW")."""
    if value is None:
        return None
    s = str(value).strip().upper()
    if s in _WIND_DEG:
        return _WIND_DEG[s]
    if re.fullmatch(r"\d{1,3}(\.\d+)?", s):
        deg = float(s)
        if deg <= 360:
            return round(deg % 360, 1)
    return None


def _tri(value: Any) -> bool | None:
    s = str(value).strip().lower() if value is not None else ""
    return True if s == "yes" else False if s == "no" else None


def check_capacity(
    projected_total_bytes: int,
    projected_geojson_gz_bytes: int,
    budget_bytes: int = DEFAULT_BUDGET_BYTES,
    geojson_gz_limit: int = GEOJSON_GZ_LIMIT,
) -> list[str]:
    """Return human-readable violations (empty list = OK)."""
    problems = []
    if projected_total_bytes > budget_bytes:
        problems.append(
            f"projected R2 storage {projected_total_bytes / 1e9:.2f} GB exceeds budget "
            f"{budget_bytes / 1e9:.2f} GB"
        )
    if projected_geojson_gz_bytes > geojson_gz_limit:
        problems.append(
            f"GeoJSON gzip size {projected_geojson_gz_bytes / 1e3:.0f} kB exceeds "
            f"{geojson_gz_limit / 1e3:.0f} kB"
        )
    return problems


# --------------------------------------------------------------------------- selection


# Launch coverage (owner decision 2026-11-14): Amsterdam only. (west, south, east, north)
AMSTERDAM_BBOX = (4.72, 52.27, 5.08, 52.44)


def _load_rows(
    conn: sqlite3.Connection,
    include_unclassified: bool,
    limit: int | None,
    bbox: tuple[float, float, float, float] | None = None,
):
    conn.row_factory = sqlite3.Row
    where = "a.id IS NOT NULL"
    if include_unclassified:
        where = "(a.id IS NOT NULL OR g.id IS NOT NULL)"
    params: list[float] = []
    if bbox is not None:
        where += " AND c.lng BETWEEN ? AND ? AND c.lat BETWEEN ? AND ?"
        params = [bbox[0], bbox[2], bbox[1], bbox[3]]
    sql = f"""
        SELECT c.id, c.lat, c.lng, c.tags,
               a.id AS attr_id, a.facing_deg, a.facing_confidence, a.facing_method,
               a.axis_only, a.bench_type, a.backrest, a.faces_category,
               a.hero_image_id, a.embed_pano_id, a.embed_heading_deg,
               g.formatted_address, g.street_name, g.street_number, g.postal_code,
               g.city, g.country
        FROM bench_candidates c
        LEFT JOIN bench_attributes a ON a.bench_candidate_id = c.id
        LEFT JOIN reverse_geocodes g ON g.bench_candidate_id = c.id
        WHERE {where}
        ORDER BY c.id
    """
    rows = conn.execute(sql, params).fetchall()
    eligible = len(rows)
    if limit is not None:
        rows = rows[:limit]
    return rows, eligible


def _load_images(conn: sqlite3.Connection, ids: list[int]) -> dict[int, list[dict]]:
    by_bench: dict[int, list[dict]] = {}
    if not ids:
        return by_bench
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _pub_ids (id INTEGER PRIMARY KEY)")
    conn.execute("DELETE FROM _pub_ids")
    conn.executemany("INSERT INTO _pub_ids VALUES (?)", [(i,) for i in ids])
    rows = conn.execute(
        """
        SELECT i.id, i.bench_candidate_id AS cid, i.filename, i.filepath, i.heading,
               i.kind, i.pano_id, i.pano_date, i.camera_bearing_deg,
               (SELECT MAX(d.max_confidence) FROM detections d
                 WHERE d.image_id = i.id AND d.detection_success = 1 AND d.has_bench = 1) AS conf
        FROM images i JOIN _pub_ids p ON p.id = i.bench_candidate_id
        WHERE i.capture_success = 1
        ORDER BY i.id
        """
    ).fetchall()
    for r in rows:
        by_bench.setdefault(r["cid"], []).append(dict(r))
    return by_bench


def _resolve(img: dict, images_root: Path) -> Path | None:
    name = img["filename"] or (Path(img["filepath"]).name if img["filepath"] else None)
    if not name:
        return None
    p = images_root / name
    return p if p.is_file() else None


def _order_images(
    imgs: list[dict], hero_id: int | None, n: int, root: Path
) -> tuple[list[dict], bool]:
    """(images, has_hero): hero first, then aimed views, then the rest by confidence."""
    usable = [i for i in imgs if _resolve(i, root)]
    by_conf = sorted(usable, key=lambda i: -(i["conf"] or 0.0))
    hero = next((i for i in usable if i["id"] == hero_id), None)
    if hero is None:
        # Prefer an aimed view whose target bench was detected (detect_aimed sets
        # has_bench only for a hit on the centre column), then any detection.
        hero = next(
            (i for i in by_conf if i["kind"] == "aimed" and (i["conf"] or 0) > 0), None
        ) or next((i for i in by_conf if (i["conf"] or 0) > 0), None)
    rest = [i for i in by_conf if i is not hero]
    rest.sort(key=lambda i: i["kind"] != "aimed")  # stable: aimed first
    ordered = ([hero] if hero else []) + rest
    return ordered[:n], hero is not None


# --------------------------------------------------------------------------- build


def _urls(digest: str, widths: tuple[int, ...], fmt: str) -> dict[str, str]:
    return {str(w): f"img/{digest}-{w}.{fmt}" for w in widths}


def _image_entry(res: ImageResult, img: dict) -> dict:
    return {
        "urls": _urls(res.hash, res.widths, "avif"),
        "urls_webp": _urls(res.hash, res.widths, "webp"),
        "width": res.width,
        "height": res.height,
        "heading": img["heading"],
        "camera_bearing_deg": (
            round(img["camera_bearing_deg"], 1)
            if img["camera_bearing_deg"] is not None
            else None
        ),
        "kind": img["kind"],
        "pano_date": img["pano_date"],
    }


def _write_json(path: Path, obj: Any) -> int:
    data = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return len(data)


def _dir_bytes(root: Path, pattern: str) -> tuple[int, int]:
    files = [
        p for p in root.glob(pattern) if p.is_file() and not p.name.endswith(".tmp")
    ]
    return sum(p.stat().st_size for p in files), len(files)


def publish(
    db_path: str | Path,
    images_root: str | Path,
    out: str | Path,
    *,
    include_unclassified: bool = False,
    limit: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    gallery_size: int = 4,
    workers: int | None = None,
    budget_bytes: int = DEFAULT_BUDGET_BYTES,
    progress: Callable[[int, int], None] | None = None,
) -> PublishResult:
    """Build the data set into ``out``. Raises ``CapacityError`` after writing if over budget."""
    t0 = time.time()
    out, images_root = Path(out), Path(images_root)
    out.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows, eligible = _load_rows(conn, include_unclassified, limit, bbox)
        imgs_by_bench = _load_images(conn, [r["id"] for r in rows])
    finally:
        conn.close()

    chosen = {
        r["id"]: _order_images(
            imgs_by_bench.get(r["id"], []),
            r["hero_image_id"],
            gallery_size,
            images_root,
        )
        for r in rows
    }
    sources = sorted(
        {str(_resolve(i, images_root)) for v, _ in chosen.values() for i in v}
    )

    results: dict[str, ImageResult] = {}
    if sources:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for n, (src, res) in enumerate(
                zip(
                    sources,
                    pool.map(
                        process_image, sources, [str(out)] * len(sources), chunksize=4
                    ),
                    strict=True,
                ),
                1,
            ):
                results[src] = res
                if progress:
                    progress(n, len(sources))

    features, details, hero_count = [], [], 0
    for r in rows:
        tags = json.loads(r["tags"]) if r["tags"] else {}
        tag_deg = parse_direction(tags.get("direction"))
        facing, conf, method = (
            r["facing_deg"],
            r["facing_confidence"],
            r["facing_method"],
        )
        if facing is None and tag_deg is not None:
            facing, conf, method = tag_deg, 1.0, "osm_tag"
        imgs, has_hero = chosen[r["id"]]
        entries = []
        for i in imgs:
            res = results[str(_resolve(i, images_root))]
            entries.append((_image_entry(res, i), i, res))
        hero = entries[0][0] if has_hero else None
        hero_key = entries[0][2].hash if has_hero else None
        hero_count += has_hero
        street = r["street_name"]
        number = r["street_number"]
        short = (
            " ".join(str(x) for x in (street, number) if x).strip()
            if street
            else (r["formatted_address"] or "").split(",")[0] or None
        )
        aimed = next(
            (i for _, i, _ in entries if i["kind"] == "aimed" and i["pano_id"]), None
        )
        pano = r["embed_pano_id"] or (aimed["pano_id"] if aimed else None)
        pano_heading = (
            r["embed_heading_deg"]
            if r["embed_pano_id"]
            else (aimed["camera_bearing_deg"] if aimed else None)
        )
        props = {
            "id": r["id"],
            "lat": round(r["lat"], COORD_DECIMALS),
            "lng": round(r["lng"], COORD_DECIMALS),
            "facing": round(facing, 1) if facing is not None else None,
            "facing_confidence": round(conf, 2) if conf is not None else None,
            "facing_method": method if facing is not None else None,
            "axis_only": bool(r["axis_only"]),
            "bench_type": r["bench_type"],
            "backrest": r["backrest"]
            if r["backrest"] is not None
            else _tri(tags.get("backrest")),
            "faces_category": r["faces_category"],
            "hero_key": hero_key,
            "hero_urls": hero["urls"] if hero else None,
            "hero_urls_webp": hero["urls_webp"] if hero else None,
            "hero_width": hero["width"] if hero else None,
            "hero_height": hero["height"] if hero else None,
            "address": short,
        }
        if isinstance(props["backrest"], int):
            props["backrest"] = bool(props["backrest"])
        features.append(
            {
                "type": "Feature",
                "id": r["id"],
                "geometry": {
                    "type": "Point",
                    "coordinates": [props["lng"], props["lat"]],
                },
                "properties": props,
            }
        )
        details.append(
            {
                **props,
                "material": tags.get("material"),
                "tags": {k: v for k, v in tags.items() if v is not None},
                "address_full": {
                    "street": street,
                    "number": number,
                    "postcode": r["postal_code"],
                    "city": r["city"],
                    "country": r["country"],
                },
                "gallery": [e for e, _, _ in entries],
                "embed_pano_id": pano,
                "embed_heading_deg": round(pano_heading, 1)
                if pano_heading is not None
                else None,
            }
        )

    # Write data. Drop stale hashed GeoJSON so only the current one remains locally.
    data_dir = out / "data"
    data_dir.mkdir(exist_ok=True)
    for old in data_dir.glob("benches.*.geojson"):
        old.unlink()
    for d in details:
        _write_json(data_dir / "bench" / f"{d['id']}.json", d)
    fc = json.dumps(
        {"type": "FeatureCollection", "features": features},
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    gname = f"benches.{hashlib.sha256(fc).hexdigest()[:10]}.geojson"
    (data_dir / gname).write_bytes(fc)
    gz = len(gzip.compress(fc, 9))

    _write_json(
        out / "manifest.json",
        {
            "version": SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "count": len(features),
            "benches": gname,
            "bench_dir": "bench",
            "data_base": "data",
            "image_base": "img",
            "counts": {
                "benches": len(features),
                "with_hero": hero_count,
                "images": len(sources),
            },
        },
    )

    res = PublishResult(
        out=out, benches=len(features), with_hero=hero_count, images=len(sources)
    )
    res.derivatives_written = sum(r.generated for r in results.values())
    res.geojson_name, res.geojson_bytes, res.geojson_gz_bytes = gname, len(fc), gz
    res.image_bytes, n_img = _dir_bytes(out, "img/*")
    bench_json_bytes, n_json = _dir_bytes(out, "data/bench/*.json")
    res.json_bytes = bench_json_bytes + (out / "manifest.json").stat().st_size
    res.file_counts = {"img": n_img, "bench_json": n_json, "geojson": 1, "manifest": 1}
    res.eligible = eligible
    scale = eligible / len(features) if features else 1.0
    res.projected_total_bytes = int(res.total_bytes * scale)
    res.projected_geojson_gz_bytes = int(gz * scale)
    res.seconds = time.time() - t0
    problems = check_capacity(
        res.projected_total_bytes, res.projected_geojson_gz_bytes, budget_bytes
    )
    if problems:
        err = CapacityError("; ".join(problems))
        err.result = res  # type: ignore[attr-defined]
        raise err
    return res


__all__ = ["FORMATS", "CapacityError", "PublishResult", "check_capacity", "publish"]
