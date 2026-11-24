"""Pick each bench's hero by showing a model all its candidate photos at once.

Today's hero is the top of a per-photo ranking (detector confidence, where the
camera stands, occlusion, framing). Each photo is judged alone, so a frame with
the bench sure and centred can still lead with a parking sign in front of it.
Here the model sees the candidates side by side (re-centred, but all unfaded:
the hero's fade would make it look washed out next to the others) and names the one that best invites someone to go and sit there.

    uv run python -m bench_finder.hero_pick pilot [--n 50] [--seed 3] [--max-usd 0.5]
    open data/hero_pick/index.html     # current hero vs the pick, mark which is better
    uv run python -m bench_finder.hero_pick agree   # vs the owner's picks from review
    uv run python -m bench_finder.hero_pick all     # every bench -> data/hero_pick/picks.json
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from bench_finder.clients.view_classifier import PRICES, prepare_image
from bench_finder.publish.exclude import FEEDBACK


MODEL = "claude-haiku-5-5"
OUT = Path("data/hero_pick")
MAX_CANDIDATES = 6
SIDE = 768  # px per photo sent; enough to judge a scene

PROMPT = """These are street-level photos of the same public bench, numbered 1 to {n}.
One of them will lead the bench's card on a map of benches: the photo people use
to decide whether to walk there and sit down.

Pick the best lead photo. Prefer, in order:
1. The bench is clearly visible and recognisable, not hidden behind cars, signs,
   bins, poles, hedges or people, and not cut off at the edge.
2. It shows the setting: what you would see or feel sitting there (water, trees,
   a square), not mostly road or parked cars.
3. It is a pleasant, well-lit, level photo.

Answer with the choose tool."""

TOOL = {
    "name": "choose",
    "description": "The best lead photo for this bench.",
    "input_schema": {
        "type": "object",
        "properties": {
            "best": {"type": "integer", "description": "The photo number"},
            "why": {"type": "string", "description": "One short sentence"},
            "lead_ok": {
                "type": "boolean",
                "description": "True if the best photo is good enough to lead the card",
            },
        },
        "required": ["best", "why", "lead_ok"],
    },
}


def candidates(n: int, seed: int, images_root: Path = Path("images")) -> list[dict]:
    """``n`` random benches with at least three candidate photos and a current hero."""
    from bench_finder.publish.build import _resolve, select_images
    from bench_finder.publish.images import render_source
    from bench_finder.recut import connect_ro

    _, _, chosen = select_images(
        connect_ro("data/benches.db"), images_root, True, gallery_size=MAX_CANDIDATES
    )
    pool = [
        {
            "bench": bid,
            "images": [
                {
                    "id": i["id"],
                    "src": str(render_source(_resolve(i, images_root), faded=False)),
                }
                for i in imgs
            ],
        }
        for bid, (imgs, has_hero) in sorted(chosen.items())
        if has_hero and len(imgs) >= 3
    ]
    random.Random(seed).shuffle(pool)
    return pool[:n]


class Picker:
    """Claude Haiku (the Gemini account's prepaid credits ran out; Haiku costs less)."""

    def __init__(self, max_usd: float):
        import anthropic

        if os.environ.get("OPENROUTER_API_KEY"):  # the direct account is out of credit
            self.model = "anthropic/claude-haiku-5.5"
            self.client = anthropic.Anthropic(
                api_key=None,
                auth_token=os.environ["OPENROUTER_API_KEY"],
                base_url="https://openrouter.ai/api",
            )
        else:
            self.model = MODEL
            self.client = anthropic.Anthropic()
        self.max_usd = max_usd
        self.usd = 0.0
        self.lock = threading.Lock()

    def pick(self, bench: dict) -> dict:
        with self.lock:
            if self.usd >= self.max_usd:
                return {"bench": bench["bench"], "skipped": "budget"}
        # Shown in a shuffled order so the current hero is not always "Photo 1".
        order = list(range(len(bench["images"])))
        random.Random(bench["bench"]).shuffle(order)
        content: list[dict] = []
        for k, idx in enumerate(order, 1):
            data, mime, _ = prepare_image(bench["images"][idx]["src"], max_side=SIDE)
            content += [
                {"type": "text", "text": f"Photo {k}:"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": base64.b64encode(data).decode(),
                    },
                },
            ]
        content.append({"type": "text", "text": PROMPT.format(n=len(order))})
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": TOOL["name"]},
            messages=[{"role": "user", "content": content}],
        )
        pin, pout = PRICES[MODEL]  # OpenRouter passes Anthropic's prices through
        usd = (msg.usage.input_tokens * pin + msg.usage.output_tokens * pout) / 1e6
        with self.lock:
            self.usd += usd
        ans = next(b.input for b in msg.content if b.type == "tool_use")
        best = order[min(max(int(ans["best"]), 1), len(order)) - 1]
        return {
            **bench,
            "pick": best,
            "why": ans["why"],
            "lead_ok": bool(ans["lead_ok"]),
            "usd": round(usd, 5),
        }


def pilot(n: int, seed: int, max_usd: float, workers: int = 8) -> dict:
    benches = candidates(n, seed)
    picker = Picker(max_usd)
    results = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(picker.pick, b): b for b in benches}
        for f in as_completed(futs):
            try:
                results.append(f.result())
            except Exception as e:  # one bad call should not lose the rest
                results.append({"bench": futs[f]["bench"], "error": str(e)[:200]})
    results.sort(key=lambda r: r.get("bench", 0))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pilot.json").write_text(json.dumps(results, indent=1))
    done = [r for r in results if "pick" in r]
    page(done)
    return {
        "benches": len(benches),
        "picked": len(done),
        "changed": sum(r["pick"] != 0 for r in done),
        "not_good_enough": sum(not r["lead_ok"] for r in done),
        "errors": sum("error" in r for r in results),
        "usd": round(picker.usd, 4),
        "page": str(OUT / "index.html"),
    }


def owner_picks() -> dict[int, int]:
    """{bench id: image id} the owner chose as hero in the review page."""
    out: dict[int, int] = {}
    for f in sorted(FEEDBACK.glob("*.json")):
        out |= {
            int(b): int(i)
            for b, i in json.loads(f.read_text()).get("hero_pick", {}).items()
        }
    return out


def agree(max_usd: float, workers: int = 8) -> dict:
    """How often the model picks the photo the owner picked, from the same gallery."""
    from bench_finder.publish.build import _resolve, select_images
    from bench_finder.publish.images import render_source
    from bench_finder.recut import connect_ro

    picks = owner_picks()
    _, _, chosen = select_images(
        connect_ro("data/benches.db"), Path("images"), True, gallery_size=MAX_CANDIDATES
    )
    benches = []
    for bid, want in sorted(picks.items()):
        imgs = (chosen.get(bid) or ([], False))[0]
        if len(imgs) < 2 or want not in {i["id"] for i in imgs}:
            continue
        benches.append(
            {
                "bench": bid,
                "want": want,
                "images": [
                    {
                        "id": i["id"],
                        "src": str(
                            render_source(_resolve(i, Path("images")), faded=False)
                        ),
                    }
                    for i in imgs
                ],
            }
        )
    picker = Picker(max_usd)
    results = []
    with ThreadPoolExecutor(workers) as ex:
        for f in as_completed([ex.submit(picker.pick, b) for b in benches]):
            try:
                results.append(f.result())
            except Exception as e:  # one bad call should not lose the rest
                results.append({"error": str(e)[:200]})
    done = [r for r in results if "pick" in r]
    hit = [r for r in done if r["images"][r["pick"]]["id"] == r["want"]]
    chance = sum(1 / len(r["images"]) for r in done)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "agree.json").write_text(json.dumps(results, indent=1))
    return {
        "owner_picks": len(picks),
        "tested": len(done),
        "agrees": len(hit),
        "by_chance": round(chance),
        "errors": len(results) - len(done),
        "usd": round(picker.usd, 4),
    }


def run_all(max_usd: float, workers: int = 8) -> dict:
    """Pick a hero for every bench with a choice; resumable (picks.json)."""
    from bench_finder.publish.build import (
        MODEL_PICKS,
        _resolve,
        select_images,
        target_gate,
    )
    from bench_finder.publish.images import render_source
    from bench_finder.recut import connect_ro

    done = json.loads(MODEL_PICKS.read_text()) if MODEL_PICKS.exists() else {}
    owner = owner_picks()
    _, _, chosen = select_images(
        connect_ro("data/benches.db"), Path("images"), True, gallery_size=MAX_CANDIDATES
    )
    benches = []
    for bid, (imgs, has_hero) in sorted(chosen.items()):
        if not has_hero or bid in owner or str(bid) in done:
            continue
        lead = [i for i in imgs if target_gate(i)[0] < 1.5]  # photos allowed to lead
        if len(lead) < 2:
            continue
        benches.append(
            {
                "bench": bid,
                "images": [
                    {
                        "id": i["id"],
                        "src": str(
                            render_source(_resolve(i, Path("images")), faded=False)
                        ),
                    }
                    for i in lead
                ],
            }
        )
    picker = Picker(max_usd)
    lock = threading.Lock()
    n = errors = 0
    with ThreadPoolExecutor(workers) as ex:
        for f in as_completed([ex.submit(picker.pick, b) for b in benches]):
            try:
                r = f.result()
            except Exception:  # one bad call should not lose the rest
                errors += 1
                continue
            if "pick" not in r:
                continue
            with lock:
                done[str(r["bench"])] = r["images"][r["pick"]]["id"]
                n += 1
                if n % 100 == 0:
                    MODEL_PICKS.write_text(json.dumps(done, indent=0))
                    print(n, "of", len(benches), f"${picker.usd:.2f}", flush=True)
    MODEL_PICKS.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PICKS.write_text(json.dumps(done, indent=0))
    return {
        "todo": len(benches),
        "picked": n,
        "errors": errors,
        "usd": round(picker.usd, 3),
    }


def _thumb(src: str, name: str) -> str:
    from PIL import Image

    (OUT / "img").mkdir(parents=True, exist_ok=True)
    dest = OUT / "img" / name
    if not dest.exists():
        with Image.open(src) as im:
            im.convert("RGB").resize((480, round(480 * im.height / im.width))).save(
                dest, "JPEG", quality=82
            )
    return f"img/{name}"


def page(results: list[dict]) -> None:
    cards = []
    for r in results:
        imgs = [_thumb(i["src"], f"{i['id']}.jpg") for i in r["images"]]
        same = r["pick"] == 0
        strip = "".join(
            f"<img src='{s}' class='{'cur' if k == 0 else ''} {'pick' if k == r['pick'] else ''}'>"
            for k, s in enumerate(imgs)
        )
        verdict = (
            "<p class='same'>Model keeps the current hero.</p>"
            if same
            else f"""<div class='pair'><figure><img src='{imgs[0]}'><figcaption>Current</figcaption></figure>
<figure><img src='{imgs[r["pick"]]}'><figcaption>Model's pick</figcaption></figure></div>
<div class='vote' data-b='{r["bench"]}'><button data-v='pick'>Pick is better</button>
<button data-v='current'>Current is better</button><button data-v='same'>About the same</button></div>"""
        )
        flag = "" if r["lead_ok"] else " <b class='weak'>no photo good enough</b>"
        cards.append(
            f"<section><h2>Bench {r['bench']}{flag}</h2><p class='why'>{html.escape(r['why'])}</p>"
            f"{verdict}<div class='strip'>{strip}</div></section>"
        )
    changed = sum(r["pick"] != 0 for r in results)
    (OUT / "index.html").write_text(
        f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>Hero pick pilot</title><style>
body{{font:15px system-ui;margin:16px;background:#f4efe6;color:#222;max-width:1100px}}
section{{background:#fff;padding:14px;margin:0 0 18px;box-shadow:0 2px 8px #0002}}
h2{{margin:0 0 4px;font-size:17px}} .why{{margin:0 0 10px;color:#555}}
.pair{{display:flex;gap:10px}} .pair figure{{margin:0;flex:1}} .pair img{{width:100%}}
figcaption{{font-size:13px;color:#555}} .strip{{display:flex;gap:6px;margin-top:10px;overflow:auto}}
.strip img{{height:80px;outline:3px solid transparent}} .strip .cur{{outline-color:#888}}
.strip .pick{{outline-color:#d33}} .same{{color:#2a7}} .weak{{color:#c50;font-size:13px}}
.vote{{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap}} .vote button{{padding:6px 10px}}
.vote button.on{{background:#222;color:#fff}} #tally{{position:sticky;top:0;background:#f4efe6;padding:8px 0}}
</style>
<h1>Hero pick pilot</h1>
<p>{len(results)} benches; the model changed the hero on {changed}. Strip: grey = current hero, red = model's pick.
Mark the changed ones; the tally counts your votes.</p><p id=tally></p>
{"".join(cards)}
<p><button id=exp>Copy votes as JSON</button></p>
<script>
const K='heropick';let v={{}};try{{v=JSON.parse(localStorage.getItem(K)||'{{}}')}}catch(e){{}}
function show(){{const c={{pick:0,current:0,same:0}};Object.values(v).forEach(x=>c[x]++);
document.getElementById('tally').textContent=`Votes: pick better ${{c.pick}} · current better ${{c.current}} · same ${{c.same}}`;
document.querySelectorAll('.vote').forEach(d=>d.querySelectorAll('button').forEach(b=>b.classList.toggle('on',v[d.dataset.b]===b.dataset.v)))}}
document.querySelectorAll('.vote button').forEach(b=>b.onclick=()=>{{v[b.parentNode.dataset.b]=b.dataset.v;
try{{localStorage.setItem(K,JSON.stringify(v))}}catch(e){{}}show()}});
document.getElementById('exp').onclick=()=>navigator.clipboard.writeText(JSON.stringify(v));show();
</script>"""
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--seed", type=int, default=3)
    p.add_argument("--max-usd", type=float, default=0.5)
    p = sub.add_parser("agree", help="agreement with the owner's hero picks")
    p.add_argument("--max-usd", type=float, default=0.3)
    p = sub.add_parser("all", help="pick a hero for every bench (resumable)")
    p.add_argument("--max-usd", type=float, default=5.0)
    a = ap.parse_args()
    if a.cmd == "all":
        print(run_all(a.max_usd))
    elif a.cmd == "agree":
        print(agree(a.max_usd))
    else:
        print(pilot(a.n, a.seed, a.max_usd))


if __name__ == "__main__":
    main()
