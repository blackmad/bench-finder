"""Imagery sweep for unmapped benches: the city's panoramas along the water.

OSM and the city register (BGT) miss benches (the owner's Baarsjesweg bench,
2026-11-19). This looks for benches in the City of Amsterdam's own 360°
panoramas near water and keeps those seen from 2+ panoramas that are not
already known.

Stages (each cached under ``data/sweep/<area>/``, safe to re-run):

    uv run python -m bench_finder.sweep panos   --area kvv   # panoramas within NEAR_WATER_M of water
    uv run python -m bench_finder.sweep detect  --area kvv   # 8 views each, YOLO; crops of hits
    uv run --group detect-extra python -m bench_finder.sweep confirm --area kvv  # SAM 3 on YOLO hits
                                                              # (+ every view of a sample, to measure
                                                              #  what the YOLO gate loses)
    uv run python -m bench_finder.sweep cluster --area kvv   # rays -> points (2+ panoramas)
    uv run python -m bench_finder.sweep page    --area kvv   # review page: data/sweep/kvv/index.html

A detection is a ray: from the panorama, along the compass bearing of the box
centre. Rays from different panoramas that cross within ``INLIER_M`` make a
point (RANSAC, greedy: best point, drop its rays, repeat). A point within
``KNOWN_M`` of a bench we already have is "known" (that also measures recall:
what share of the known benches by the water the sweep finds).
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import math
import random
import sqlite3
import time
from pathlib import Path

import numpy as np
from PIL import Image

AREAS = {
    # Kostverlorenvaart, southern stretch: Postjeswetering / Admiralengracht
    # junction (the owner's missing bench, 52.3645, 4.8578) up to Jan Evertsenstraat.
    "kvv": (4.850, 52.356, 4.868, 52.372),
}
CHECKS = {"kvv": [("owner: Baarsjesweg 224, behind the quay wall", 52.36447, 4.85772)]}
API = "https://api.data.amsterdam.nl/panorama/panoramas/"
UA = {"User-Agent": "bench-finder (sweep)"}
NEAR_WATER_M = 25.0
SPOT_M = 4.0  # one panorama per spot (newest)
HEADINGS = [0, 45, 90, 135, 180, 225, 270, 315]
FOV = 60.0
VIEW_PX = 1024
YOLO_FLOOR = 0.10
SAM3_MIN = 0.5
SAMPLE_ALL = 0.10  # share of panoramas whose every view SAM 3 checks (gate audit)
MAX_RANGE_M = 30.0
INLIER_M = 1.5
MIN_SPREAD_DEG = 12.0
KNOWN_M = 15.0
M_LAT = 110_574.0


def _m_lng(lat: float) -> float:
    return 111_320.0 * math.cos(math.radians(lat))


def area_dir(area: str) -> Path:
    d = Path("data/sweep") / area
    (d / "views").mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------ panoramas


def _water(bbox):
    from shapely.geometry import Polygon, box
    from shapely.strtree import STRtree

    w, s, e, n = bbox
    pad = 0.001
    clip = box(w - pad, s - pad, e + pad, n + pad)
    lat0 = (s + n) / 2
    k = _m_lng(lat0)
    shapes = []
    for ring in json.loads(Path("data/osm_water.json").read_text()):
        p = Polygon(ring)
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty or not p.intersects(clip):
            continue
        shapes.append(
            Polygon([((x - w) * k, (y - s) * M_LAT) for x, y in ring]).buffer(0).boundary
        )
    return shapes, STRtree(shapes), (w, s, k)


async def _panos(bbox) -> list[dict]:
    import aiohttp

    w, s, e, n = bbox
    lat0 = (s + n) / 2
    step = 120.0  # metres between query centres; radius covers the diagonal
    pts = [
        (s + (j + 0.5) * step / M_LAT, w + (i + 0.5) * step / _m_lng(lat0))
        for i in range(int((e - w) * _m_lng(lat0) / step) + 1)
        for j in range(int((n - s) * M_LAT / step) + 1)
    ]
    out: dict[str, dict] = {}
    sem = asyncio.Semaphore(6)
    async with aiohttp.ClientSession(headers=UA) as session:

        async def one(lat, lng):
            url = f"{API}?near={lng},{lat}&radius=90&newest_in_range=true&page_size=2000"
            async with sem:
                for attempt in range(4):
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=90)) as r:
                            r.raise_for_status()
                            data = await r.json()
                        break
                    except Exception:
                        if attempt == 3:
                            raise
                        await asyncio.sleep(2 * (attempt + 1))
            for p in data.get("_embedded", {}).get("panoramas", []):
                x, y = p["geometry"]["coordinates"][:2]
                if w <= x <= e and s <= y <= n:
                    out[p["pano_id"]] = {
                        "id": p["pano_id"],
                        "lat": y,
                        "lng": x,
                        "date": p["timestamp"][:10],
                        "image": p["_links"]["equirectangular_medium"]["href"],
                    }

        await asyncio.gather(*(one(a, b) for a, b in pts))
    return list(out.values())


def panos(area: str) -> dict:
    from shapely.geometry import Point

    bbox = AREAS[area]
    shapes, tree, (w, s, k) = _water(bbox)
    allp = asyncio.run(_panos(bbox))
    near = []
    for p in allp:
        q = Point((p["lng"] - w) * k, (p["lat"] - s) * M_LAT)
        if q.distance(shapes[tree.nearest(q)]) <= NEAR_WATER_M:
            near.append(p)
    # newest per spot
    near.sort(key=lambda p: p["date"], reverse=True)
    kept: list[dict] = []
    grid: dict[tuple[int, int], list[dict]] = {}
    for p in near:
        x, y = (p["lng"] - w) * k, (p["lat"] - s) * M_LAT
        cell = (int(x // SPOT_M), int(y // SPOT_M))
        close = [
            o
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            for o in grid.get((cell[0] + dx, cell[1] + dy), [])
            if math.hypot(o["_x"] - x, o["_y"] - y) < SPOT_M
        ]
        if close:
            continue
        p = {**p, "_x": x, "_y": y}
        grid.setdefault(cell, []).append(p)
        kept.append(p)
    for p in kept:
        p.pop("_x"), p.pop("_y")
    (area_dir(area) / "panos.json").write_text(json.dumps(kept))
    years: dict[str, int] = {}
    for p in kept:
        years[p["date"][:4]] = years.get(p["date"][:4], 0) + 1
    return {"in_box": len(allp), "near_water": len(near), "spots": len(kept), "years": years}


# ------------------------------------------------------------------ detection


def _bearing(heading: float, cx: float) -> float:
    """Compass bearing of an image column in a VIEW_PX-wide view at ``heading``."""
    f = (VIEW_PX / 2) / math.tan(math.radians(FOV / 2))
    return (heading + math.degrees(math.atan((cx - VIEW_PX / 2) / f))) % 360


async def _fetch(session, url: str, cache: Path) -> np.ndarray:
    if not cache.exists():
        for attempt in range(4):
            try:
                async with session.get(url) as r:
                    r.raise_for_status()
                    cache.write_bytes(await r.read())
                break
            except Exception:
                if attempt == 3:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
    return np.asarray(Image.open(cache).convert("RGB"))


def detect(area: str, device: str = "mps", limit: int | None = None) -> dict:
    import aiohttp
    from ultralytics import YOLO

    from bench_finder.core.pano_geometry import render_aimed_view

    d = area_dir(area)
    eq = d / "equirect"
    eq.mkdir(exist_ok=True)
    ps = json.loads((d / "panos.json").read_text())
    out = d / "yolo.jsonl"
    done = {json.loads(line)["pano"] for line in out.open()} if out.exists() else set()
    todo = [p for p in ps if p["id"] not in done][:limit]
    model = YOLO("models/yolo11x-seg.pt")
    stats = {"panos": len(todo), "views": 0, "hits": 0}
    t0 = time.time()

    async def run():
        async with aiohttp.ClientSession(headers=UA) as session:
            nxt = asyncio.ensure_future(
                _fetch(session, todo[0]["image"], eq / f"{todo[0]['id']}.jpg")
            ) if todo else None
            for i, p in enumerate(todo):
                arr = await nxt
                if i + 1 < len(todo):
                    q = todo[i + 1]
                    nxt = asyncio.ensure_future(_fetch(session, q["image"], eq / f"{q['id']}.jpg"))
                views = [
                    render_aimed_view(
                        arr, center_compass_deg=0.0, aim_bearing_deg=h, fov_deg=FOV, out_size=VIEW_PX
                    )
                    for h in HEADINGS
                ]
                res = model.predict(views, conf=YOLO_FLOOR, classes=[13], device=device, verbose=False)
                dets = []
                for h, v, r in zip(HEADINGS, views, res, strict=True):
                    stats["views"] += 1
                    boxes = [
                        (float(b.conf), [round(float(x), 1) for x in b.xyxy[0].tolist()])
                        for b in r.boxes
                    ]
                    if boxes:
                        stats["hits"] += 1
                        Image.fromarray(v).save(d / "views" / f"{p['id']}_{h}.jpg", quality=82)
                        dets.append({"heading": h, "boxes": boxes})
                with out.open("a") as f:
                    f.write(json.dumps({"pano": p["id"], "dets": dets}) + "\n")
                if (i + 1) % 100 == 0:
                    rate = (i + 1) / (time.time() - t0)
                    print(f"{i + 1}/{len(todo)} panos, {rate:.2f}/s, {stats}", flush=True)

    asyncio.run(run())
    return stats


def confirm(area: str, device: str = "mps", sample: float = SAMPLE_ALL) -> dict:
    """SAM 3 ("bench") on every view YOLO flagged, plus every view of a random
    ``sample`` of panoramas (rendered again from the cached equirect)."""
    from bench_finder.bakeoff.detectors import MODELS
    from bench_finder.core.pano_geometry import render_aimed_view

    d = area_dir(area)
    ps = {p["id"]: p for p in json.loads((d / "panos.json").read_text())}
    yolo = {r["pano"]: r for r in map(json.loads, (d / "yolo.jsonl").open())}
    out = d / "sam3.jsonl"
    done = {(r["pano"], r["heading"]) for r in map(json.loads, out.open())} if out.exists() else set()
    rng = random.Random(7)
    audit = {pid for pid in sorted(yolo) if rng.random() < sample}
    jobs = [(pid, x["heading"]) for pid, r in yolo.items() for x in r["dets"]]
    jobs += [(pid, h) for pid in sorted(audit) for h in HEADINGS]
    jobs = sorted(set(jobs) - done)
    sam = MODELS["sam3"]
    sam.load(Path("models"), device)
    t0 = time.time()
    n = 0
    for pid, h in jobs:
        path = d / "views" / f"{pid}_{h}.jpg"
        if not path.exists():
            arr = np.asarray(Image.open(d / "equirect" / f"{pid}.jpg").convert("RGB"))
            v = render_aimed_view(arr, center_compass_deg=0.0, aim_bearing_deg=h, fov_deg=FOV, out_size=VIEW_PX)
            Image.fromarray(v).save(path, quality=82)
        dets = [x for x in sam.detect(path) if x.conf >= 0.3]
        rec = {
            "pano": pid,
            "heading": h,
            "audit": pid in audit,
            "boxes": [(round(x.conf, 3), [round(x.x1, 1), round(x.y1, 1), round(x.x2, 1), round(x.y2, 1)]) for x in dets],
        }
        with out.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        n += 1
        if n % 200 == 0:
            print(f"{n}/{len(jobs)} views, {n / (time.time() - t0):.2f}/s", flush=True)
    del ps
    return {"views": len(jobs), "audit_panos": len(audit)}


# ------------------------------------------------------------------ clustering


def _cross(a, b):
    (ax, ay, ab), (bx, by, bb) = a[:3], b[:3]
    adx, ady = math.sin(math.radians(ab)), math.cos(math.radians(ab))
    bdx, bdy = math.sin(math.radians(bb)), math.cos(math.radians(bb))
    den = adx * bdy - ady * bdx
    if abs(den) < 1e-9:
        return None
    t = ((bx - ax) * bdy - (by - ay) * bdx) / den
    u = ((bx - ax) * ady - (by - ay) * adx) / den
    if not (0.5 < t <= MAX_RANGE_M and 0.5 < u <= MAX_RANGE_M):
        return None
    return ax + t * adx, ay + t * ady


def _dist(p, r) -> float:
    """Distance from p to ray r (inf behind the camera or out of range)."""
    x, y, b = r[:3]
    dx, dy = math.sin(math.radians(b)), math.cos(math.radians(b))
    vx, vy = p[0] - x, p[1] - y
    t = vx * dx + vy * dy
    if t <= 0.5 or t > MAX_RANGE_M:
        return math.inf
    return abs(vx * dy - vy * dx)


def _ang(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def cluster(area: str, db: str = "data/benches.db") -> dict:
    d = area_dir(area)
    w, s, _, n = AREAS[area]
    k = _m_lng((s + n) / 2)
    ps = {p["id"]: p for p in json.loads((d / "panos.json").read_text())}
    sam = list(map(json.loads, (d / "sam3.jsonl").open()))
    yolo = {r["pano"]: r for r in map(json.loads, (d / "yolo.jsonl").open())}
    rays = []  # (x, y, bearing, conf, pano, heading, box)
    for r in sam:
        p = ps[r["pano"]]
        for c, (x1, y1, x2, y2) in r["boxes"]:
            if c < SAM3_MIN:
                continue
            rays.append(
                ((p["lng"] - w) * k, (p["lat"] - s) * M_LAT, _bearing(r["heading"], (x1 + x2) / 2), c, r["pano"], r["heading"], [x1, y1, x2, y2])
            )
    # Overlapping views (60° fov every 45°) see the same bench twice: one ray per
    # pano and direction.
    rays.sort(key=lambda r: -r[3])
    uniq = []
    for r in rays:
        if not any(u[4] == r[4] and _ang(u[2], r[2]) < 3 for u in uniq):
            uniq.append(r)
    rays = uniq
    # grid for candidate pairs
    left = set(range(len(rays)))
    points = []
    while True:
        best = None
        idx = sorted(left)
        for i, j in itertools.combinations(idx, 2):
            a, b = rays[i], rays[j]
            if a[4] == b[4] or math.hypot(a[0] - b[0], a[1] - b[1]) > 2 * MAX_RANGE_M:
                continue
            if _ang(a[2], b[2]) < MIN_SPREAD_DEG:
                continue
            p = _cross(a, b)
            if p is None:
                continue
            inl = [m for m in idx if _dist(p, rays[m]) <= INLIER_M]
            panos_ = {rays[m][4] for m in inl}
            key = (len(panos_), sum(rays[m][3] for m in inl))
            if best is None or key > best[0]:
                best = (key, p, inl)
        if best is None or best[0][0] < 2:
            break
        _, p, inl = best
        # refine: least-squares point of the inlier lines
        A, bb = [], []
        for m in inl:
            x, y, br = rays[m][:3]
            nx, ny = math.cos(math.radians(br)), -math.sin(math.radians(br))
            A.append((nx, ny))
            bb.append(nx * x + ny * y)
        sol, *_ = np.linalg.lstsq(np.array(A), np.array(bb), rcond=None)
        px, py = float(sol[0]), float(sol[1])
        if math.hypot(px - p[0], py - p[1]) > 3:
            px, py = p
        by_pano: dict[str, tuple] = {}
        for m in inl:
            r = rays[m]
            if r[4] not in by_pano or r[3] > by_pano[r[4]][3]:
                by_pano[r[4]] = r
        sees = sorted(by_pano.values(), key=lambda r: math.hypot(r[0] - px, r[1] - py))
        points.append(
            {
                "lat": s + py / M_LAT,
                "lng": w + px / k,
                "panos": len(by_pano),
                "conf": round(max(r[3] for r in sees), 3),
                "views": [
                    {"pano": r[4], "heading": r[5], "box": r[6], "conf": r[3], "dist": round(math.hypot(r[0] - px, r[1] - py), 1)}
                    for r in sees
                ],
            }
        )
        left -= set(inl)
    # known benches
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    known = conn.execute(
        "SELECT id, lat, lng, source FROM bench_candidates WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?",
        (s - 0.001, n + 0.001, w - 0.002, AREAS[area][2] + 0.002),
    ).fetchall()
    conn.close()

    def metres(a, b, c, e):
        return math.hypot((a - c) * M_LAT, (b - e) * k)

    for pt in points:
        near = min(((metres(pt["lat"], pt["lng"], la, ln), i, src) for i, la, ln, src in known), default=None)
        pt["known"] = near[1] if near and near[0] <= KNOWN_M else None
        pt["known_m"] = round(near[0], 1) if near else None
        pt["known_source"] = near[2] if near and near[0] <= KNOWN_M else None
    # recall over known benches near the swept panoramas (within 20 m of one)
    pano_xy = [((p["lat"]), (p["lng"])) for p in ps.values()]
    reachable = [
        (i, la, ln) for i, la, ln, _ in known
        if any(metres(la, ln, a, b) <= 20 for a, b in pano_xy)
    ]
    found = {pt["known"] for pt in points if pt["known"]}
    checks = []
    for label, la, ln in CHECKS.get(area, []):
        near = min(points, key=lambda pt: metres(pt["lat"], pt["lng"], la, ln), default=None)
        checks.append(
            {
                "label": label,
                "lat": la,
                "lng": ln,
                "nearest_m": round(metres(near["lat"], near["lng"], la, ln), 1) if near else None,
            }
        )
    # the YOLO gate audit: SAM 3 hits in views YOLO did not flag
    flagged = {(pid, x["heading"]) for pid, r in yolo.items() for x in r["dets"]}
    audit = [r for r in sam if r.get("audit")]
    missed = [r for r in audit if (r["pano"], r["heading"]) not in flagged and any(c >= SAM3_MIN for c, _ in r["boxes"])]
    caught = [r for r in audit if (r["pano"], r["heading"]) in flagged and any(c >= SAM3_MIN for c, _ in r["boxes"])]
    summary = {
        "panoramas": len(ps),
        "views": len(ps) * len(HEADINGS),
        "yolo_views": len(flagged),
        "sam3_rays": len(rays),
        "points": len(points),
        "new": sum(1 for p in points if not p["known"]),
        "new_3plus": sum(1 for p in points if not p["known"] and p["panos"] >= 3),
        "known_points": sum(1 for p in points if p["known"]),
        "known_reachable": len(reachable),
        "known_found": len(found & {i for i, _, _ in reachable}),
        "gate_audit": {"views_with_sam3_bench": len(missed) + len(caught), "yolo_missed": len(missed)},
        "checks": checks,
    }
    (d / "points.json").write_text(json.dumps({"summary": summary, "points": points}))
    return summary


# ------------------------------------------------------------------ review page


def page(area: str) -> Path:
    d = area_dir(area)
    data = json.loads((d / "points.json").read_text())
    pts = sorted(data["points"], key=lambda p: (p["known"] is not None, -p["panos"], -p["conf"]))
    for i, p in enumerate(pts):
        p["n"] = i
    html = PAGE.replace("__DATA__", json.dumps({"summary": data["summary"], "points": pts, "area": area}))
    out = d / "index.html"
    out.write_text(html)
    return out


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sweep review</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--ink:#1c1b19;--ink2:#5d5a54;--paper:#f7f0e1;--card:#fffdf8;--rule:#d9d0bd;--new:#c2410c;--known:#2563eb;--ok:#15803d}
*{box-sizing:border-box}body{margin:0;font:14px/1.4 system-ui,sans-serif;background:var(--paper);color:var(--ink)}
header{position:sticky;top:0;z-index:1000;background:var(--card);border-bottom:1px solid var(--rule);padding:10px 16px;display:flex;gap:16px;flex-wrap:wrap;align-items:center}
header h1{font-size:16px;margin:0}header .stats{color:var(--ink2);font-size:13px}
header button,header select{font:inherit;padding:4px 10px;border:1px solid var(--ink);background:var(--card);cursor:pointer}
main{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:0;height:calc(100vh - 54px)}
#list{overflow:auto;padding:12px 16px}#map{height:100%}
@media(max-width:900px){main{grid-template-columns:1fr;height:auto}#map{height:320px;order:-1}}
.pt{background:var(--card);border:1px solid var(--rule);margin:0 0 14px;padding:10px 12px}
.pt.sel{outline:2px solid var(--new)}.pt h2{font-size:14px;margin:0 0 6px;display:flex;gap:10px;flex-wrap:wrap;align-items:baseline}
.tag{font-size:12px;padding:1px 6px;border:1px solid}.tag.new{color:var(--new)}.tag.known{color:var(--known)}
.views{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px}
.v{flex:0 0 auto;width:260px}.v .c{position:relative;width:260px;height:180px;overflow:hidden;background:#ccc;cursor:zoom-in}
.v .c canvas{display:block}.v small{color:var(--ink2);display:block}
.marks{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.marks button{font:inherit;font-size:13px;padding:3px 9px;border:1px solid var(--ink2);background:var(--card);cursor:pointer}
.marks button[aria-pressed=true]{background:var(--ink);color:#fff;border-color:var(--ink)}
dialog{max-width:95vw;padding:0;border:0}dialog canvas{max-width:95vw;max-height:90vh;display:block}
.check{font-size:13px}.check b{color:var(--new)}
</style></head><body>
<header><h1>Sweep review: <span id="area"></span></h1><span class="stats" id="stats"></span>
<label>Show <select id="filter"><option value="new">new only</option><option value="all">all</option><option value="known">known only</option><option value="unmarked">new, unmarked</option></select></label>
<button id="export">Export marks</button></header>
<main><div id="list"></div><div id="map"></div></main>
<dialog id="big"><canvas></canvas></dialog>
<script>
const D=__DATA__;const KEY='sweep-marks-'+D.area;
let marks={};try{marks=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(marks))}catch(e){}};
const S=D.summary;document.getElementById('area').textContent=D.area;
document.getElementById('stats').innerHTML=`${S.panoramas} panoramas · ${S.yolo_views} views YOLO flagged · ${S.sam3_rays} SAM 3 rays → <b>${S.points}</b> points: <b>${S.new}</b> new (${S.new_3plus} seen from 3+), ${S.known_points} known · known benches found ${S.known_found}/${S.known_reachable} · YOLO gate missed ${S.gate_audit.yolo_missed}/${S.gate_audit.views_with_sam3_bench} audited SAM 3 views`+
 S.checks.map(c=>`<div class="check">${c.label}: nearest point <b>${c.nearest_m??'none'} m</b></div>`).join('');
const map=L.map('map').setView([D.points[0]?.lat||52.364,D.points[0]?.lng||4.858],16);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{attribution:'© OpenStreetMap, © CARTO',maxZoom:20}).addTo(map);
S.checks.forEach(c=>L.circleMarker([c.lat,c.lng],{radius:9,color:'#15803d',weight:3,fill:false}).addTo(map).bindTooltip(c.label));
const MARKS=[['bench','Public bench'],['private','Private / terrace'],['known','Already on map'],['not','Not a bench'],['unsure','Unsure']];
const markers={};
function draw(cv,img,box,w,h,zoomed){const ctx=cv.getContext('2d');const bw=box[2]-box[0],bh=box[3]-box[1];
 let s=zoomed?1:Math.min(3,Math.max(1,Math.min(w/(bw*2.2),h/(bh*2.2))));const cx=(box[0]+box[2])/2,cy=(box[1]+box[3])/2;
 cv.width=w;cv.height=h;ctx.drawImage(img,cx-w/2/s,cy-h/2/s,w/s,h/s,0,0,w,h);
 ctx.strokeStyle='#ff2d2d';ctx.lineWidth=2;ctx.strokeRect((box[0]-cx)*s+w/2,(box[1]-cy)*s+h/2,bw*s,bh*s);}
function render(){const f=document.getElementById('filter').value;const list=document.getElementById('list');list.innerHTML='';
 for(const p of D.points){const m=marks[p.n];
  if(f==='new'&&p.known)continue;if(f==='known'&&!p.known)continue;if(f==='unmarked'&&(p.known||m))continue;
  const el=document.createElement('section');el.className='pt';el.id='p'+p.n;
  const gm=`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${p.lat},${p.lng}`;
  el.innerHTML=`<h2><span>#${p.n}</span><span class="tag ${p.known?'known':'new'}">${p.known?('known: '+p.known_source+' '+p.known+' at '+p.known_m+' m'):'new'+(p.known_m!=null?' (nearest known '+p.known_m+' m)':'')}</span><span>seen from ${p.panos} panoramas · SAM 3 ${p.conf}</span>
  <a href="https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lng}#map=20/${p.lat}/${p.lng}" target="_blank">OSM</a><a href="${gm}" target="_blank">Street View</a></h2>
  <div class="views"></div><div class="marks"></div>`;
  const vs=el.querySelector('.views');
  for(const v of p.views){const d=document.createElement('div');d.className='v';d.innerHTML=`<div class="c"><canvas></canvas></div><small>${v.dist} m away · looking ${v.heading}° · ${v.conf.toFixed(2)}</small>`;
   const img=new Image();img.onload=()=>draw(d.querySelector('canvas'),img,v.box,260,180,false);img.src=`views/${v.pano}_${v.heading}.jpg`;
   d.querySelector('.c').onclick=()=>{const dl=document.getElementById('big');const cv=dl.querySelector('canvas');draw(cv,img,v.box,1024,1024,true);dl.showModal()};vs.appendChild(d)}
  const mk=el.querySelector('.marks');for(const[k,l]of MARKS){const b=document.createElement('button');b.textContent=l;b.setAttribute('aria-pressed',m===k);
   b.onclick=()=>{marks[p.n]=marks[p.n]===k?undefined:k;if(!marks[p.n])delete marks[p.n];save();render();};mk.appendChild(b)}
  el.onmouseenter=()=>markers[p.n]?.openTooltip();list.appendChild(el)}
}
for(const p of D.points){markers[p.n]=L.circleMarker([p.lat,p.lng],{radius:p.known?4:6,color:p.known?'#2563eb':'#c2410c',weight:2,fillOpacity:.6}).addTo(map)
 .bindTooltip('#'+p.n).on('click',()=>{const f=document.getElementById('filter');if(!document.getElementById('p'+p.n)){f.value='all';render()}const el=document.getElementById('p'+p.n);document.querySelectorAll('.pt.sel').forEach(e=>e.classList.remove('sel'));el.classList.add('sel');el.scrollIntoView({block:'center',behavior:'smooth'})})}
document.getElementById('filter').onchange=render;document.getElementById('big').onclick=e=>e.currentTarget.close();
document.getElementById('export').onclick=()=>{const out={area:D.area,marks:Object.fromEntries(Object.entries(marks).map(([n,m])=>{const p=D.points[n];return[n,{mark:m,lat:p.lat,lng:p.lng,known:p.known}]}))};
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:'application/json'}));a.download=`sweep-${D.area}-marks.json`;a.click()};
render();
</script></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("cmd", choices=["panos", "detect", "confirm", "cluster", "page"])
    ap.add_argument("--area", default="kvv", choices=sorted(AREAS))
    ap.add_argument("--device", default="mps")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.cmd == "panos":
        print(panos(a.area))
    elif a.cmd == "detect":
        print(detect(a.area, a.device, a.limit))
    elif a.cmd == "confirm":
        print(confirm(a.area, a.device))
    elif a.cmd == "cluster":
        print(cluster(a.area))
    else:
        print(page(a.area))


if __name__ == "__main__":
    main()
