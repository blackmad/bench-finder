"""What changed between two publishes: new and lost benches, photos gained, lost
and changed, facings and looks-at that moved. A local review page.

Every ``publish`` snapshots its data into ``data/snapshots/<generated_at>/``
(the GeoJSON, every bench file and the manifest; ~30 MB). Images are not
copied: renditions are content-hashed and stay in ``dist-data/img``.

    uv run python -m bench_finder.whats_new            # the last two snapshots
    uv run python -m bench_finder.whats_new --from 2026-11-16T21-33-54+00-00
    open data/whats_new/index.html
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path


SNAPS = Path("data/snapshots")
OUT = Path("data/whats_new")
DIST = Path("dist-data")
SITE = "https://bench.blackmad.com/bench/"
FACING_MOVE = 30.0  # degrees


def snapshot(out: Path) -> Path:
    """Copy a finished publish's data (not its images) into ``data/snapshots``."""
    m = json.loads((out / "manifest.json").read_text())
    dest = SNAPS / m["generated_at"].replace(":", "-")
    if not dest.exists():
        dest.mkdir(parents=True)
        shutil.copytree(out / m.get("data_base", "data"), dest / "data")
        shutil.copy(out / "manifest.json", dest / "manifest.json")
    return dest


def load(snap: Path) -> dict[int, dict]:
    m = json.loads((snap / "manifest.json").read_text())
    bench_dir = snap / "data" / m.get("bench_dir", "bench")
    return {int(p.stem): json.loads(p.read_text()) for p in bench_dir.glob("*.json")}


def _turn(a: float, b: float) -> float:
    return abs((b - a + 180) % 360 - 180)


def diff(old: dict[int, dict], new: dict[int, dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {
        k: []
        for k in (
            "new_bench",
            "lost_bench",
            "photo_gained",
            "photo_lost",
            "photo_changed",
            "facing_moved",
            "looks_changed",
        )
    }
    for i in sorted(new.keys() - old.keys()):
        out["new_bench"].append({"new": new[i]})
    for i in sorted(old.keys() - new.keys()):
        out["lost_bench"].append({"old": old[i]})
    for i in sorted(old.keys() & new.keys()):
        a, b = old[i], new[i]
        pair = {"old": a, "new": b}
        ha, hb = a.get("hero_key"), b.get("hero_key")
        if hb and not ha:
            out["photo_gained"].append(pair)
        elif ha and not hb:
            out["photo_lost"].append(pair)
        elif ha != hb:
            out["photo_changed"].append(pair)
        fa, fb = a.get("facing"), b.get("facing")
        if fa is not None and fb is not None and _turn(fa, fb) >= FACING_MOVE:
            out["facing_moved"].append({**pair, "turn": _turn(fa, fb)})
        if a.get("faces_category") != b.get("faces_category"):
            out["looks_changed"].append(pair)
    return out


TITLES = {
    "new_bench": "New benches",
    "lost_bench": "Benches no longer published",
    "photo_gained": "Got a photo",
    "photo_lost": "Lost their photo",
    "photo_changed": "Photo changed",
    "facing_moved": f"Facing moved {FACING_MOVE:.0f}° or more",
    "looks_changed": "Looks at changed",
}


def _img(b: dict | None, rel: str) -> str:
    urls = (b or {}).get("hero_urls") or {}
    src = urls.get("400") or next(iter(urls.values()), None)
    return (
        f"<img loading=lazy src='{rel}/{html.escape(src)}'>"
        if src
        else "<div class=none>no photo</div>"
    )


def _facts(b: dict | None) -> str:
    if not b:
        return ""
    f = b.get("facing")
    bits = [
        html.escape(b.get("address") or ""),
        f"faces {f:.0f}° ({html.escape(str(b.get('facing_method') or '?'))})"
        if f is not None
        else "no facing",
        f"looks at {html.escape(str(b.get('faces_category')))}"
        if b.get("faces_category")
        else "",
    ]
    return " · ".join(x for x in bits if x)


FEEDBACK = ("good", "no bench", "bad photo", "wrong spot", "winter")
FB = (
    "<div class=fb>"
    + "".join(f"<button data-fb='{f}'>{f}</button>" for f in FEEDBACK)
    + "</div>"
)


def page(changes: dict[str, list[dict]], old_name: str, new_name: str, rel: str) -> str:
    e = html.escape
    points = []
    cards: list[str] = []
    for kind, items in changes.items():
        cards.append(
            f"<section data-kind={kind}><h2 id={kind}>{TITLES[kind]} · {len(items)}</h2><div class=grid>"
        )
        for it in items:
            b = it.get("new") or it["old"]
            points.append([b["lat"], b["lng"], kind, b["id"]])
            extra = f" · turned {it['turn']:.0f}°" if "turn" in it else ""
            pics = (
                f"<div class=pair>{_img(it.get('old'), rel)}{_img(it.get('new'), rel)}</div>"
                if kind in ("photo_changed", "facing_moved", "looks_changed")
                else _img(b, rel)
            )
            before = (
                f"<small>before: {_facts(it.get('old'))}</small>"
                if it.get("old") and it.get("new")
                else ""
            )
            cards.append(
                f"<article data-id={b['id']} data-text='{e((b.get('address') or '').lower())}'>{pics}"
                f"<p><b>#{b['id']}</b>{extra} · <a href='{SITE}{b['id']}'>live</a> · "
                f"<a href='https://www.openstreetmap.org/?mlat={b['lat']}&mlon={b['lng']}#map=19/{b['lat']}/{b['lng']}'>OSM</a> · "
                f"<a href='#' data-fly='{b['lat']},{b['lng']}'>map</a></p>"
                f"<small>{_facts(it.get('new') or it.get('old'))}</small>{before}{FB}</article>"
            )
        cards.append("</div></section>")
    nav = "".join(
        f"<label><input type=checkbox checked value={k}> {TITLES[k]} ({len(v)})</label>"
        for k, v in changes.items()
    )
    colors = {
        "new_bench": "#2e7d32",
        "lost_bench": "#c62828",
        "photo_gained": "#1565c0",
        "photo_lost": "#ef6c00",
        "photo_changed": "#6a1b9a",
        "facing_moved": "#00838f",
        "looks_changed": "#8d6e63",
    }
    return f"""<!doctype html><meta charset=utf-8><title>What's new</title>
<link rel=stylesheet href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>body{{font:14px system-ui;margin:0;background:#f7f0e1;color:#2b261e}}
header{{position:sticky;top:0;z-index:1000;background:#fbf8f1;padding:10px 16px;border-bottom:1px solid #ddd2bd}}
header label{{margin-right:12px;white-space:nowrap}}#q{{padding:4px 8px;width:220px}}
main{{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:16px;padding:0 16px}}
#map{{position:sticky;top:110px;height:calc(100vh - 130px);margin-top:16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}}
article{{background:#fffdf8;padding:8px;border-radius:4px}}article p{{margin:6px 0 2px}}
article img,.none{{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:#e9e2d2}}
.none{{display:grid;place-items:center;color:#9a8f7c}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:4px}}
small{{display:block;color:#675d4d}}
.fb{{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}}.fb button{{font:12px system-ui;padding:2px 6px;border:1px solid #cbbfa8;background:#fbf8f1;border-radius:3px;cursor:pointer}}
.fb button.on{{background:#2b261e;color:#fff;border-color:#2b261e}}article.marked{{outline:2px solid #2b261e}}
#fbout{{margin-left:8px}}a{{color:#2b5a8a}}
@media (max-width:900px){{main{{grid-template-columns:1fr}}#map{{position:static;height:300px}}}}</style>
<header><b>What's new</b> · {e(old_name)} → {e(new_name)} ·
<input id=q placeholder="filter: id or address">
<span id=fbout><button id=fbcopy>Copy feedback (0)</button> <button id=fbsave>Download</button>
<label><input type=checkbox id=unmarked value=_> only unmarked</label></span><br>{nav}</header>
<main><div>{"".join(cards)}</div><div id=map></div></main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const pts={json.dumps(points)}, colors={json.dumps(colors)};
const map=L.map('map').setView([52.37,4.89],12);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{maxZoom:20,subdomains:'abcd',attribution:'© OpenStreetMap contributors © CARTO'}}).addTo(map);
const marks=pts.map(([la,ln,k,id])=>{{const m=L.circleMarker([la,ln],{{radius:5,color:colors[k],weight:2}}).bindPopup('#'+id+' '+k).addTo(map);m.k=k;m.id=id;return m}});
let apply=function(){{const on=new Set([...document.querySelectorAll('header input[type=checkbox]:checked')].map(c=>c.value));
const q=document.getElementById('q').value.trim().toLowerCase();
document.querySelectorAll('section').forEach(s=>s.hidden=!on.has(s.dataset.kind));
document.querySelectorAll('article').forEach(a=>a.hidden=q&&!(a.dataset.id===q||a.dataset.text.includes(q)));
marks.forEach(m=>{{const show=on.has(m.k);show?m.addTo(map):m.remove()}})}}
const KEY='wn-fb-'+{json.dumps(new_name)};let fb={{}};try{{fb=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
function paint(){{document.querySelectorAll('article').forEach(a=>{{const v=fb[a.dataset.id]||[];a.classList.toggle('marked',v.length>0);
a.querySelectorAll('[data-fb]').forEach(b=>b.classList.toggle('on',v.includes(b.dataset.fb)))}});
document.getElementById('fbcopy').textContent='Copy feedback ('+Object.keys(fb).length+')'}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(fb))}}catch(e){{}}paint()}}
document.addEventListener('click',ev=>{{const b=ev.target.closest('[data-fb]');if(!b)return;const id=b.closest('article').dataset.id,f=b.dataset.fb;
const v=new Set(fb[id]||[]);v.has(f)?v.delete(f):v.add(f);if(v.size)fb[id]=[...v];else delete fb[id];save()}});
const dump=()=>JSON.stringify({{snapshot:{json.dumps(new_name)},feedback:fb}},null,1);
document.getElementById('fbcopy').onclick=()=>navigator.clipboard.writeText(dump());
document.getElementById('fbsave').onclick=()=>{{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([dump()],{{type:'application/json'}}));a.download='whats_new_feedback.json';a.click()}};
const _apply=apply;apply=function(){{_apply();if(document.getElementById('unmarked').checked)document.querySelectorAll('article').forEach(a=>{{if(fb[a.dataset.id])a.hidden=true}})}};
paint();
document.querySelectorAll('header input').forEach(i=>i.addEventListener('input',apply));
document.addEventListener('click',ev=>{{const f=ev.target.dataset&&ev.target.dataset.fly;if(f){{ev.preventDefault();map.setView(f.split(',').map(Number),18)}}}});
</script>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--from", dest="old", help="snapshot name (default: second newest)")
    ap.add_argument("--to", dest="new", help="snapshot name (default: newest)")
    a = ap.parse_args()
    snaps = sorted(p.name for p in SNAPS.iterdir() if p.is_dir())
    old, new = a.old or snaps[-2], a.new or snaps[-1]
    changes = diff(load(SNAPS / old), load(SNAPS / new))
    OUT.mkdir(parents=True, exist_ok=True)
    rel = Path("../../" + str(DIST)).as_posix()
    (OUT / "index.html").write_text(page(changes, old, new, rel))
    print({k: len(v) for k, v in changes.items()}, OUT / "index.html")


if __name__ == "__main__":
    main()
