"""Hero explorer: look through every Google, Apple and City of Amsterdam panorama
near a bench and make the best framing its hero.

Served by the review server at ``/explore?id=<bench>`` (``e`` on the review and duel
pages opens it for the bench on screen). Each panorama is downloaded once and kept
in memory while you aim, zoom and tilt. Previews are rendered from that copy.
"Use as hero" renders the view at 1024 px (plus a 2048 px hi-res cut, as
``bench_finder.recut`` makes), saves it as a ``kind = 'framed'`` image (one per panorama per bench) and sets it
as
the bench's ``hero_pick`` in the review feedback, so the next publish leads with it.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import sqlite3
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image

from bench_finder.core.pano_geometry import (
    PanoCandidate,
    apple_center_compass,
    google_center_compass,
    haversine_m,
    render_aimed_view,
)


if TYPE_CHECKING:
    import numpy as np

from bench_finder.vantage import (
    Bench,
    amsterdam_candidates,
    amsterdam_equirect,
    fov_for,
    score,
)


DB = "data/benches.db"
SNAPS = Path("data/snapshots")
PREVIEW_PX = 640
SAVE_PX, HIRES_PX = 1024, 2048
KEEP_PANOS = 4  # equirects held in memory (an Apple one is ~60 MB)
# Exploring resolution: Google zoom 3 (4096 px), Apple zoom 2 (6416 px, ~20 s
# to stitch), the city's "medium" (4000 px). Saving fetches more when needed.
GOOGLE_PREVIEW_W = 4096
APPLE_PREVIEW_ZOOM = 2
APPLE_WIDTHS = {0: 16384, 1: 12016, 2: 6416, 3: 4560}


# The ``images`` columns a saved view sets (as BenchDatabase.add_image does).
SAVED_FIELDS = (
    "heading",
    "filepath",
    "filename",
    "file_size",
    "capture_success",
    "capture_error",
    "image_source",
    "panorama_lat",
    "panorama_lng",
    "panorama_metadata",
    "panorama_heading",
    "pano_id",
    "pano_date",
    "camera_bearing_deg",
    "camera_distance_m",
    "fov_deg",
    "pitch_deg",
    "kind",
)


def _wrap(rad: float | None) -> float:
    return 0.0 if rad is None else (rad + math.pi) % (2 * math.pi) - math.pi


@dataclass
class Pano:
    arr: np.ndarray
    center: float  # compass bearing of the equirect's centre column
    pitch: float
    roll: float

    @property
    def width(self) -> int:
        return int(self.arr.shape[1])


def _needed_width(fov: float, out_px: int) -> int:
    return math.ceil(out_px * 360.0 / fov)


def load_bench(bid: int, db: str = DB) -> tuple[Bench, dict]:
    """The bench (with facing, as vantage sees it) and what the page shows about it."""
    from bench_finder.publish.build import parse_direction
    from bench_finder.publish.images import render_source

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT c.lat, c.lng, c.tags, a.facing_deg, a.faces_category, a.facing_method, "
        "g.formatted_address FROM bench_candidates c "
        "LEFT JOIN bench_attributes a ON a.bench_candidate_id = c.id "
        "LEFT JOIN reverse_geocodes g ON g.bench_candidate_id = c.id WHERE c.id = ?",
        (bid,),
    ).fetchone()
    if row is None:
        conn.close()
        raise KeyError(bid)
    lat, lng, tags, facing, faces, method, addr = row
    if facing is None:
        facing = parse_direction((json.loads(tags) if tags else {}).get("direction"))
    views = [
        {
            "id": iid,
            "pano": str(pid),
            "src": "/" + str(render_source(Path(fp), faded=False)),
            "source": src,
            "when": (when or "")[:7],
        }
        for iid, pid, fp, src, when in conn.execute(
            "SELECT id, pano_id, filepath, image_source, pano_date FROM images "
            "WHERE bench_candidate_id = ? AND kind IN ('aimed', 'framed') "
            "AND capture_success = 1 "
            "AND filepath IS NOT NULL ORDER BY id",
            (bid,),
        )
    ]
    conn.close()
    bench = Bench(
        bid,
        lat,
        lng,
        None if facing is None else float(facing),
        faces == "water" or method == "water_edge",
        frozenset(v["pano"] for v in views),
    )
    hero = None
    snaps = sorted(p for p in SNAPS.iterdir() if p.is_dir()) if SNAPS.exists() else []
    f = snaps[-1] / "data" / "bench" / f"{bid}.json" if snaps else None
    if f and f.exists():
        hero = (json.loads(f.read_text()).get("hero_urls") or {}).get("800")
    info = {
        "id": bid,
        "lat": lat,
        "lng": lng,
        "facing": bench.facing,
        "address": (addr or "").split(",")[0],
        "hero": hero,
        "views": views,
    }
    return bench, info


def newest_per_spot(
    cands: list[PanoCandidate], cell_m: float = 3.0
) -> list[PanoCandidate]:
    """The city's API returns every mission year at every spot: keep the newest one
    per ``cell_m`` grid cell."""
    best: dict[tuple[int, int], PanoCandidate] = {}
    for c in cands:
        cell = (round(c.lat * 111_320 / cell_m), round(c.lon * 68_000 / cell_m))
        if cell not in best or (c.date_str or "") > (best[cell].date_str or ""):
            best[cell] = c
    return list(best.values())


class Explorer:
    """Panorama search and rendering on one background event loop."""

    def __init__(self, db: str = DB) -> None:
        self.db = db
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self._client: Any = None
        self._session: Any = None
        self.cands: dict[tuple[int, int], tuple[Bench, dict, list[PanoCandidate]]] = {}
        self.panos: OrderedDict[tuple[str, str, int], Pano] = OrderedDict()
        self.fetching: dict[tuple[str, str, int], asyncio.Future] = {}

    def run(self, coro) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    async def _ready(self) -> tuple[Any, Any]:
        if self._client is None:
            import aiohttp

            from bench_finder.core.streetview import StreetViewClient

            self._client = StreetViewClient()
            self._client.indoor_filter = None  # you are looking at it yourself
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=300, connect=20)
            )
        return self._client, self._session

    # ------------------------------------------------------------ candidates

    def bench(self, bid: int, radius: int) -> dict:
        return self.run(self._bench(bid, radius))

    async def _bench(self, bid: int, radius: int) -> dict:
        bench, info = await asyncio.to_thread(load_bench, bid, self.db)
        client, session = await self._ready()
        g, e1 = await client.enumerate_google_panoramas(
            bench.lat, bench.lng, session, max_m=radius
        )
        a, e2 = await client.enumerate_apple_panoramas(
            bench.lat, bench.lng, session, max_m=radius
        )
        errors = e1 + e2
        try:
            ams = await amsterdam_candidates(bench.lat, bench.lng, radius, session)
        except Exception as e:
            ams, errors = [], [*errors, f"amsterdam: {e}"]
        cands = [c for c in g if not c.is_third_party] + a + newest_per_spot(ams)
        self.cands[(bid, radius)] = (bench, info, cands)
        out = []
        for k, c in enumerate(cands):
            rel = (
                None
                if bench.facing is None
                else math.cos(math.radians(c.bearing_deg - bench.facing))
            )
            out.append(
                {
                    "k": k,
                    "key": f"{c.source}:{c.pano_id}",
                    "source": c.source,
                    "lat": c.lat,
                    "lng": c.lon,
                    "dist": round(c.distance_m, 1),
                    "bearing": round(c.bearing_deg, 1),
                    "date": (c.date_str or "")[:10] or (str(c.year) if c.year else ""),
                    "side": None
                    if rel is None
                    else "behind"
                    if rel > 0.34
                    else "front"
                    if rel < -0.34
                    else "side",
                    "have": c.pano_id in bench.have,
                    "score": score(c, bench),
                    "fov": round(fov_for(c.distance_m), 1),
                }
            )
        # Vantage's ranking first (best shots on top), then the rest by distance.
        out.sort(key=lambda o: (o["score"] is None, -(o["score"] or 0), o["dist"]))
        return {**info, "panos": out, "errors": errors[:5]}

    def _cand(self, bid: int, key: str) -> tuple[Bench, PanoCandidate]:
        for (b, _), (bench, _, cands) in self.cands.items():
            if b == bid:
                for c in cands:
                    if f"{c.source}:{c.pano_id}" == key:
                        return bench, c
        raise KeyError(key)

    # ----------------------------------------------------------- panoramas

    async def _pano(self, c: PanoCandidate, width: int) -> Pano:
        """The panorama with at least ``width`` px across (as close as the source has)."""
        for (src, pid, w), p in self.panos.items():
            if (src, pid) == (c.source, c.pano_id) and w >= width:
                self.panos.move_to_end((src, pid, w))
                return p
        key = (c.source, c.pano_id, width)
        if key not in self.fetching:
            self.fetching[key] = asyncio.ensure_future(self._download(c, width))
        try:
            p = await asyncio.shield(self.fetching[key])
        finally:
            self.fetching.pop(key, None)
        self.panos[(c.source, c.pano_id, p.width)] = p
        while len(self.panos) > KEEP_PANOS:
            self.panos.popitem(last=False)
        return p

    async def _download(self, c: PanoCandidate, width: int) -> Pano:
        from bench_finder.core.streetview import _decode_faces, _to_rgb_array

        client, session = await self._ready()
        if c.source == "google":
            pano = c.raw
            if not pano.image_sizes:  # metadata from the coverage tile only
                pano = await client._google_meta(c.pano_id, session)
            widths = [s.x for s in pano.image_sizes]
            zoom = next(
                (z for z, w in enumerate(widths) if w >= width), len(widths) - 1
            )
            img = await client._download_google_pano(pano, zoom, session)
            arr = await asyncio.to_thread(_to_rgb_array, img)
            return Pano(
                arr,
                google_center_compass(pano.heading),
                _wrap(pano.pitch),
                _wrap(pano.roll),
            )
        if c.source == "apple":
            from streetlevel import lookaround

            try:
                from pillow_heif import register_heif_opener

                register_heif_opener()
            except ImportError:
                pass
            pano = c.raw
            fits = [z for z, w in APPLE_WIDTHS.items() if w >= width]
            zoom = max(fits) if fits else 0
            blobs = await asyncio.gather(
                *[client._fetch_apple_face(pano, i, zoom) for i in range(6)]
            )
            faces = await asyncio.to_thread(_decode_faces, blobs)
            equirect = await asyncio.to_thread(
                lookaround.to_equirectangular, faces, pano.camera_metadata
            )
            arr = await asyncio.to_thread(_to_rgb_array, equirect)
            return Pano(
                arr,
                apple_center_compass(pano.heading),
                _wrap(pano.pitch),
                _wrap(pano.roll),
            )
        size = "medium" if width <= 4000 else "full"
        arr = await amsterdam_equirect(c.pano_id, session, size)
        return Pano(arr, 0.0, 0.0, 0.0)

    @staticmethod
    def _render(p: Pano, aim: float, fov: float, tilt: float, px: int) -> np.ndarray:
        return render_aimed_view(
            p.arr,
            center_compass_deg=p.center,
            aim_bearing_deg=aim,
            fov_deg=fov,
            out_size=px,
            pitch_rad=p.pitch,
            roll_rad=p.roll,
            tilt_deg=tilt,
        )

    def preview(self, bid: int, key: str, aim: float, fov: float, tilt: float) -> bytes:
        return self.run(self._preview(bid, key, aim, fov, tilt))

    async def _preview(
        self, bid: int, key: str, aim: float, fov: float, tilt: float
    ) -> bytes:
        _, c = self._cand(bid, key)
        want = (
            GOOGLE_PREVIEW_W
            if c.source != "apple"
            else APPLE_WIDTHS[APPLE_PREVIEW_ZOOM]
        )
        p = await self._pano(c, want)
        view = await asyncio.to_thread(self._render, p, aim, fov, tilt, PREVIEW_PX)
        buf = io.BytesIO()
        Image.fromarray(view).save(buf, "JPEG", quality=85)
        return buf.getvalue()

    # ----------------------------------------------------------------- save

    def save(
        self, bid: int, key: str, aim: float, fov: float, tilt: float, images_dir: str
    ) -> int:
        return self.run(self._save(bid, key, aim, fov, tilt, images_dir))

    async def _save(
        self, bid: int, key: str, aim: float, fov: float, tilt: float, images_dir: str
    ) -> int:
        from bench_finder.core.streetview import _safe_name
        from bench_finder.models.enums import ImageKind, ImageSource
        from bench_finder.models.streetview_models import (
            PanoramaMetadata,
            StreetViewImageCaptureSuccess,
        )
        from bench_finder.publish.images import hires_path
        from bench_finder.services.image_download_service import image_base_from_capture

        bench, c = self._cand(bid, key)
        client, _ = await self._ready()
        p = await self._pano(c, _needed_width(fov, HIRES_PX))
        name = (
            f"aimed_{bid}_{_safe_name(c.pano_id)}_x{round(aim) % 360}"
            f"f{round(fov)}t{round(tilt)}.jpg"
        )
        path = Path(images_dir) / name
        for px, dest in ((SAVE_PX, path), (HIRES_PX, hires_path(path))):
            view = await asyncio.to_thread(self._render, p, aim, fov, tilt, px)
            dest.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(
                Image.fromarray(view).save, dest, "JPEG", quality=92
            )
        source = {
            "google": ImageSource.STREETVIEW_STREETLEVEL,
            "apple": ImageSource.APPLE_STREETLEVEL,
        }.get(c.source, ImageSource.AMSTERDAM_PANORAMA)
        common = client._common_fields(
            c, str(bid), bench.lat, bench.lng, fov, name, source
        )
        # The aim is what you framed, not the straight line to the bench pin;
        # recut reads it (and the tilt, from pitch_deg) to re-render the same view.
        common.update(
            heading=round(aim) % 360,
            camera_bearing_deg=aim % 360,
            camera_distance_m=haversine_m(c.lat, c.lon, bench.lat, bench.lng),
            pitch_deg=-tilt,
            kind=ImageKind.FRAMED.value,
        )
        if c.source == "google":
            common["panorama_metadata"] = PanoramaMetadata.from_streetview_pano(c.raw)
        elif c.source == "apple":
            common["panorama_metadata"] = PanoramaMetadata.from_lookaround_pano(c.raw)
        cap = StreetViewImageCaptureSuccess(
            filepath=str(path),
            file_size=path.stat().st_size,
            cached=False,
            width=SAVE_PX,
            height=SAVE_PX,
            **common,
        )
        base = image_base_from_capture(cap)
        return await asyncio.to_thread(self._insert, base, bid)

    def _insert(self, base: Any, bid: int) -> int:
        """The bench's ``framed`` row for this panorama, created or replaced.

        Not ``BenchDatabase.add_image``'s upsert on kind ``aimed``: that would
        overwrite the bench's automatic view from this panorama (and orphan its
        detections). ``framed`` is a separate kind, so the explorer only ever
        replaces its own earlier framing from the same panorama."""
        from bench_finder.models.unified_models import Image as ImageRow
        from bench_finder.services.database import BenchDatabase

        # db_url, not db_path: config always sets DATABASE_URL, which wins over db_path.
        db = BenchDatabase(db_url=f"sqlite:///{self.db}")
        with db.get_session() as session:
            row = (
                session.query(ImageRow)
                .filter(
                    ImageRow.bench_candidate_id == bid,
                    ImageRow.pano_id == base.pano_id,
                    ImageRow.kind == base.kind,
                )
                .first()
            ) or ImageRow(bench_candidate_id=bid)
            for field in SAVED_FIELDS:
                setattr(row, field, getattr(base, field))
            session.add(row)
            session.commit()
            session.refresh(row)
            return int(row.id)


PAGE = r"""<!doctype html><meta charset=utf-8><title>Hero explorer</title>
<meta name=viewport content="width=device-width">
<link rel=stylesheet href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{box-sizing:border-box}
body{margin:0;font:14px system-ui;background:#1c1b19;color:#eee;height:100vh;display:flex;flex-direction:column;overflow:hidden}
header{display:flex;gap:14px;align-items:center;padding:8px 14px;border-bottom:1px solid #333}
header h1{font-size:16px;margin:0}header input,header select{font:inherit;background:#2a2926;color:#eee;border:1px solid #444;padding:3px 6px;width:90px}
header select{width:auto}#srcs input{width:auto}a{color:#9bd}.mute{color:#999}
main{flex:1;display:grid;grid-template-columns:400px 1fr;min-height:0}
#left{display:flex;flex-direction:column;min-height:0;border-right:1px solid #333}
#map{height:330px;background:#ddd}
#list{flex:1;overflow:auto}
#list div{display:grid;grid-template-columns:14px 70px 1fr auto;gap:8px;padding:5px 10px;cursor:pointer;border-bottom:1px solid #2a2926;align-items:center}
#list div:hover{background:#2a2926}#list div.on{background:#3a3524}
#list i{width:10px;height:10px;border-radius:50%;display:block}
#list .have{color:#e8b04a}
#right{display:flex;flex-direction:column;min-height:0;padding:10px 14px;gap:8px}
#stage{flex:1;min-height:0;display:flex;gap:12px}
#vwrap{position:relative;flex:1;min-width:0;display:flex;align-items:center;justify-content:center;background:#000;border-radius:6px}
#view{max-width:100%;max-height:100%;aspect-ratio:1;object-fit:contain}
#cross{position:absolute;left:50%;top:50%;width:18px;height:18px;margin:-9px;border:1px solid #fff8;border-radius:50%;pointer-events:none}
#busy{position:absolute;top:10px;left:10px;background:#000c;padding:6px 10px;border-radius:6px;display:none}
#side{width:220px;overflow:auto;display:flex;flex-direction:column;gap:6px}
#side img{width:100%;border-radius:4px;display:block}#side p{margin:0;font-size:12px;color:#aaa}
#info{color:#ccc}#info b{color:#fff}
footer{display:flex;gap:14px;flex-wrap:wrap;color:#aaa;font-size:12.5px}
kbd{background:#eee;color:#222;border-radius:4px;padding:0 5px;font:12px ui-monospace,monospace}
button{font:inherit;background:#e8b04a;border:0;padding:6px 14px;border-radius:6px;cursor:pointer;font-weight:600}
button:disabled{opacity:.5}
#toast{position:fixed;top:40%;left:50%;transform:translate(-50%,-50%);font-size:26px;font-weight:700;background:#000d;padding:14px 26px;border-radius:12px;opacity:0;transition:opacity .4s;pointer-events:none}
</style>
<header><h1>Hero explorer</h1>
<label>bench <input id=bid></label>
<label>within <select id=rad><option>30<option selected>50<option>80<option>120</select> m</label>
<span id=srcs><label><input type=checkbox value=google checked> google</label> <label><input type=checkbox value=apple checked> apple</label> <label><input type=checkbox value=amsterdam checked> city</label></span>
<span id=addr class=mute></span><span id=links></span></header>
<main><div id=left><div id=map></div><div id=list></div></div>
<div id=right>
<div id=info class=mute>Pick a panorama on the map or in the list.</div>
<div id=stage><div id=vwrap><img id=view><div id=cross></div><div id=busy></div></div>
<div id=side><p>published hero</p><div id=hero></div><p>views it already has</p><div id=views></div></div></div>
<footer><span><kbd>←</kbd><kbd>→</kbd> aim (<kbd>shift</kbd> ×5)</span><span><kbd>-</kbd><kbd>=</kbd> zoom out / in</span>
<span><kbd>↑</kbd><kbd>↓</kbd> tilt</span><span><kbd>r</kbd> reset framing</span><span>drag the photo to pan</span>
<span><kbd>j</kbd><kbd>k</kbd> next / previous panorama</span><span><kbd>Enter</kbd> use as hero</span>
<button id=save disabled>Use as hero</button></footer>
</div></main>
<div id=toast></div>
<script>
const $=id=>document.getElementById(id),esc=s=>String(s??"").replace(/[&<'"]/g,c=>"&#"+c.charCodeAt(0)+";");
const COL={google:"#4285f4",apple:"#bbb",amsterdam:"#e23b1e"};
let B=null,P=[],cur=-1,aim=0,fov=40,tilt=0,seq=0,map=L.map("map",{zoomControl:false}),layer=L.layerGroup().addTo(map),cone=null;
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:21,maxNativeZoom:19,attribution:"© OpenStreetMap"}).addTo(map);
const qs=new URLSearchParams(location.search);$("bid").value=qs.get("id")||"";
document.querySelectorAll("#srcs input").forEach(x=>x.onchange=()=>B&&draw());
$("bid").onchange=()=>{history.replaceState(null,"","?id="+$("bid").value);load()};$("rad").onchange=load;
function dest(lat,lng,brg,m){const r=brg*Math.PI/180,dy=m*Math.cos(r)/111320,dx=m*Math.sin(r)/(111320*Math.cos(lat*Math.PI/180));return[lat+dy,lng+dx]}
async function load(){const id=+$("bid").value;if(!id)return;busy("finding panoramas…");
 const r=await fetch(`/explore/bench?id=${id}&r=${$("rad").value}`);busy(null);
 if(!r.ok){$("info").textContent="bench not found";return}
 B=await r.json();draw()}
function draw(){const on=new Set([...document.querySelectorAll("#srcs input:checked")].map(x=>x.value));
 P=B.panos.filter(p=>on.has(p.source));cur=-1;
 $("addr").textContent=`#${B.id} ${B.address}`+(B.facing==null?" · facing unknown":` · faces ${Math.round(B.facing)}°`)+` · ${P.length} of ${B.panos.length} panoramas`+(B.errors.length?` · ${B.errors.length} errors`:"");
 $("links").innerHTML=`<a target=_blank href="https://bench.blackmad.com/bench/${B.id}">live</a> · <a target=_blank href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${B.lat},${B.lng}">google</a> · <a target=_blank href="https://maps.apple.com/?ll=${B.lat},${B.lng}&z=19">apple</a>`;
 $("hero").innerHTML=B.hero?`<img src="${esc(B.hero)}">`:"<p>none</p>";
 $("views").innerHTML=B.views.map(v=>`<img title="${esc(v.source)} ${esc(v.when)}" src="${esc(v.src)}">`).join("")||"<p>none</p>";
 layer.clearLayers();map.setView([B.lat,B.lng],19);
 L.circleMarker([B.lat,B.lng],{radius:7,color:"#000",weight:2,fillColor:"#e8b04a",fillOpacity:1}).addTo(layer);
 if(B.facing!=null)L.polyline([[B.lat,B.lng],dest(B.lat,B.lng,B.facing,8)],{color:"#000",weight:3}).addTo(layer);
 P.forEach((p,k)=>{p.m=L.circleMarker([p.lat,p.lng],{radius:5,color:p.have?"#e8b04a":"#222",weight:p.have?2:1,fillColor:COL[p.source]||"#888",fillOpacity:.95}).addTo(layer).on("click",()=>pick(k));p.m.bindTooltip(`${p.source} ${p.date} · ${p.dist} m`)});
 $("list").innerHTML=P.map((p,k)=>`<div data-k=${k}><i style="background:${COL[p.source]}"></i><span>${p.source}</span><span>${esc(p.date)} · ${p.dist} m${p.side?" · "+p.side:""}</span><span class=have>${p.have?"have":""}${p.score!=null?" ★":""}</span></div>`).join("");
 $("list").querySelectorAll("div").forEach(d=>d.onclick=()=>pick(+d.dataset.k));
 if(P.length)pick(0);else $("info").textContent="No panoramas within "+$("rad").value+" m."}
function pick(k){cur=k;const p=P[k];aim=p.bearing;fov=p.fov;tilt=0;
 $("list").querySelectorAll("div").forEach(d=>d.classList.toggle("on",+d.dataset.k===k));
 $("list").querySelector(`[data-k="${k}"]`)?.scrollIntoView({block:"nearest"});
 render(p.source==="apple"?"stitching the Apple panorama (about 20 s the first time)…":"loading panorama…")}
function busy(t){$("busy").style.display=t?"block":"none";$("busy").textContent=t||""}
let timer=null;
function render(msg){const p=P[cur];if(!p)return;aim=(aim+360)%360;
 $("info").innerHTML=`<b>${p.source}</b> ${esc(p.date)} · ${p.dist} m${p.side?" · "+p.side:""}${p.have?" · already has a view from here":""} · aim <b>${aim.toFixed(0)}°</b> · fov <b>${fov.toFixed(0)}°</b> · tilt <b>${tilt.toFixed(0)}°</b>`;
 if(cone)layer.removeLayer(cone);
 const far=Math.max(p.dist*1.4,12);cone=L.polygon([[p.lat,p.lng],dest(p.lat,p.lng,aim-fov/2,far),dest(p.lat,p.lng,aim+fov/2,far)],{color:COL[p.source],weight:1,fillOpacity:.2}).addTo(layer);
 clearTimeout(timer);timer=setTimeout(()=>{const n=++seq;busy(msg||"rendering…");$("save").disabled=true;
  const img=new Image();img.onload=()=>{if(n===seq){$("view").src=img.src;busy(null);$("save").disabled=false}};
  img.onerror=()=>{if(n===seq)busy("render failed")};
  img.src=`/explore/view?id=${B.id}&key=${encodeURIComponent(p.key)}&aim=${aim.toFixed(1)}&fov=${fov.toFixed(1)}&tilt=${tilt.toFixed(1)}`},msg?0:120)}
function toast(t){const e=$("toast");e.textContent=t;e.style.opacity=1;setTimeout(()=>e.style.opacity=0,1200)}
async function save(){const p=P[cur];if(!p||$("save").disabled)return;$("save").disabled=true;busy("saving (fetching full resolution)…");
 const r=await fetch("/explore/save",{method:"POST",body:JSON.stringify({id:B.id,key:p.key,aim,fov,tilt})});busy(null);
 if(!r.ok){toast("save failed: "+await r.text());$("save").disabled=false;return}
 const j=await r.json();toast("hero set ✓ (image "+j.image_id+") — publishes next run");p.have=true;$("save").disabled=false;
 $("hero").innerHTML=`<img src="${esc($("view").src)}"><p>picked here, not published yet</p>`}
$("save").onclick=save;
// Drag the photo to pan and tilt.
let drag=null;$("view").onmousedown=e=>{e.preventDefault();drag={x:e.clientX,y:e.clientY,aim,tilt}};
onmouseup=()=>drag=null;onmousemove=e=>{if(!drag)return;const w=$("view").clientWidth,dpp=fov/w;
 aim=drag.aim-(e.clientX-drag.x)*dpp;tilt=Math.max(-40,Math.min(40,drag.tilt-(e.clientY-drag.y)*dpp));render()};
$("vwrap").onwheel=e=>{e.preventDefault();fov=Math.max(8,Math.min(100,fov*(e.deltaY>0?1.08:1/1.08)));render()};
document.onkeydown=e=>{if(e.target.tagName==="INPUT"||e.metaKey||e.ctrlKey||e.altKey)return;const k=e.key,s=e.shiftKey?5:1;
 if(k==="ArrowLeft")aim-=2*s;else if(k==="ArrowRight")aim+=2*s;
 else if(k==="ArrowUp")tilt=Math.max(-40,tilt-2*s);else if(k==="ArrowDown")tilt=Math.min(40,tilt+2*s);
 else if(k==="-"||k==="_")fov=Math.min(100,fov*1.15);else if(k==="="||k==="+")fov=Math.max(8,fov/1.15);
 else if(k==="r"&&P[cur]){aim=P[cur].bearing;fov=P[cur].fov;tilt=0}
 else if(k==="j"&&P.length){pick((cur+1)%P.length);e.preventDefault();return}
 else if(k==="k"&&P.length){pick((cur-1+P.length)%P.length);e.preventDefault();return}
 else if(k==="Enter"){save();e.preventDefault();return}
 else return;e.preventDefault();render()};
load();
</script>"""
