"""Keyboard review of benches: one at a time, marks saved as you go.

    uv run python -m bench_finder.review [--queue new|changed|photoless|all]
    open http://localhost:8897

Keys (each sets its mark and moves on; u clears): g good · p wrong photo (veto it, keep the bench) · x no bench here (hide)
· w wrong spot · s bus/tram/train stop (hide) · ←/→ or j/k move · u undo.
Marks go to ``data/feedback/review.json``: ``feedback`` {bench: [marks]} and
``wrong_photo`` [image ids], which ``publish`` reads (bench_finder.publish.exclude).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bench_finder import duel
from bench_finder.publish.build import AMSTERDAM_BBOX, select_images
from bench_finder.publish.images import render_source
from bench_finder.whats_new import SNAPS, diff, load


OUT = Path("data/feedback/review.json")
ROOTS = {"img/": Path("dist-data"), "images/": Path(".")}
QUEUES = {
    "new": ("new_bench",),
    "changed": ("photo_changed", "photo_gained"),
    "photoless": (),
    # No hero although SAM 3 is sure of a view: Flash-Lite vetoed it. Click the
    # view that shows the bench to make it the hero (overrides the veto).
    # Opus's "business" verdicts (terrace.py; no longer hide anything): x hides
    # one that really belongs to a cafe or shop, g keeps it.
    "business": (),
    "vetoed": (),
    # Hidden benches whose best view is just under SAM 3's cutoff (0.5-0.6):
    # h on the view that shows the bench, g if none of them does. Measures
    # whether the cutoff can drop to 0.5.
    "nearmiss": (),
    # Heroes just over SAM 3's cutoff (0.6-0.7): g if it is a bench, p if not.
    "borderline": (),
    "all": (),
}


def _state() -> dict:
    s = json.loads(OUT.read_text()) if OUT.exists() else {}
    s.setdefault("feedback", {})
    s.setdefault("wrong_photo", [])
    s.setdefault("hero_pick", {})
    return s


def build_queue(queue: str, base: str | None) -> list[dict]:
    snaps = sorted(p.name for p in SNAPS.iterdir() if p.is_dir())
    new = load(SNAPS / snaps[-1])
    if queue in ("new", "changed"):
        ch = diff(load(SNAPS / (base or snaps[0])), new)
        ids = [it["new"]["id"] for k in QUEUES[queue] for it in ch[k] if it.get("new")]
    elif queue == "photoless":
        ids = [i for i, b in new.items() if not b.get("hero_key")]
    elif queue == "business":
        from bench_finder.terrace import hidden

        ids = sorted(i for i, use in hidden().items() if use == "business")
    else:
        ids = sorted(new)
    conn = sqlite3.connect("file:data/benches.db?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    _, _, chosen = select_images(conn, Path("images"), True, bbox=AMSTERDAM_BBOX)
    if queue in ("vetoed", "borderline", "nearmiss"):
        ids = [i for i in sorted(new) if _in_band(queue, *chosen.get(i, ([], False)))]
    score = dict(
        conn.execute(
            "SELECT d.image_id, max(di.confidence) FROM detections d JOIN detection_items di "
            "ON di.detection_id = d.id AND di.is_target = 1 WHERE d.model_id = 'sam3' "
            "GROUP BY d.image_id"
        )
    )
    views: dict[int, list] = {}
    want = set(ids)
    for iid, bid, fp, src, when in conn.execute(
        "SELECT id, bench_candidate_id, filepath, image_source, pano_date FROM images "
        "WHERE kind = 'aimed' AND capture_success = 1 AND filepath IS NOT NULL ORDER BY id"
    ):
        if bid in want:
            views.setdefault(bid, []).append(
                {
                    "id": iid,
                    # The levelled re-render the site uses, when there is one.
                    "src": str(render_source(Path(fp), faded=False)),
                    "score": score.get(iid),
                    "source": src,
                    "when": when,
                }
            )
    conn.close()
    items = []
    for i in ids:
        b = new.get(i) or _unpublished(i)
        imgs, has_hero = chosen.get(i, ([], False))
        hero = imgs[0]["id"] if has_hero and imgs else None
        v = sorted(views.get(i, []), key=lambda x: -(x["score"] or 0))[:12]
        if not v and not hero:  # nothing to judge: no imagery at all
            continue
        items.append(
            {
                "id": i,
                "lat": b["lat"],
                "lng": b["lng"],
                "address": b.get("address") or "",
                "facts": " · ".join(
                    str(x)
                    for x in (
                        b.get("faces_category") and f"looks at {b['faces_category']}",
                        b.get("facing") is not None and f"faces {b['facing']:.0f}°",
                        b.get("bench_type"),
                        (b.get("tags") or {}).get("source") or "OSM",
                    )
                    if x
                ),
                "hero": (b.get("hero_urls") or {}).get("800"),
                "hero_id": hero,
                "views": v,
            }
        )
    return items


def _unpublished(bid: int) -> dict:
    """A hidden bench (not in the snapshot): position and address from the db."""
    conn = sqlite3.connect("file:data/benches.db?mode=ro", uri=True)
    row = conn.execute(
        "SELECT c.lat, c.lng, g.formatted_address FROM bench_candidates c "
        "LEFT JOIN reverse_geocodes g ON g.bench_candidate_id = c.id WHERE c.id = ?",
        (bid,),
    ).fetchone()
    conn.close()
    lat, lng, addr = row or (0.0, 0.0, "")
    return {"lat": lat, "lng": lng, "address": (addr or "").split(",")[0]}


def _sam3(img: dict) -> float:
    return ((img.get("targets") or {}).get("sam3") or (0.0,))[0]


def _in_band(queue: str, imgs: list[dict], has_hero: bool) -> bool:
    from bench_finder.publish.build import SAM3_MIN, target_gate

    if queue == "vetoed":
        return not has_hero and any(
            _sam3(i) >= SAM3_MIN and i.get("vetoed") for i in imgs
        )
    hero = imgs[0] if has_hero and imgs else None
    return (
        hero is not None and target_gate(hero)[0] == 0 and SAM3_MIN <= _sam3(hero) < 0.7
    )


PAGE = """<!doctype html><meta charset=utf-8><title>Bench review</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{--paper:#f5efe3;--ink:#2a2620;--mute:#7a6f5c;--card:#fffdf8;--hi:#b5442e}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.4 system-ui,sans-serif}
header{display:flex;gap:16px;align-items:baseline;padding:10px 16px;border-bottom:1px solid #ddd3c0}
header b{font-size:18px}main{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:16px;padding:16px;max-width:1300px;margin:auto}
.hero{width:100%;max-height:62vh;object-fit:contain;background:#e9e2d2;display:block}
.none{height:40vh;display:grid;place-items:center;background:#e9e2d2;color:var(--mute)}
.views{display:grid;grid-template-columns:repeat(6,1fr);gap:4px;margin-top:6px}
.views a{position:relative;display:block;outline:3px solid transparent}.views a.h{outline-color:var(--hi)}.views a.sel{outline-color:#2a5db0}.cap{margin:4px 0 0;font-size:12.5px;color:var(--mute)}
.views img{width:100%;aspect-ratio:1;object-fit:cover;display:block}
.views i{position:absolute;left:2px;bottom:2px;font:11px system-ui;background:#fffd;padding:0 3px;font-style:normal}
aside{display:grid;gap:10px;align-content:start}h1{font-size:20px;margin:0}.mute{color:var(--mute)}
iframe{width:100%;height:220px;border:0}.keys{display:grid;grid-template-columns:auto 1fr;gap:4px 10px}
kbd{font:12px ui-monospace,monospace;border:1px solid #c9bea8;border-bottom-width:2px;padding:1px 6px;background:var(--card);text-align:center}
.on{background:var(--ink);color:var(--card)}.marks{min-height:24px}.marks span{background:var(--ink);color:var(--card);padding:2px 8px;margin-right:4px}
@media(max-width:800px){main{grid-template-columns:1fr}.views{grid-template-columns:repeat(4,1fr)}}
</style>
<header><b>Bench review</b><select id=qsel style="margin-left:14px;font:inherit"><option value=new>New benches<option value=changed>Changed photos<option value=photoless>No photo<option value=business>Business (Opus thought so)<option value=nearmiss>Near misses (SAM 3 0.5-0.6)<option value=vetoed>Vetoed by Flash-Lite<option value=borderline>Borderline heroes (SAM 3 0.6-0.7)<option value=all>All benches</select><span id=pos class=mute></span><span id=done class=mute></span></header>
<main><section id=pics></section><aside>
<h1 id=title></h1><div id=facts class=mute></div><div class=marks id=marks></div>
<div class=keys>
<kbd>g</kbd><span>right as shown (with no photo: I see no bench in any view)</span><kbd>p</kbd><span>wrong photo: veto it, keep the bench</span>
<kbd>x</kbd><span>no bench here: hide it</span><kbd>w</kbd><span>wrong spot</span>
<kbd>s</kbd><span>bus / tram / train stop: hide it</span><kbd>← →</kbd><span>previous / next</span>
<kbd>↑ ↓</kbd><span>cycle this bench's views (or 1-9)</span><kbd>h</kbd><span>there is a bench: use the shown view as the photo</span><kbd>n</kbd><span>next unreviewed</span><kbd>u</kbd><span>undo this bench</span></div>
<div id=links></div><iframe id=map loading=lazy></iframe></aside></main>
<script>
const KEYS={g:"good",p:"wrong photo",x:"no bench",w:"wrong spot",s:"bus stop"},ADV=new Set("gpxs");
let Q=[],S={feedback:{},wrong_photo:[],hero_pick:{}},i=0,sel=null;
const $=id=>document.getElementById(id),esc=s=>String(s??"").replace(/[&<'"]/g,c=>"&#"+c.charCodeAt(0)+";");
async function boot(){const q=location.hash.slice(1)||new URLSearchParams(location.search).get("q")||"new";$("qsel").value=q;$("title").textContent="Loading…";
 [Q,S]=await Promise.all([fetch("queue?name="+q).then(r=>r.json()),fetch("state").then(r=>r.json())]);
 i=Q.findIndex(b=>!S.feedback[b.id]);if(i<0)i=0;show()}
$("qsel").onchange=e=>{location.hash=e.target.value;boot()};
function show(){sel=null;const b=Q[i];if(!b){$("title").textContent="Queue empty";$("pics").innerHTML="";return}
 const m=S.feedback[b.id]||[];$("pos").textContent=`${i+1} / ${Q.length}`;
 $("done").textContent=`${Q.filter(x=>S.feedback[x.id]).length} reviewed`;
 $("title").textContent=`#${b.id} ${b.address}`;$("facts").textContent=b.facts;
 $("marks").innerHTML=m.map(x=>`<span>${esc(x)}</span>`).join("");
 const hero=b.hero?`<img class=hero src="${esc(b.hero)}"><p class=cap>published crop of the HERO view · click a view below to see it whole</p>`:`<div class=none>no photo · ${b.views.length?b.views.length+" views, none passed (needs 0.60)":"no street-level imagery"}</div>`;
 $("pics").innerHTML=`<div id=big>${hero}</div>`+`<div class=views>${b.views.map(v=>`<a data-id=${v.id} class="${v.id===b.hero_id?"h":""}" href="${esc(v.src)}" target=_blank><img loading=lazy src="${esc(v.src)}"><i>${S.hero_pick[b.id]===v.id?"PICKED · ":v.id===b.hero_id?"HERO · ":""}${v.score==null?"–":v.score.toFixed(2)} ${esc((v.source||"").slice(0,5))} ${esc((v.when||"").slice(0,7))}</i></a>`).join("")}</div>`;
 $("links").innerHTML=`<a href="https://bench.blackmad.com/bench/${b.id}" target=_blank>live</a> · <a href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${b.lat},${b.lng}" target=_blank>street view</a> · <a href="https://www.openstreetmap.org/?mlat=${b.lat}&mlon=${b.lng}#map=19/${b.lat}/${b.lng}" target=_blank>OSM</a>`;
 const d=.0012;$("map").src=`https://www.openstreetmap.org/export/embed.html?bbox=${b.lng-d*1.6},${b.lat-d},${b.lng+d*1.6},${b.lat+d}&layer=mapnik&marker=${b.lat},${b.lng}`}
function pickView(a){sel=+a.dataset.id;document.querySelectorAll(".views a").forEach(x=>x.classList.toggle("sel",x===a));
 const all=[...document.querySelectorAll(".views a")],n=all.indexOf(a)+1;
 $("big").innerHTML=`<img class=hero src="${esc(a.getAttribute("href"))}"><p class=cap>view ${n} of ${all.length} · ${a.classList.contains("h")?"the HERO view, uncropped":"press h to use it as the photo"} · ↑↓ or 1-9 for others</p>`}
function stepView(d){const all=[...document.querySelectorAll(".views a")];if(!all.length)return;
 const cur=all.findIndex(x=>+x.dataset.id===sel);pickView(all[(cur<0?(d>0?0:all.length-1):(cur+d+all.length)%all.length)])}
document.addEventListener("click",e=>{const a=e.target.closest(".views a");if(!a||e.metaKey||e.ctrlKey)return;
 e.preventDefault();pickView(a)});
async function save(b,marks){const r=await fetch("mark",{method:"POST",body:JSON.stringify({id:b.id,marks,hero_id:b.hero_id})});S=await r.json();show()}
document.onkeydown=e=>{if(e.metaKey||e.ctrlKey||e.altKey)return;const b=Q[i],k=e.key;
 if(k==="ArrowDown"||k==="ArrowUp"){e.preventDefault();stepView(k==="ArrowDown"?1:-1)}
 else if(/^[1-9]$/.test(k)){const a=document.querySelectorAll(".views a")[+k-1];if(a)pickView(a)}
 else if(k==="ArrowRight"||k==="j"){i=Math.min(Q.length-1,i+1);show()}
 else if(k==="ArrowLeft"||k==="k"){i=Math.max(0,i-1);show()}
 else if(k==="n"){const j=Q.findIndex((x,n)=>n>i&&!S.feedback[x.id]);if(j>=0){i=j;show()}}
 else if(k==="u"&&b){fetch("mark",{method:"POST",body:JSON.stringify({id:b.id,marks:[],pick:null})}).then(r=>r.json()).then(x=>{S=x;show()})}
 else if(k==="h"&&b&&(sel=sel||b.hero_id||(b.views[0]||{}).id)){const m=new Set(S.feedback[b.id]||[]);m.delete("wrong photo");m.delete("no bench");m.add("good");
  fetch("mark",{method:"POST",body:JSON.stringify({id:b.id,marks:[...m],pick:sel})}).then(r=>r.json()).then(x=>{S=x;if(i<Q.length-1)i++;show()})}
 else if(KEYS[k]&&b){const m=new Set(S.feedback[b.id]||[]);m.add(KEYS[k]);
  if(k==="g"){m.delete("wrong photo");m.delete("no bench")}if(k!=="g"&&k!=="w")m.delete("good");
  save(b,[...m]).then(()=>{if(ADV.has(k)&&i<Q.length-1){i++;show()}})}};
boot();
</script>"""


def serve(base: str | None, port: int) -> None:
    cache: dict[str, bytes] = {}
    lock = threading.Lock()

    def queue_body(name: str) -> bytes:
        with lock:  # one build at a time; each reads the whole DB
            if name not in cache:
                cache[name] = json.dumps(build_queue(name, base)).encode()
            return cache[name]

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, data: bytes, ctype: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0].lstrip("/")
            if path == "":
                return self._send(PAGE.encode(), "text/html; charset=utf-8")
            if path == "queue":
                q = parse_qs(urlparse(self.path).query).get("name", ["new"])[0]
                if q not in QUEUES:
                    return self.send_error(404)
                return self._send(queue_body(q), "application/json")
            if path == "duel":
                return self._send(duel.PAGE.encode(), "text/html; charset=utf-8")
            if path == "duel.json":
                return self._send(json.dumps(duel.items()).encode(), "application/json")
            if path == "state":
                return self._send(json.dumps(_state()).encode(), "application/json")
            for prefix, root in ROOTS.items():
                f = (root / path).resolve()
                if (
                    path.startswith(prefix)
                    and f.is_file()
                    and root.resolve() in f.parents
                ):
                    ext = f.suffix.lower().lstrip(".")
                    ctype = {"jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(
                        ext, f"image/{ext}"
                    )
                    return self._send(f.read_bytes(), ctype)
            self.send_error(404)

        def do_POST(self):
            if self.path == "/duel":
                return self._duel()
            if self.path != "/mark":
                return self.send_error(404)
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            s = _state()
            bid, marks = str(req["id"]), req["marks"]
            if marks:
                s["feedback"][bid] = marks
            else:
                s["feedback"].pop(bid, None)
            if "pick" in req:  # "use this view as the hero" (None clears it)
                if req["pick"]:
                    s["hero_pick"][bid] = req["pick"]
                else:
                    s["hero_pick"].pop(bid, None)
            hero = req.get("hero_id")
            wrong = set(s["wrong_photo"])
            if hero:
                (wrong.add if "wrong photo" in marks else wrong.discard)(hero)
            s["wrong_photo"] = sorted(wrong)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(s, indent=0))
            self._send(json.dumps(s).encode(), "application/json")

        def _duel(self) -> None:
            """A duel vote; a photo chosen as better becomes the bench's hero."""
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            bid, vote = str(req["bench"]), req.get("vote")
            old = next(
                (x["vote"] for x in duel.items() if str(x["bench"]) == bid), None
            )
            s = _state()
            if old and old.get("hero") and s["hero_pick"].get(bid) == old["hero"]:
                s["hero_pick"].pop(bid)  # undo what this page set before
            if vote and vote.get("hero"):
                s["hero_pick"][bid] = vote["hero"]
            OUT.write_text(json.dumps(s, indent=0))
            duel.save(int(bid), vote)
            self._send(b"{}", "application/json")

    print(f"http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument(
        "--from", dest="base", help="snapshot to compare with (default: oldest)"
    )
    ap.add_argument("--port", type=int, default=8897)
    a = ap.parse_args()
    serve(a.base, a.port)


if __name__ == "__main__":
    main()
