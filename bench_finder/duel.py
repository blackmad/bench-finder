"""Keyboard page for judging the hero-pick pilot: current hero vs the model's pick.

Served by the review server at /duel. Votes go to data/hero_pick/votes.json;
"the pick is better" (or a number key) also makes that photo the bench's hero,
through the review feedback file, so the next publish uses it.
"""

from __future__ import annotations

import json
from pathlib import Path


PILOT = Path("data/hero_pick/pilot.json")
VOTES = Path("data/hero_pick/votes.json")


def items() -> list[dict]:
    """The pilot benches where the model changed the hero, with any saved vote."""
    votes = json.loads(VOTES.read_text()) if VOTES.exists() else {}
    out = []
    for r in json.loads(PILOT.read_text()) if PILOT.exists() else []:
        if "pick" not in r or r["pick"] == 0:
            continue
        out.append(
            {
                "bench": r["bench"],
                "why": r["why"],
                "lead_ok": r["lead_ok"],
                "pick": r["pick"],
                "images": [{"id": i["id"], "src": "/" + i["src"]} for i in r["images"]],
                "vote": votes.get(str(r["bench"])),
            }
        )
    return out


def save(bench: int, vote: dict | None) -> None:
    votes = json.loads(VOTES.read_text()) if VOTES.exists() else {}
    if vote:
        votes[str(bench)] = vote
    else:
        votes.pop(str(bench), None)
    VOTES.parent.mkdir(parents=True, exist_ok=True)
    VOTES.write_text(json.dumps(votes, indent=0))


PAGE = r"""<!doctype html><meta charset=utf-8><title>Hero duel</title>
<meta name=viewport content="width=device-width">
<style>
*{box-sizing:border-box}
body{margin:0;font:15px system-ui;background:#1c1b19;color:#eee;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#bar{height:5px;background:#333}#fill{height:100%;background:#e8b04a;transition:width .25s}
header{display:flex;gap:16px;align-items:baseline;padding:10px 18px}
header h1{font-size:17px;margin:0}header .n{color:#aaa}header a{color:#9bd}
#why{padding:0 18px 8px;color:#bbb;min-height:1.4em}#why b{color:#f90}
main{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:0 18px;min-height:0}
figure{margin:0;display:flex;flex-direction:column;min-height:0;border-radius:8px;outline:4px solid transparent;transition:outline-color .15s,transform .15s}
figure img{flex:1;min-height:0;width:100%;object-fit:contain;background:#000;border-radius:8px}
figcaption{padding:6px 2px;color:#ccc;display:flex;justify-content:space-between}
kbd{background:#eee;color:#222;border-radius:4px;padding:1px 6px;font:13px ui-monospace,monospace}
figure.win{outline-color:#4caf50;transform:scale(1.01)}figure.lose{opacity:.45}
.strip{display:flex;gap:8px;padding:10px 18px;align-items:flex-end}
.strip div{position:relative}.strip img{height:76px;border-radius:4px;outline:3px solid transparent;display:block}
.strip span{position:absolute;left:4px;top:2px;font:bold 13px ui-monospace,monospace;text-shadow:0 0 3px #000}
.strip .cur img{outline-color:#888}.strip .pick img{outline-color:#e8b04a}.strip .chosen img{outline-color:#4caf50}
footer{padding:6px 18px 12px;color:#aaa;font-size:13px;display:flex;gap:18px;flex-wrap:wrap}
#toast{position:fixed;top:40%;left:50%;transform:translate(-50%,-50%);font-size:34px;font-weight:700;background:#000c;padding:14px 26px;border-radius:12px;opacity:0;transition:opacity .3s;pointer-events:none}
#done{position:fixed;inset:0;background:#1c1b19;display:none;flex-direction:column;align-items:center;justify-content:center;gap:10px;font-size:20px}
</style>
<div id=bar><div id=fill></div></div>
<header><h1>Which photo should lead the card?</h1><span class=n id=n></span><span class=n id=tally></span><a id=live target=_blank>live</a></header>
<div id=why></div>
<main><figure id=L><img><figcaption><span><kbd>←</kbd> current hero</span></figcaption></figure>
<figure id=R><img><figcaption><span>model's pick <kbd>→</kbd></span></figcaption></figure></main>
<div class=strip id=strip></div>
<footer><span><kbd>←</kbd> current better (stays the hero)</span><span><kbd>→</kbd> pick better (becomes the hero)</span>
<span><kbd>↓</kbd> about the same</span><span><kbd>1</kbd>–<kbd>6</kbd> a different photo is best</span>
<span><kbd>x</kbd> no photo shows a bench</span><span><kbd>⌫</kbd> back</span><span><kbd>n</kbd> next unvoted</span></footer>
<div id=toast></div>
<div id=done><div>All done 🎉</div><div id=sum></div><div style="font-size:14px;color:#aaa">Votes are saved. <kbd>⌫</kbd> to go back.</div></div>
<script>
let items=[],i=0,busy=false;const $=id=>document.getElementById(id);
const LABEL={current:"current ✓",pick:"pick ✓",same:"same",other:"photo #",none:"no bench"};
fetch("/duel.json").then(r=>r.json()).then(d=>{items=d;i=Math.max(0,items.findIndex(x=>!x.vote));if(items.every(x=>x.vote))i=items.length;show()});
function tally(){const c={current:0,pick:0,same:0,other:0,none:0};items.forEach(x=>x.vote&&c[x.vote.v]++);return c}
function show(){
  const c=tally(),done=items.filter(x=>x.vote).length;
  $("fill").style.width=(100*done/items.length)+"%";
  $("tally").textContent=`current ${c.current} · pick ${c.pick} · same ${c.same} · other ${c.other} · no bench ${c.none}`;
  if(i>=items.length){$("done").style.display="flex";$("sum").textContent=$("tally").textContent;return}
  $("done").style.display="none";
  const b=items[i];$("n").textContent=`${i+1} / ${items.length} · bench ${b.bench}`;
  $("live").href="https://bench.blackmad.com/?bench="+b.bench;
  $("why").innerHTML=(b.lead_ok?"":"<b>model: no photo good enough · </b>")+"model says: "+b.why.replace(/</g,"&lt;");
  $("L").querySelector("img").src=b.images[0].src;$("R").querySelector("img").src=b.images[b.pick].src;
  const v=b.vote&&b.vote.v;
  $("L").className=v==="current"?"win":v&&v!=="same"?"lose":"";
  $("R").className=v==="pick"?"win":v&&v!=="same"?"lose":"";
  const chosen=v==="pick"?b.pick:v==="current"?0:v==="other"?b.vote.k:-1;
  $("strip").innerHTML=b.images.map((m,k)=>`<div class="${k===0?"cur":""} ${k===b.pick?"pick":""} ${k===chosen?"chosen":""}"><img src="${m.src}"><span>${k+1}</span></div>`).join("");
  // warm the next pair
  const nx=items[i+1];if(nx){new Image().src=nx.images[0].src;new Image().src=nx.images[nx.pick].src}
}
function toast(t){const e=$("toast");e.textContent=t;e.style.opacity=1;setTimeout(()=>e.style.opacity=0,450)}
async function vote(v,k){
  if(busy||i>=items.length)return;busy=true;const b=items[i];
  const hero=v==="current"?b.images[0].id:v==="pick"?b.images[b.pick].id:v==="other"?b.images[k].id:null;
  b.vote={v,k,hero};show();toast(v==="other"?"photo "+(k+1):LABEL[v]);
  await fetch("/duel",{method:"POST",body:JSON.stringify({bench:b.bench,vote:b.vote})});
  setTimeout(()=>{busy=false;i++;show()},260);
}
document.onkeydown=e=>{
  if(e.metaKey||e.ctrlKey||e.altKey)return;const k=e.key;
  if(k==="ArrowLeft")vote("current");else if(k==="ArrowRight")vote("pick");
  else if(k==="ArrowDown"||k==="s")vote("same");else if(k==="x")vote("none");
  else if(/^[1-9]$/.test(k)&&i<items.length&&+k<=items[i].images.length){const n=+k-1;vote(n===0?"current":n===items[i].pick?"pick":"other",n)}
  else if(k==="Backspace"||k==="u"){i=Math.max(0,i-1);show()}
  else if(k==="n"){const j=items.findIndex(x=>!x.vote);i=j<0?items.length:j;show()}
  else return;e.preventDefault()};
</script>"""
