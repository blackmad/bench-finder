"""Visitors' missing-bench reports: pull, locate, add as candidates, resolve.

A report has a map pin and, usually, a City of Amsterdam panorama with the
compass heading at which the reporter put the bench under the line. The pin is
rough (often dropped where the reporter stood), so ``locate`` triangulates:

1. SAM 3 ("bench") on the reported view; the box nearest the line refines the
   heading (ray 0 from the panorama).
2. Each other panorama within ``NEIGHBOUR_M`` renders a view aimed along ray 0
   (2-30 m out); every SAM 3 bench in it is a ray, and where it crosses ray 0 is
   a guess at the distance.
3. The distance most guesses agree on (within ``AGREE_M``) is the bench.

Without a panorama, or when fewer than two panoramas agree, the pin is used and
the report is marked for a look.

    uv run python -m bench_finder.reports pull                 # pending -> data/reports/missing.json
    uv run --group detect-extra python -m bench_finder.reports locate [--id N]
    uv run python -m bench_finder.reports add --id N           # bench_candidates (source REPORT)
    # photos: the commands `add` prints (fetch-images, vantage, wide_views, YOLO, SAM 3)
    uv run python -m bench_finder.reports finish --id N        # address, looks-at, facing, Street View, hero
    # look at the hero and facing it prints; then publish --upload
    uv run python -m bench_finder.reports resolve --id N --note "..."   # D1 status = resolved
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


DIR = Path("data/reports")
API = "https://api.data.amsterdam.nl/panorama/panoramas/"
UA = {"User-Agent": "bench-finder (reports)"}
NEIGHBOUR_M = 35.0
NEAR_T, FAR_T = 2.0, 30.0
AGREE_M = 1.5
SAM3_MIN = 0.4
VIEW_PX = 1024
M_LAT = 110_574.0


def _k(lat: float) -> float:
    return 111_320.0 * math.cos(math.radians(lat))


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=60
    ).read()


def _d1(sql: str) -> list[dict]:
    out = subprocess.run(
        [
            "npx",
            "wrangler",
            "d1",
            "execute",
            "bench-finder",
            "--remote",
            "--json",
            "--command",
            sql,
        ],
        cwd="worker",
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)[0]["results"]


def pull() -> dict:
    rows = _d1(
        "SELECT id, lat, lng, accuracy_meters, note, photo_key, user_id IS NOT NULL AS signed_in, "
        "created_at, pano_source, pano_id, pano_heading, pano_url FROM missing_bench_reports "
        "WHERE status = 'pending' ORDER BY id"
    )
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "missing.json").write_text(json.dumps(rows, indent=1))
    return {"pending": len(rows), "with_pano": sum(1 for r in rows if r["pano_id"])}


def _pano(pid: str) -> tuple[dict, np.ndarray]:
    meta = json.loads(_get(f"{API}{pid}/"))
    cache = DIR / "equirect" / f"{pid}.jpg"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        cache.write_bytes(_get(meta["_links"]["equirectangular_medium"]["href"]))
    return meta, np.asarray(Image.open(cache).convert("RGB"))


def _bearing_of(heading: float, fov: float, cx: float) -> float:
    f = (VIEW_PX / 2) / math.tan(math.radians(fov / 2))
    return (heading + math.degrees(math.atan((cx - VIEW_PX / 2) / f))) % 360


def _col_of(heading: float, fov: float, bearing: float) -> float:
    f = (VIEW_PX / 2) / math.tan(math.radians(fov / 2))
    d = (bearing - heading + 180) % 360 - 180
    return VIEW_PX / 2 + f * math.tan(math.radians(d))


def _bearing(dx: float, dy: float) -> float:
    return math.degrees(math.atan2(dx, dy)) % 360


def _cross_t(p0, b0, p1, b1) -> tuple[float, float] | None:
    """Distances along ray 0 and ray 1 to where they cross."""
    d0 = (math.sin(math.radians(b0)), math.cos(math.radians(b0)))
    d1 = (math.sin(math.radians(b1)), math.cos(math.radians(b1)))
    den = d0[0] * d1[1] - d0[1] * d1[0]
    if abs(den) < 1e-6:
        return None
    wx, wy = p1[0] - p0[0], p1[1] - p0[1]
    t = (wx * d1[1] - wy * d1[0]) / den
    u = (wx * d0[1] - wy * d0[0]) / den
    return t, u


def _save(view: np.ndarray, boxes, line_col: float | None, path: Path) -> None:
    im = Image.fromarray(view)
    d = ImageDraw.Draw(im)
    if line_col is not None:
        d.line([(line_col, 0), (line_col, VIEW_PX)], fill=(255, 60, 40), width=2)
    for c, (x1, y1, x2, y2), ok in boxes:
        d.rectangle(
            [x1, y1, x2, y2], outline=(40, 220, 60) if ok else (255, 200, 0), width=3
        )
        d.text((x1 + 3, y1 + 3), f"{c:.2f}", fill=(255, 255, 255))
    im.save(path, quality=85)


def locate(rid: int | None = None, device: str = "mps") -> list[dict]:
    from bench_finder.bakeoff.detectors import MODELS
    from bench_finder.core.pano_geometry import render_aimed_view

    reports = json.loads((DIR / "missing.json").read_text())
    if rid is not None:
        reports = [r for r in reports if r["id"] == rid]
    sam = MODELS["sam3"]
    sam.load(Path("models"), device)
    out = []
    for r in reports:
        res = {
            "id": r["id"],
            "pin": [r["lat"], r["lng"]],
            "method": "pin",
            "lat": r["lat"],
            "lng": r["lng"],
        }
        if r["pano_source"] != "amsterdam" or not r["pano_id"]:
            res["why"] = "no city panorama: pin used, needs a look"
            out.append(res)
            continue
        vdir = DIR / str(r["id"])
        vdir.mkdir(parents=True, exist_ok=True)
        meta, arr = _pano(r["pano_id"])
        lng0, lat0 = meta["geometry"]["coordinates"][:2]
        k = _k(lat0)

        def xy(lat, lng, lat0=lat0, lng0=lng0, k=k):
            return ((lng - lng0) * k, (lat - lat0) * M_LAT)

        # 1. the reported view: the SAM 3 box nearest the line refines the heading
        h0, fov0 = float(r["pano_heading"]), 50.0
        v = render_aimed_view(
            arr,
            center_compass_deg=0.0,
            aim_bearing_deg=h0,
            fov_deg=fov0,
            out_size=VIEW_PX,
        )
        Image.fromarray(v).save(vdir / "reported.jpg")
        dets = [d for d in sam.detect(vdir / "reported.jpg") if d.conf >= SAM3_MIN]
        near = min(
            dets, key=lambda d: abs((d.x1 + d.x2) / 2 - VIEW_PX / 2), default=None
        )
        if near and abs((near.x1 + near.x2) / 2 - VIEW_PX / 2) < VIEW_PX * 0.2:
            b0 = _bearing_of(h0, fov0, (near.x1 + near.x2) / 2)
            res["reported_view"] = {
                "sam3": round(near.conf, 3),
                "heading_fix": round((b0 - h0 + 180) % 360 - 180, 1),
            }
        else:
            b0 = h0
            res["reported_view"] = {"sam3": None}
        _save(
            v,
            [(d.conf, (d.x1, d.y1, d.x2, d.y2), d is near) for d in dets],
            _col_of(h0, fov0, b0),
            vdir / "reported.jpg",
        )

        # 2. neighbours aimed along ray 0
        q = f"{API}?near={lng0},{lat0}&radius={int(NEIGHBOUR_M)}&newest_in_range=true&page_size=200"
        ps = [
            p
            for p in json.loads(_get(q)).get("_embedded", {}).get("panoramas", [])
            if p["pano_id"] != r["pano_id"]
        ]
        guesses, views = [], []
        d0 = (math.sin(math.radians(b0)), math.cos(math.radians(b0)))
        for p in ps:
            plng, plat = p["geometry"]["coordinates"][:2]
            px, py = xy(plat, plng)
            if math.hypot(px, py) < 1.5:
                continue
            a = _bearing(NEAR_T * d0[0] - px, NEAR_T * d0[1] - py)
            b = _bearing(FAR_T * d0[0] - px, FAR_T * d0[1] - py)
            span = abs((b - a + 180) % 360 - 180)
            mid = (a + ((b - a + 180) % 360 - 180) / 2) % 360
            fov = min(100.0, max(40.0, span + 16))
            try:
                _, parr = _pano(p["pano_id"])
            except Exception:
                continue
            pv = render_aimed_view(
                parr,
                center_compass_deg=0.0,
                aim_bearing_deg=mid,
                fov_deg=fov,
                out_size=VIEW_PX,
            )
            path = vdir / f"n_{p['pano_id']}.jpg"
            Image.fromarray(pv).save(path)
            boxes = []
            for d in (d for d in sam.detect(path) if d.conf >= SAM3_MIN):
                bb = _bearing_of(mid, fov, (d.x1 + d.x2) / 2)
                tu = _cross_t((0, 0), b0, (px, py), bb)
                ok = tu is not None and NEAR_T <= tu[0] <= FAR_T and tu[1] > 0.5
                boxes.append((d.conf, (d.x1, d.y1, d.x2, d.y2), ok))
                if ok:
                    guesses.append(
                        {
                            "t": tu[0],
                            "pano": p["pano_id"],
                            "conf": d.conf,
                            "date": p["timestamp"][:10],
                        }
                    )
            _save(pv, boxes, None, path)
            views.append(
                {
                    "pano": p["pano_id"],
                    "dist": round(math.hypot(px, py), 1),
                    "boxes": len(boxes),
                }
            )
        # 3. the distance most panoramas agree on
        best = None
        for g in guesses:
            agree = [h for h in guesses if abs(h["t"] - g["t"]) <= AGREE_M]
            panos = {h["pano"] for h in agree}
            key = (len(panos), sum(h["conf"] for h in agree))
            if best is None or key > best[0]:
                best = (key, agree)
        res["neighbours"] = len(views)
        res["guesses"] = [
            {"t": round(g["t"], 1), "pano": g["pano"], "conf": round(g["conf"], 2)}
            for g in guesses
        ]
        if best and best[0][0] >= 2:
            agree = best[1]
            t = float(
                np.average([h["t"] for h in agree], weights=[h["conf"] for h in agree])
            )
            res |= {
                "method": "triangulated",
                "distance_m": round(t, 1),
                "agreeing_panos": best[0][0],
                "lat": lat0 + t * d0[1] / M_LAT,
                "lng": lng0 + t * d0[0] / k,
            }
            pin_m = math.hypot(*xy(r["lat"], r["lng"])) if r["lat"] else None
            res["pin_off_m"] = round(
                math.hypot(
                    t * d0[0] - xy(r["lat"], r["lng"])[0],
                    t * d0[1] - xy(r["lat"], r["lng"])[1],
                ),
                1,
            )
            del pin_m
        else:
            res["why"] = (
                "fewer than two panoramas agree on where along the line it is: pin used"
            )
        out.append(res)
    prev = (
        json.loads((DIR / "located.json").read_text())
        if (DIR / "located.json").exists()
        else {}
    )
    prev |= {str(x["id"]): x for x in out}
    (DIR / "located.json").write_text(json.dumps(prev, indent=1))
    return out


def add(rid: int, db: str = "data/benches.db") -> dict:
    """The located report as a bench candidate (source REPORT, external id = report id)."""
    loc = json.loads((DIR / "located.json").read_text())[str(rid)]
    rep = next(
        r for r in json.loads((DIR / "missing.json").read_text()) if r["id"] == rid
    )
    conn = sqlite3.connect(db, timeout=120)
    have = conn.execute(
        "SELECT id FROM bench_candidates WHERE source = 'REPORT' AND external_id = ?",
        (str(rid),),
    ).fetchone()
    if have:
        return {"candidate": have[0], "existing": True}
    now = datetime.now(UTC).isoformat()
    sid = conn.execute(
        "INSERT INTO searches (query, start_lat, start_lng, search_radius, created_at, status) "
        "VALUES (?, ?, ?, 0, ?, 'completed')",
        (f"missing-report-{rid}", loc["lat"], loc["lng"], now),
    ).lastrowid
    # The reporter's note stays out: tags are public on the bench page.
    tags = {"amenity": "bench", "source": "visitor report", "report_id": rid}
    del rep
    cid = conn.execute(
        "INSERT INTO bench_candidates (search_id, provider_id, lat, lng, tags, source, external_id, "
        "confidence, created_at, status) VALUES (?, ?, ?, ?, ?, 'REPORT', ?, ?, ?, 'PENDING')",
        (
            sid,
            f"report/{rid}",
            loc["lat"],
            loc["lng"],
            json.dumps(tags),
            str(rid),
            1.0 if loc["method"] == "triangulated" else 0.5,
            now,
        ),
    ).lastrowid
    conn.commit()
    conn.close()
    return {
        "candidate": cid,
        "lat": loc["lat"],
        "lng": loc["lng"],
        "method": loc["method"],
        "next": PHOTO_STEPS.format(sid=sid)
        + f"uv run python -m bench_finder.reports finish --id {rid}",
    }


PHOTO_STEPS = (
    "uv run bench-finder fetch-images --search-id {sid}\n"
    "uv run python -m bench_finder.vantage run\n"
    "uv run python -m bench_finder.wide_views\n"
    "uv run python -m bench_finder.detect_aimed --model yolo11x-seg\n"
    "uv run --group detect-extra python -m bench_finder.detect_aimed --model sam3\n"
)


def _run(*args: str) -> str:
    out = subprocess.run(
        ["uv", "run", "python", "-m", *args], capture_output=True, text=True, check=True
    )
    return out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""


def _address(conn: sqlite3.Connection, cid: int, lat: float, lng: float) -> str | None:
    have = conn.execute(
        "SELECT formatted_address FROM reverse_geocodes WHERE bench_candidate_id = ?",
        (cid,),
    ).fetchone()
    if have:
        return have[0]
    from bench_finder.core.geocoder import Geocoder
    from bench_finder.services.database import BenchDatabase

    a = Geocoder().reverse_geocode_structured(lat, lng)
    if not a:
        return None
    BenchDatabase(conn_path(conn)).add_or_update_reverse_geocode(
        bench_candidate_id=cid,
        formatted_address=a["formatted_address"],
        street_number=a.get("street_number"),
        street_name=a.get("street_name"),
        city=a.get("city"),
        state=a.get("state"),
        postal_code=a.get("postal_code"),
        country=a.get("country"),
        raw_response=a.get("raw_response"),
    )
    return a["formatted_address"]


def conn_path(conn: sqlite3.Connection) -> str:
    return conn.execute("PRAGMA database_list").fetchone()[2]


def finish(rid: int, db: str = "data/benches.db") -> dict:
    """After the photo steps: what a published bench needs, for this one bench.

    Address (Google, cached), looks-at and seat from the view labeller (about a
    cent), the water-facing rule, Street View opened along the reporter's line,
    and a re-centred hero. The facing it ends with is printed to be checked
    against the hero: the labeller's own facings are often wrong (they are not
    published) and only the water rule or a person makes one shown.
    """
    conn = sqlite3.connect(db, timeout=120)
    row = conn.execute(
        "SELECT id, lat, lng FROM bench_candidates WHERE source = 'REPORT' AND external_id = ?",
        (str(rid),),
    ).fetchone()
    if not row:
        raise SystemExit(f"report {rid} has no candidate yet: run add first")
    cid, lat, lng = row
    photos = conn.execute(
        "SELECT count(DISTINCT i.id) FROM images i JOIN detections d ON d.image_id = i.id "
        "JOIN detection_items di ON di.detection_id = d.id AND di.is_target = 1 "
        "WHERE i.bench_candidate_id = ?",
        (cid,),
    ).fetchone()[0]
    if not photos:
        raise SystemExit(
            f"bench {cid} has no photo with the bench detected: run the photo steps"
        )
    out: dict = {"candidate": cid, "photos_with_bench": photos}
    out["address"] = _address(conn, cid, lat, lng)
    conn.close()
    out["label"] = _run(
        "bench_finder.label_views", "run", "--bench", str(cid), "--max-usd", "0.05"
    )
    out["fuse"] = _run("bench_finder.label_views", "fuse", "--new-only")
    out["water"] = _run("bench_finder.water_facing", "apply")
    conn = sqlite3.connect(db, timeout=120)
    if not conn.execute(
        "SELECT 1 FROM bench_attributes WHERE bench_candidate_id = ?", (cid,)
    ).fetchone():
        raise SystemExit(
            f"bench {cid}: labelling wrote no attributes (see label output)"
        )
    # Street View opens where the reporter pointed (their panorama and line).
    rep = next(
        (r for r in json.loads((DIR / "missing.json").read_text()) if r["id"] == rid),
        None,
    )
    loc = json.loads((DIR / "located.json").read_text()).get(str(rid), {})
    if rep and rep.get("pano_source") == "amsterdam" and rep.get("pano_id"):
        fix = (loc.get("reported_view") or {}).get("heading_fix", 0.0)
        heading = round((rep["pano_heading"] + fix) % 360, 1)
        conn.execute(
            "UPDATE bench_attributes SET embed_pano_id = ?, embed_heading_deg = ? "
            "WHERE bench_candidate_id = ?",
            (rep["pano_id"], heading, cid),
        )
        out["street_view"] = {"pano": rep["pano_id"], "heading": heading}
    conn.commit()
    conn.close()
    out["recentre"] = _run("bench_finder.recentre", "run", "--bench", str(cid))
    conn = sqlite3.connect(db)
    f = conn.execute(
        "SELECT facing_deg, facing_method, faces_category, faces_text, backrest "
        "FROM bench_attributes WHERE bench_candidate_id = ?",
        (cid,),
    ).fetchone()
    conn.close()
    out["facing"] = dict(
        zip(["deg", "method", "looks_at", "text", "backrest"], f, strict=True)
    )
    out["check"] = (
        "shown facing"
        if f[1] in ("water_edge", "water_back", "osm_tag", "human")
        else "facing not shown (labeller only): set it by hand if the hero makes it clear"
    )
    return out


def resolve(rid: int, note: str) -> dict:
    now = datetime.now(UTC).isoformat()
    safe = note.replace("'", "''")
    _d1(
        f"UPDATE missing_bench_reports SET status = 'resolved', admin_notes = '{safe}', "
        f"resolved_at = '{now}', resolved_by = 'pipeline' WHERE id = {int(rid)}"
    )
    return {"resolved": rid}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("cmd", choices=["pull", "locate", "add", "finish", "resolve"])
    ap.add_argument("--id", type=int)
    ap.add_argument("--note", default="")
    ap.add_argument("--device", default="mps")
    a = ap.parse_args()
    if a.cmd == "pull":
        print(pull())
    elif a.cmd == "locate":
        print(json.dumps(locate(a.id, a.device), indent=1))
    elif a.cmd == "add":
        r = add(a.id)
        print(json.dumps({k: v for k, v in r.items() if k != "next"}))
        print("next:\n" + r.get("next", ""))
    elif a.cmd == "finish":
        print(json.dumps(finish(a.id), indent=1))
    else:
        print(resolve(a.id, a.note))


if __name__ == "__main__":
    main()
