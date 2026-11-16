"""Local progress page for the long chains (``data/gaps.sh`` and friends).

    uv run python -m bench_finder.dashboard [--log data/gaps.log] [--port 8899]
    open http://localhost:8899

Each refresh reads the chain log for the steps (``== name date`` headers), counts
the running step's progress straight from the database and image folders (the
log only keeps a tail), and turns the last ~15 minutes of samples into a rate
and an estimated finish. Read-only; it never touches the jobs.
"""

from __future__ import annotations

import argparse
import html
import re
import sqlite3
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DB = "data/benches.db"
IMAGES = Path("images")
HEADER = re.compile(r"^== (.+?) (\w{3} \w{3} +\d+ [\d:]+ \w+ \d{4})$")
WINDOW_S = 15 * 60


def _q(sql: str, *args) -> int:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    try:
        return int(conn.execute(sql, args).fetchone()[0] or 0)
    finally:
        conn.close()


def _files(pattern: str, sub: str = "") -> int:
    d = IMAGES / sub if sub else IMAGES
    return sum(1 for _ in d.glob(pattern)) if d.exists() else 0


SAM3_TODO = """SELECT COUNT(*) FROM images i WHERE i.kind='aimed' AND i.capture_success=1
  AND i.filepath IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detections d
  WHERE d.image_id=i.id AND d.model_id='sam3')"""
OCC_TODO = """SELECT COUNT(DISTINCT i.id) FROM images i
  JOIN detections d ON d.image_id=i.id AND d.model_id='sam3' AND d.detection_success=1
  JOIN detection_items di ON di.detection_id=d.id AND di.is_target=1 AND di.confidence>=0.6
  WHERE i.kind='aimed' AND NOT EXISTS (SELECT 1 FROM image_annotations a
  WHERE a.image_id=i.id AND a.label_type='occluded')"""


def counter(step: str) -> tuple[int, int | None] | None:
    """(done, total or None) for a step, by the start of its name."""
    s = step.lower()
    if s.startswith("vantage"):
        f = Path("data/vantage_done.txt")
        done = len(f.read_text().split()) if f.exists() else 0
        return done, _q("SELECT COUNT(*) FROM bench_candidates")
    if s.startswith("wide"):
        return _files("aimed_*_amsterdam_wide.jpg"), None
    if s.startswith("sam3"):
        done = _q("SELECT COUNT(*) FROM detections WHERE model_id='sam3'")
        return done, done + _q(SAM3_TODO)
    if s.startswith("recentre"):
        return _files("*.jpg", "centred"), None
    if s.startswith("local occlusion"):
        done = _q(
            "SELECT COUNT(*) FROM image_annotations WHERE annotator LIKE 'ollama/%' AND label_type='occluded'"
        )
        return done, done + _q(OCC_TODO)
    if s.startswith("hero masks"):
        try:
            done = _q("SELECT COUNT(*) FROM hero_masks")
        except sqlite3.OperationalError:
            done = 0
        return done, _files("*.jpg", "centred") or None
    if s.startswith("fade"):
        try:
            total = _q("SELECT COUNT(*) FROM hero_masks")
        except sqlite3.OperationalError:
            total = None
        return _files("*.jpg", "faded"), total
    if s.startswith("fetch images"):
        total = _q("SELECT COUNT(*) FROM bench_candidates WHERE source='BGT'")
        pending = _q(
            "SELECT COUNT(*) FROM bench_candidates WHERE source='BGT' AND status='PENDING'"
        )
        return total - pending, total
    return None


samples: dict[str, deque] = {}


def rate_per_s(step: str, done: int) -> float | None:
    q = samples.setdefault(step, deque())
    now = time.time()
    q.append((now, done))
    while q and now - q[0][0] > WINDOW_S:
        q.popleft()
    if len(q) < 2 or q[-1][0] - q[0][0] < 30:
        return None
    r = (q[-1][1] - q[0][1]) / (q[-1][0] - q[0][0])
    return r if r > 0 else None


def parse_log(log: Path) -> tuple[list[tuple[str, datetime, list[str]]], bool]:
    steps: list[tuple[str, datetime, list[str]]] = []
    if not log.exists():
        return steps, False
    for line in log.read_text(errors="replace").splitlines():
        m = HEADER.match(line)
        if m:
            when = datetime.strptime(re.sub(" +", " ", m[2]), "%a %b %d %H:%M:%S %Z %Y")
            steps.append((m[1], when, []))
        elif steps:
            steps[-1][2].append(line)
    finished = bool(steps) and steps[-1][0].startswith("done")
    return steps, finished


STEP = re.compile(r'echo "== (.+?) \$\(date\)"')
FUNC = re.compile(r"^(\w+)\(\) *\{")


def plan(script: Path) -> list[str]:
    """Step names in the order the chain script runs them, functions expanded."""
    if not script.exists():
        return []
    funcs: dict[str, list[str]] = {}
    main: list[str] = []
    cur: list[str] | None = None
    for line in script.read_text().splitlines():
        m = FUNC.match(line.strip())
        if m:
            cur = funcs.setdefault(m[1], [])
            continue
        if cur is not None and line.strip() == "}":
            cur = None
            continue
        target = cur if cur is not None else main
        step = STEP.search(line)
        if step:
            target.append(step[1])
        elif cur is None and line.strip() in funcs:
            target.append("@" + line.strip())
    out: list[str] = []
    for item in main:
        out.extend(funcs[item[1:]] if item.startswith("@") else [item])
    return [s for s in out if s != "done"]


def fmt_dur(s: float) -> str:
    s = int(s)
    return (
        f"{s // 3600}h {s % 3600 // 60:02d}m"
        if s >= 3600
        else f"{s // 60}m {s % 60:02d}s"
    )


def page(log: Path, script: Path) -> str:
    e = html.escape
    steps, finished = parse_log(log)
    planned = plan(script)
    now = datetime.now()
    rows, card = [], ""
    for k, (name, start, out) in enumerate(steps):
        end = steps[k + 1][1] if k + 1 < len(steps) else None
        running = end is None and not finished
        dur = fmt_dur(((end or now) - start).total_seconds())
        last = e(out[-1][:140]) if out else ""
        rows.append(
            f"<tr class={'run' if running else ''}><td>{e(name)}</td>"
            f"<td>{start:%H:%M}</td><td>{dur}{' …' if running else ''}</td><td><small>{last}</small></td></tr>"
        )
        if running:
            c = None
            try:
                c = counter(name)
            except sqlite3.OperationalError as err:
                card = f"<p>database busy ({e(str(err))}); retrying next refresh</p>"
            if c:
                done, total = c
                r = rate_per_s(name, done)
                bits = [f"<b>{done:,}</b>" + (f" of {total:,}" if total else "")]
                if r:
                    bits.append(f"{r * 60:,.1f}/min")
                if r and total and total > done:
                    eta = time.time() + (total - done) / r
                    bits.append(
                        f"finishes ≈ <b>{datetime.fromtimestamp(eta):%H:%M}</b> (in {fmt_dur((total - done) / r)})"
                    )
                elif not r:
                    bits.append("measuring rate…")
                pct = f"{100 * done / total:.1f}" if total else "0"
                card = (
                    f"<h2>{e(name)}</h2><div class=bar><i style='width:{pct}%'></i></div>"
                    f"<p>{' · '.join(bits)}</p>"
                )
            elif not card:
                card = f"<h2>{e(name)}</h2><p>running for {dur}; no counter for this step</p>"
    upcoming = [] if finished else planned[len(steps) :]
    rows += [
        f"<tr class=todo><td>{e(n.split(' $')[0])}</td><td></td><td>to do</td><td></td></tr>"
        for n in upcoming
    ]
    if planned and not finished:
        card += f"<p><small>step {len(steps)} of {len(planned)}</small></p>"
    tail = "\n".join(steps[-1][2][-6:]) if steps else ""
    status = "finished" if finished else ("running" if steps else "not started")
    return (
        "<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=20>"
        "<title>Bench jobs</title><style>body{font:14px system-ui;margin:20px;background:#f7f0e1;color:#2b261e;max-width:980px}"
        "table{border-collapse:collapse;width:100%}td{padding:4px 8px;border-bottom:1px solid #ddd2bd;vertical-align:top}"
        "tr.run{background:#fffdf8;font-weight:600}tr.todo{color:#9a8f7c}.bar{height:10px;background:#ddd2bd;border-radius:5px;overflow:hidden}"
        ".bar i{display:block;height:100%;background:#4f8a5b}pre{background:#fffdf8;padding:8px;white-space:pre-wrap;font-size:12px}"
        "small{color:#675d4d;font-weight:400}</style>"
        f"<h1>{e(log.name)} · {status}</h1><p><small>refreshes every 20 s · {now:%H:%M:%S}</small></p>"
        f"{card}<table>{''.join(rows)}</table><h3>Log tail</h3><pre>{e(tail)}</pre>"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--log", type=Path, default=Path("data/gaps.log"))
    ap.add_argument(
        "--script", type=Path, help="the chain script (default: the log's .sh)"
    )
    ap.add_argument("--port", type=int, default=8899)
    a = ap.parse_args()

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = page(a.log, a.script or a.log.with_suffix(".sh")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:
            pass

    print(f"http://localhost:{a.port}")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
