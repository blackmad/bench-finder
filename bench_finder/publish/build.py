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

from PIL import Image

from bench_finder.publish.images import (
    FORMATS,
    ImageResult,
    format_widths,
    process_image,
    render_source,
)
from bench_finder.publish.places import group_places


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


def _material(value: Any) -> str | None:
    s = str(value).strip().lower() if value is not None else ""
    return s or None


def _seats(value: Any) -> int | None:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return n if 0 < n < 100 else None


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
               a.axis_only, a.bench_type, a.backrest, a.faces_category, a.faces_text,
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
               i.kind, i.pano_id, i.pano_date, i.camera_bearing_deg, dc.conf
        FROM images i JOIN _pub_ids p ON p.id = i.bench_candidate_id
        -- Aggregated once: a correlated MAX per image let SQLite pick the
        -- has_bench index and scan half the detections table per image.
        LEFT JOIN (
            SELECT image_id, MAX(max_confidence) AS conf FROM detections
            WHERE detection_success = 1 AND has_bench = 1 GROUP BY image_id
        ) dc ON dc.image_id = i.id
        WHERE i.capture_success = 1
        ORDER BY i.id
        """
    ).fetchall()
    by_id: dict[int, dict] = {}
    for r in rows:
        img = dict(r)
        img.update(targets={}, view_labels={})
        by_id[img["id"]] = img
        by_bench.setdefault(r["cid"], []).append(img)
    if not by_id:
        return by_bench

    marks = ",".join("?" * len(TARGET_MODELS))
    scope = (
        "JOIN images i ON i.id = d.image_id "
        "JOIN _pub_ids p ON p.id = i.bench_candidate_id"
    )
    # Which target models ran on each image: a sam3 miss is a verdict too.
    for image_id, model in conn.execute(
        f"SELECT d.image_id, d.model_id FROM detections d {scope} "
        f"WHERE d.detection_success = 1 AND d.model_id IN ({marks})",
        TARGET_MODELS,
    ):
        if image_id in by_id:
            by_id[image_id]["targets"].setdefault(model, (0.0, None))
    # Best target box per image and model (SQLite returns the bbox of the MAX row).
    for image_id, model, conf, bbox in conn.execute(
        f"SELECT d.image_id, d.model_id, MAX(di.confidence), di.bbox FROM detections d "
        f"JOIN detection_items di ON di.detection_id = d.id {scope} "
        f"WHERE d.detection_success = 1 AND di.is_target = 1 AND d.model_id IN ({marks}) "
        "GROUP BY d.image_id, d.model_id",
        TARGET_MODELS,
    ):
        if image_id in by_id:
            by_id[image_id]["targets"][model] = (
                conf or 0.0,
                json.loads(bbox) if bbox else None,
            )
    for image_id, annotator, value in conn.execute(
        "SELECT a.image_id, a.annotator, a.value FROM image_annotations a "
        "JOIN images i ON i.id = a.image_id JOIN _pub_ids p ON p.id = i.bench_candidate_id "
        "WHERE a.label_type = 'view_relation'"
    ):
        if image_id in by_id:
            try:
                v = json.loads(value) if value else None
            except ValueError:
                v = value
            if isinstance(v, str):
                by_id[image_id]["view_labels"][annotator] = v
    # Is the bench hidden behind something? The VLM labeller's answer wins over
    # the local model's (bench_finder.local_occlusion), which only fills gaps.
    for image_id, annotator, value in conn.execute(
        "SELECT a.image_id, a.annotator, a.value FROM image_annotations a "
        "JOIN images i ON i.id = a.image_id JOIN _pub_ids p ON p.id = i.bench_candidate_id "
        "WHERE a.label_type = 'occluded'"
    ):
        if image_id in by_id:
            blocked = value in ("true", "1", 1, True)
            img = by_id[image_id]
            local = annotator.startswith(OCCLUSION_LOCAL_PREFIX)
            if not local or "occluded" not in img:
                img["occluded"] = blocked
    return by_bench


def _resolve(img: dict, images_root: Path) -> Path | None:
    name = img["filename"] or (Path(img["filepath"]).name if img["filepath"] else None)
    if not name:
        return None
    p = images_root / name
    return p if p.is_file() else None


def _source(img: dict, images_root: Path) -> str:
    """The file renditions are cut from: the hi-res re-cut when one exists.

    Decided once per image and cached on it: a re-cut finishing mid-publish
    must not change the answer between cutting renditions and looking them up.
    """
    if "_source" not in img:
        path = _resolve(img, images_root)
        assert path is not None  # only resolvable images are chosen
        img["_source"] = str(render_source(path))
    return img["_source"]


# --------------------------------------------------------------------------- hero ranking

TARGET_MODELS = ("sam3", "yolo11x-seg")
SAM3_MIN = 0.6
YOLO_MIN = 0.25
# Annotators trusted for view_relation, best first; the first real label wins.
OCCLUSION_LOCAL_PREFIX = "ollama/"  # local_occlusion.py's annotator

VIEW_ANNOTATORS = (
    "oracle:",
    "gemini-4-hydrogen",
    "gemini-3.1-flash-lite@v2",  # bench_finder.label_views; best hero picker in the bake-off
    "anthropic/claude-opus",
    "anthropic/",
)
# Where the camera stands relative to the bench. 0 = behind it, seeing what the
# sitter sees; higher is worse for a hero.
VIEW_TIER = {
    "back": 0.0,
    "back-left": 1.0,
    "back-right": 1.0,
    "left": 2.0,
    "right": 2.0,
    "front-left": 3.0,
    "front-right": 3.0,
    "front": 4.0,
}
UNKNOWN_VIEW_TIER = 2.5
BEHIND_DEG = 60.0


def _angle(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def _bearing(img: dict) -> float | None:
    """Where the camera looks. Legacy rows carry a nominal heading, not a real one."""
    if img.get("camera_bearing_deg") is not None:
        return float(img["camera_bearing_deg"])
    if img.get("kind") != "legacy" and img.get("heading") is not None:
        return float(img["heading"])
    return None


def view_label(img: dict) -> str | None:
    """The view_relation from the most trusted annotator that gave a real one."""
    labels: dict[str, str] = img.get("view_labels") or {}
    for prefix in VIEW_ANNOTATORS:
        for annotator in sorted(labels):
            if annotator.startswith(prefix) and labels[annotator] in VIEW_TIER:
                return labels[annotator]
    return None


def _camera_car(img: dict, box: dict | None, h: float = 1024.0) -> bool:
    """A city-panorama target box reaching the bottom edge is the camera car's
    bonnet or roof rack, which SAM 3 and yolo11x-seg both call a bench."""
    name = img.get("filename") or ""
    city = "amsterdam" in name or "TMX" in name or "recording_" in name
    return bool(city and box and float(box["y2"]) >= 0.97 * h)


def target_gate(img: dict) -> tuple[int, float, dict | None]:
    """(tier, confidence, bbox) for the bench the image was aimed at.

    Tier 0: a target detection by sam3 >= 0.6 when sam3 has run on the image (it
    is the stricter model, so its miss counts).
    Tier 1: no such target, but an older detector saw a bench (legacy images).
    Tier 1.5: a yolo11x-seg target >= 0.25 SAM 3 has not checked. Gallery only.
    Tier 2: no bench seen; never a hero.
    """
    t = img.get("targets") or {}
    if "sam3" in t:
        conf, box = t["sam3"]
        if conf >= SAM3_MIN and not _camera_car(img, box):
            return 0, conf, box
    elif "yolo11x-seg" in t:
        conf, box = t["yolo11x-seg"]
        # yolo11x-seg alone is not enough: in wide views it calls the camera
        # car's roof rack, gratings and planters benches. SAM 3 checks its best
        # views (detect_aimed.verify_images); unchecked ones may join a gallery.
        if conf >= YOLO_MIN:
            return 1.5, conf, box
    if not t and (img.get("conf") or 0) > 0:  # legacy: an older detector only
        return 1, float(img["conf"]), None
    return 2, 0.0, None


def _box_score(box: dict | None, size: tuple[int, int] | None) -> float:
    """0..1: a bigger, more central target box scores higher."""
    if not box:
        return 0.0
    w, h = size or (1024, 1024)
    x1, y1, x2, y2 = (float(box[k]) for k in ("x1", "y1", "x2", "y2"))
    area = max(0.0, (x2 - x1) * (y2 - y1)) / float(w * h)
    centre = 1 - min(1.0, abs((x1 + x2) / 2 / w - 0.5) * 2)
    return 0.5 * min(1.0, area / 0.12) + 0.5 * centre


def image_rank(
    img: dict, facing: float | None, size: tuple[int, int] | None = None
) -> tuple:
    """Sort key for the hero and the "More views" order (smaller is better).

    1. Target gate (``target_gate``): a confirmed detection of the aimed-at bench
       first, then legacy detections, then images where no bench was seen.
       Within a gate, views labelled ``occluded`` come after unblocked ones, then
       winter views (December to February: snow, bare trees) after the rest.
    2. View relation: the camera behind the bench (the sitter's view) beats the
       back corners, then the sides, then the front. A trusted label decides
       (``VIEW_ANNOTATORS``, oracle first). Without one, when the bench's facing
       is known (attributes or the OSM ``direction`` tag), geometry decides: a
       camera looking within 60 deg of the facing stands behind the bench,
       within 120 deg beside it, otherwise in front. Unlabelled views of benches
       with no facing rank between side and front views.
    3. With a known facing, the angle between camera and facing breaks ties
       (so of a "back-left" and a "back-right" view the more square one wins).
    4. Size and centrality of the target box, then its confidence.
    5. The newest panorama, then the image id (stable).
    """
    gate, conf, box = target_gate(img)
    bearing = _bearing(img)
    diff = (
        _angle(bearing, facing) if bearing is not None and facing is not None else None
    )
    label = view_label(img)
    if label is not None:
        tier = VIEW_TIER[label]
    elif diff is not None:
        tier = 0.0 if diff <= BEHIND_DEG else 2.0 if diff <= 2 * BEHIND_DEG else 4.0
    else:
        tier = UNKNOWN_VIEW_TIER
    digits = re.sub(r"\D", "", img.get("pano_date") or "")[:6]
    return (
        gate,
        bool(img.get("occluded")),  # a bench hidden behind a hedge or car loses
        _winter(img),  # snow, bare trees and grey skies lose to a summer view
        tier,
        diff / 180 if diff is not None else 0.5,
        -round(_box_score(box, size), 3),
        -round(conf, 3),
        -int(digits or 0),
        img["id"],
    )


WINTER_MONTHS = {12, 1, 2}


def _winter(img: dict) -> bool:
    m = re.match(r"\d{4}-(\d{2})", img.get("pano_date") or "")
    return bool(m) and int(m.group(1)) in WINTER_MONTHS


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as im:
            return im.size
    except OSError:
        return None


def _order_images(
    imgs: list[dict],
    hero_id: int | None,
    n: int,
    root: Path,
    facing: float | None = None,
) -> tuple[list[dict], bool]:
    """(images, has_hero): ranked by ``image_rank``; a manually chosen hero leads."""
    usable = [(i, p) for i in imgs if (p := _resolve(i, root))]
    ranked = [
        i
        for i, _ in sorted(
            usable,
            key=lambda ip: image_rank(
                ip[0],
                facing,
                _image_size(ip[1]) if target_gate(ip[0])[2] else None,
            ),
        )
    ]
    hero = next((i for i in ranked if i["id"] == hero_id), None)
    if hero is None and ranked and target_gate(ranked[0])[0] < 1.5:
        hero = ranked[0]
    rest = [i for i in ranked if i is not hero]
    if hero is not None and (hy := _year(hero)):
        # Benches get replaced: a view years older than the hero may show the
        # old one (Museumplein: red metal in 2021, wood since 2022).
        rest = [
            i for i in rest if (y := _year(i)) is None or y >= hy - MAX_GALLERY_AGE_Y
        ]
    return (([hero] if hero else []) + rest)[:n], hero is not None


MAX_GALLERY_AGE_Y = 3


def _year(img: dict) -> int | None:
    m = re.match(r"(\d{4})", img.get("pano_date") or "")
    return int(m.group(1)) if m else None


def _rank_facing(r: sqlite3.Row) -> float | None:
    """The facing the hero ranking trusts: a direction, not just an axis."""
    if r["axis_only"]:
        return None
    if r["facing_deg"] is not None:
        return float(r["facing_deg"])
    tags = json.loads(r["tags"]) if r["tags"] else {}
    return parse_direction(tags.get("direction"))


# --------------------------------------------------------------------------- build


def _urls(digest: str, widths: tuple[int, ...], fmt: str) -> dict[str, str]:
    return {str(w): f"img/{digest}-{w}.{fmt}" for w in format_widths(widths, fmt)}


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


def select_images(
    conn: sqlite3.Connection,
    images_root: Path,
    include_unclassified: bool = False,
    limit: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    gallery_size: int = 4,
) -> tuple[list[sqlite3.Row], int, dict[int, tuple[list[dict], bool]]]:
    """(rows, eligible, {bench id: (ordered images, has_hero)}) exactly as published."""
    rows, eligible = _load_rows(conn, include_unclassified, limit, bbox)
    imgs_by_bench = _load_images(conn, [r["id"] for r in rows])
    chosen = {
        r["id"]: _order_images(
            imgs_by_bench.get(r["id"], []),
            r["hero_image_id"],
            gallery_size,
            images_root,
            _rank_facing(r),
        )
        for r in rows
    }
    return rows, eligible, chosen


def _place_rank(d: dict) -> tuple:
    """Best representative first: a photo, then what it looks at, then a facing."""
    return (
        d["hero_urls"] is None,
        d["faces_category"] is None,
        d["facing"] is None,
        -len(d["gallery"]),
        d["id"],
    )


_MEMBER_KEYS = (
    "id",
    "lat",
    "lng",
    "address",
    "facing",
    "facing_confidence",
    "facing_method",
    "axis_only",
    "backrest",
    "bench_type",
    "faces_category",
    "hero_key",
    "hero_urls",
    "hero_urls_webp",
    "hero_width",
    "hero_height",
)


def _group_into_places(features: list[dict], details: list[dict]) -> list[dict]:
    """One feature per place (benches a few metres apart; see ``places``).

    The place carries its best bench's props plus ``bench_ids`` and ``count``;
    backrest is true if any member has one, and looks-at falls back to a member's.
    Every bench keeps its own detail file, which gains ``place`` (the others).
    """
    feat = {f["id"]: f for f in features}
    det = {d["id"]: d for d in details}
    order = sorted(det.values(), key=_place_rank)
    places = group_places([(d["id"], d["lat"], d["lng"]) for d in order])
    out = []
    for members in places:
        f = feat[members[0]]
        props = dict(f["properties"])
        ms = [det[m] for m in members]
        props["bench_ids"] = members
        props["count"] = len(members)
        if any(m["backrest"] is True for m in ms):
            props["backrest"] = True
        if props["faces_category"] is None:
            props["faces_category"] = next(
                (m["faces_category"] for m in ms if m["faces_category"]), None
            )
        if len(ms) > 1 and all(m["seats"] for m in ms):
            props["seats"] = sum(m["seats"] for m in ms)
        out.append({**f, "properties": props})
        for m in ms:
            m["place"] = {
                "id": members[0],
                "count": len(members),
                "benches": [
                    {k: o[k] for k in _MEMBER_KEYS} for o in ms if o["id"] != m["id"]
                ],
            }
    return out


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
        rows, eligible, chosen = select_images(
            conn, images_root, include_unclassified, limit, bbox, gallery_size
        )
    finally:
        conn.close()

    sources = sorted({_source(i, images_root) for v, _ in chosen.values() for i in v})

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
            res = results[_source(i, images_root)]
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
            # OSM tags the home-page filters use; the rest stay in the bench file.
            "material": _material(tags.get("material")),
            "seats": _seats(tags.get("seats")),
            "lit": _tri(tags.get("lit")),
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
                "tags": {k: v for k, v in tags.items() if v is not None},
                "address_full": {
                    "street": street,
                    "number": number,
                    "postcode": r["postal_code"],
                    "city": r["city"],
                    "country": r["country"],
                },
                "faces_text": r["faces_text"],
                "gallery": [e for e, _, _ in entries],
                "embed_pano_id": pano,
                "embed_heading_deg": round(pano_heading, 1)
                if pano_heading is not None
                else None,
            }
        )

    n_benches = len(features)
    features = _group_into_places(features, details)

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
            "count": len(features),  # places: one feature per place
            "benches": gname,
            "bench_dir": "bench",
            "data_base": "data",
            "image_base": "img",
            "counts": {
                "benches": n_benches,
                "places": len(features),
                "with_hero": hero_count,
                "images": len(sources),
            },
        },
    )

    res = PublishResult(
        out=out, benches=n_benches, with_hero=hero_count, images=len(sources)
    )
    res.derivatives_written = sum(r.generated for r in results.values())
    res.geojson_name, res.geojson_bytes, res.geojson_gz_bytes = gname, len(fc), gz
    # Only images this publish uses count: older renditions stay on disk but
    # the upload prunes them from the bucket.
    from bench_finder.publish.upload import live_keys

    live_imgs = [out / k for k in live_keys(out) if k.startswith("img/")]
    res.image_bytes = sum(p.stat().st_size for p in live_imgs if p.is_file())
    n_img = len(live_imgs)
    bench_json_bytes, n_json = _dir_bytes(out, "data/bench/*.json")
    res.json_bytes = bench_json_bytes + (out / "manifest.json").stat().st_size
    res.file_counts = {"img": n_img, "bench_json": n_json, "geojson": 1, "manifest": 1}
    res.eligible = eligible
    scale = eligible / n_benches if n_benches else 1.0
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
