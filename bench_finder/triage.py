"""Triage page: OSM benches that published without a photo, grouped by why.

    uv run python -m bench_finder.triage
    open data/triage/index.html

Reasons, first match wins:
  no_views    no panorama within 30 m of the pin (parks, courtyards, car-free paths)
  indoor      the only panoramas nearby were indoor ones, dropped
  failed      views were tried but none has a file on disk
  vlm_absent  views exist and the VLM said the bench isn't in any labelled one
  missed      views exist but no detector found the bench at publish thresholds
Each bench shows its views (distance, panorama month, best SAM 3 / YOLO score,
VLM labels) with links to OpenStreetMap, Google Maps and the live page.
"""

from __future__ import annotations

import argparse
import html
import sqlite3
from collections import defaultdict
from pathlib import Path

from bench_finder.publish.build import (
    AMSTERDAM_BBOX,
    _resolve,
    select_images,
    target_gate,
)


REASONS = {
    "no_views": "No panorama within 30 m of the pin",
    "indoor": "Only indoor panoramas nearby",
    "failed": "Views tried, none saved",
    "vlm_absent": "The VLM says the bench isn't in any view",
    "missed": "Views exist, detectors didn't find the bench",
}
SITE = "https://bench.blackmad.com/bench/"


def collect(db: str, images_root: Path) -> dict[str, list[dict]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    conn.row_factory = sqlite3.Row
    rows, _, chosen = select_images(
        conn,
        images_root,
        include_unclassified=True,
        bbox=AMSTERDAM_BBOX,
        gallery_size=99,
    )
    osm = {
        i for (i,) in conn.execute("SELECT id FROM bench_candidates WHERE source='OSM'")
    }
    tried: dict[int, int] = defaultdict(int)
    errors: dict[int, set[str]] = defaultdict(set)
    dist: dict[int, float | None] = {}
    for cid, iid, d, err in conn.execute(
        "SELECT bench_candidate_id, id, camera_distance_m, capture_error FROM images"
    ):
        tried[cid] += 1
        dist[iid] = d
        if err:
            errors[cid].add(err.split(" (")[0])
    labels: dict[int, list[str]] = defaultdict(list)
    for iid, kind, val in conn.execute(
        "SELECT image_id, label_type, value FROM image_annotations "
        "WHERE label_type IN ('bench_present', 'occluded')"
    ):
        labels[iid].append(f"{kind}={val}")
    out: dict[str, list[dict]] = {k: [] for k in REASONS}
    for r in rows:
        imgs, has_hero = chosen[r["id"]]
        if has_hero or r["id"] not in osm:
            continue
        usable = [i for i in imgs if _resolve(i, images_root)]
        present = [
            v for i in usable for v in labels[i["id"]] if v.startswith("bench_present")
        ]
        errs = errors[r["id"]]
        if not usable and (
            not tried[r["id"]] or errs == {"no usable panorama within 30 m"}
        ):
            reason = "no_views"
        elif (
            not usable
            and errs
            and all(
                e.startswith("indoor")
                for e in errs - {"no usable panorama within 30 m"}
            )
        ):
            reason = "indoor"
        elif not usable:
            reason = "failed"
        elif present and all(v.endswith(("=no", "=\"no\"")) for v in present):
            reason = "vlm_absent"
        else:
            reason = "missed"
        views = []
        for i in usable:
            t = i.get("targets") or {}
            score = (
                " ".join(f"{m} {c:.2f}" for m, (c, _) in t.items()) or "no target box"
            )
            views.append(
                {
                    "name": _resolve(i, images_root).name,
                    "dist": dist.get(i["id"]),
                    "date": (i.get("pano_date") or "")[:7],
                    "score": score,
                    "tier": target_gate(i)[0],
                    "labels": ", ".join(labels[i["id"]]),
                }
            )
        out[reason].append(
            {
                "id": r["id"],
                "lat": r["lat"],
                "lng": r["lng"],
                "tried": tried[r["id"]],
                "views": views,
            }
        )
    return out


def page(groups: dict[str, list[dict]], images_rel: str) -> str:
    e = html.escape
    total = sum(map(len, groups.values()))
    parts = [
        "<!doctype html><meta charset=utf-8><title>Benches without a photo</title><style>"
        "body{font:14px system-ui;margin:16px;background:#f7f0e1;color:#2b261e}"
        "nav a{margin-right:14px}section{margin:24px 0}"
        ".b{background:#fffdf8;padding:10px 12px;margin:0 0 12px;border-radius:4px}"
        ".v{display:flex;gap:8px;overflow-x:auto}.v figure{margin:0;width:220px;flex:none}"
        ".v img{width:220px;aspect-ratio:1;object-fit:cover;background:#ddd}"
        "figcaption{font-size:12px;color:#675d4d}a{color:#2b5a8a}</style>",
        f"<h1>{total} OSM benches without a photo</h1><nav>",
    ]
    parts += [
        f"<a href='#{k}'>{e(REASONS[k])} ({len(v)})</a>" for k, v in groups.items()
    ]
    parts.append("</nav>")
    for k, benches in groups.items():
        parts.append(f"<section id='{k}'><h2>{e(REASONS[k])} · {len(benches)}</h2>")
        for b in benches:
            lat, lng = b["lat"], b["lng"]
            parts.append(
                f"<div class=b><b>#{b['id']}</b> · {b['tried']} view rows · "
                f"<a href='https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=19/{lat}/{lng}'>OSM</a> · "
                f"<a href='https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}'>Street View</a> · "
                f"<a href='https://www.google.com/maps?q={lat},{lng}&t=k'>satellite</a> · "
                f"<a href='{SITE}{b['id']}'>live page</a><div class=v>"
            )
            for v in b["views"]:
                d = f"{v['dist']:.0f} m" if v["dist"] is not None else "? m"
                parts.append(
                    f"<figure><img loading=lazy src='{images_rel}/{e(v['name'])}'>"
                    f"<figcaption>{d} · {e(v['date'])} · {e(v['score'])}"
                    f"{' · ' + e(v['labels']) if v['labels'] else ''}</figcaption></figure>"
                )
            parts.append("</div></div>")
        parts.append("</section>")
    return "".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument("--images-root", type=Path, default=Path("images"))
    ap.add_argument("--out", type=Path, default=Path("data/triage"))
    a = ap.parse_args()
    groups = collect(a.db, a.images_root)
    a.out.mkdir(parents=True, exist_ok=True)
    rel = Path("../" * len(a.out.parts)) / a.images_root
    (a.out / "index.html").write_text(page(groups, rel.as_posix()))
    print({k: len(v) for k, v in groups.items()}, a.out / "index.html")


if __name__ == "__main__":
    main()
