"""Keyboard review of benches: one at a time, marks saved as you go.

    uv run python -m bench_finder.review [--queue new|changed|photoless|all]
    open http://localhost:8897

Keys: g good · p wrong photo (veto it, keep the bench) · x no bench here (hide)
· w wrong spot · s bus/tram/train stop (hide) · ←/→ or j/k move · u undo.
Marks go to ``data/feedback/review.json``: ``feedback`` {bench: [marks]} and
``wrong_photo`` [image ids], which ``publish`` reads (bench_finder.publish.exclude).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bench_finder.publish.build import AMSTERDAM_BBOX, select_images
from bench_finder.whats_new import SNAPS, diff, load


OUT = Path("data/feedback/review.json")
ROOTS = {"img/": Path("dist-data"), "images/": Path(".")}
QUEUES = {
    "new": ("new_bench",),
    "changed": ("photo_changed", "photo_gained"),
    "photoless": (),
    "all": (),
}


def _state() -> dict:
    s = json.loads(OUT.read_text()) if OUT.exists() else {}
    s.setdefault("feedback", {})
    s.setdefault("wrong_photo", [])
    return s


def build_queue(queue: str, base: str | None) -> list[dict]:
    snaps = sorted(p.name for p in SNAPS.iterdir() if p.is_dir())
    new = load(SNAPS / snaps[-1])
    if queue in ("new", "changed"):
        ch = diff(load(SNAPS / (base or snaps[0])), new)
        ids = [it["new"]["id"] for k in QUEUES[queue] for it in ch[k] if it.get("new")]
    elif queue == "photoless":
        ids = [i for i, b in new.items() if not b.get("hero_key")]
    else:
        ids = sorted(new)
    conn = sqlite3.connect("file:data/benches.db?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    _, _, chosen = select_images(conn, Path("images"), True, bbox=AMSTERDAM_BBOX)
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
                    "src": fp,
                    "score": score.get(iid),
                    "source": src,
                    "when": when,
                }
            )
    conn.close()
    items = []
    for i in ids:
        b = new[i]
        imgs, has_hero = chosen.get(i, ([], False))
        hero = imgs[0]["id"] if has_hero and imgs else None
        v = sorted(views.get(i, []), key=lambda x: -(x["score"] or 0))[:12]
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
.views a{position:relative;display:block;outline:3px solid transparent}.views a.h{outline-color:var(--hi)}
.views img{width:100%;aspect-ratio:1;object-fit:cover;display:block}
.views i{position:absolute;left:2px;bottom:2px;font:11px system-ui;background:#fffd;padding:0 3px;font-style:normal}
aside{display:grid;gap:10px;align-content:start}h1{font-size:20px;margin:0}.mute{color:var(--mute)}
iframe{width:100%;height:220px;border:0}.keys{display:grid;grid-template-columns:auto 1fr;gap:4px 10px}
kbd{font:12px ui-monospace,monospace;border:1px solid #c9bea8;border-bottom-width:2px;padding:1px 6px;background:var(--card);text-align:center}
.on{background:var(--ink);color:var(--card)}.marks{min-height:24px}.marks span{background:var(--ink);color:var(--card);padding:2px 8px;margin-right:4px}
@media(max-width:800px){main{grid-template-columns:1fr}.views{grid-template-columns:repeat(4,1fr)}}
</style>
<header><b>Bench review</b><span id=pos class=mute></span><span id=done class=mute></span></header>
<main><section id=pics></section><aside>
<h1 id=title></h1><div id=facts class=mute></div><div class=marks id=marks></div>
<div class=keys>
<kbd>g</kbd><span>good</span><kbd>p</kbd><span>wrong photo: veto it, keep the bench</span>
<kbd>x</kbd><span>no bench here: hide it</span><kbd>w</kbd><span>wrong spot</span>
<kbd>s</kbd><span>bus / tram / train stop: hide it</span><kbd>← →</kbd><span>previous / next</span>
<kbd>n</kbd><span>next unreviewed</span><kbd>u</kbd><span>undo this bench</span></div>
<div id=links></div><iframe id=map loading=lazy></iframe></aside></main>
<script>
const KEYS={g:"good",p:"wrong photo",x:"no bench",w:"wrong spot",s:"bus stop"},ADV=new Set("gpxs");
let Q=[],S={feedback:{},wrong_photo:[]},i=0;
const $=id=>document.getElementById(id),esc=s=>String(s??"").replace(/[&<'"]/g,c=>"&#"+c.charCodeAt(0)+";");
async function boot(){[Q,S]=await Promise.all([fetch("queue").then(r=>r.json()),fetch("state").then(r=>r.json())]);
 i=Q.findIndex(b=>!S.feedback[b.id]);if(i<0)i=0;show()}
function show(){const b=Q[i];if(!b){$("title").textContent="Queue empty";return}
 const m=S.feedback[b.id]||[];$("pos").textContent=`${i+1} / ${Q.length}`;
 $("done").textContent=`${Q.filter(x=>S.feedback[x.id]).length} reviewed`;
 $("title").textContent=`#${b.id} ${b.address}`;$("facts").textContent=b.facts;
 $("marks").innerHTML=m.map(x=>`<span>${esc(x)}</span>`).join("");
 const hero=b.hero?`<img class=hero src="${esc(b.hero)}">`:`<div class=none>no photo · ${b.views.length?b.views.length+" views, none passed (needs 0.60)":"no street-level imagery"}</div>`;
 $("pics").innerHTML=hero+`<div class=views>${b.views.map(v=>`<a class="${v.id===b.hero_id?"h":""}" href="${esc(v.src)}" target=_blank><img loading=lazy src="${esc(v.src)}"><i>${v.score==null?"–":v.score.toFixed(2)} ${esc((v.source||"").slice(0,5))} ${esc((v.when||"").slice(0,7))}</i></a>`).join("")}</div>`;
 $("links").innerHTML=`<a href="https://bench.blackmad.com/bench/${b.id}" target=_blank>live</a> · <a href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${b.lat},${b.lng}" target=_blank>street view</a> · <a href="https://www.openstreetmap.org/?mlat=${b.lat}&mlon=${b.lng}#map=19/${b.lat}/${b.lng}" target=_blank>OSM</a>`;
 const d=.0012;$("map").src=`https://www.openstreetmap.org/export/embed.html?bbox=${b.lng-d*1.6},${b.lat-d},${b.lng+d*1.6},${b.lat+d}&layer=mapnik&marker=${b.lat},${b.lng}`}
async function save(b,marks){const r=await fetch("mark",{method:"POST",body:JSON.stringify({id:b.id,marks,hero_id:b.hero_id})});S=await r.json();show()}
document.onkeydown=e=>{if(e.metaKey||e.ctrlKey||e.altKey)return;const b=Q[i],k=e.key;
 if(k==="ArrowRight"||k==="j"){i=Math.min(Q.length-1,i+1);show()}
 else if(k==="ArrowLeft"||k==="k"){i=Math.max(0,i-1);show()}
 else if(k==="n"){const j=Q.findIndex((x,n)=>n>i&&!S.feedback[x.id]);if(j>=0){i=j;show()}}
 else if(k==="u"&&b)save(b,[]);
 else if(KEYS[k]&&b){const m=new Set(S.feedback[b.id]||[]);m.has(KEYS[k])?m.delete(KEYS[k]):m.add(KEYS[k]);
  if(k==="g"){m.delete("wrong photo");m.delete("no bench")}if(k!=="g"&&k!=="w")m.delete("good");
  save(b,[...m]).then(()=>{if(ADV.has(k)&&m.has(KEYS[k])&&i<Q.length-1){i++;show()}})}};
boot();
</script>"""


def serve(queue: list[dict], port: int) -> None:
    body_q = json.dumps(queue).encode()

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
                return self._send(body_q, "application/json")
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
            if self.path != "/mark":
                return self.send_error(404)
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            s = _state()
            bid, marks = str(req["id"]), req["marks"]
            if marks:
                s["feedback"][bid] = marks
            else:
                s["feedback"].pop(bid, None)
            hero = req.get("hero_id")
            wrong = set(s["wrong_photo"])
            if hero:
                (wrong.add if "wrong photo" in marks else wrong.discard)(hero)
            s["wrong_photo"] = sorted(wrong)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(s, indent=0))
            self._send(json.dumps(s).encode(), "application/json")

    print(f"http://localhost:{port}  ({len(queue)} benches)")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--queue", choices=list(QUEUES), default="new")
    ap.add_argument(
        "--from", dest="base", help="snapshot to compare with (default: oldest)"
    )
    ap.add_argument("--port", type=int, default=8897)
    a = ap.parse_args()
    serve(build_queue(a.queue, a.base), a.port)


if __name__ == "__main__":
    main()
