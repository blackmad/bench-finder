"""stdlib HTTP server + CLI for the labeling tool.

uv run python -m bench_finder.labeling --db data/benches.db --images-root images/ --port 8877
uv run python -m bench_finder.labeling --db data/benches.db --export gold.jsonl
"""

from __future__ import annotations

import argparse
import contextlib
import json
import mimetypes
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from bench_finder.labeling import store


INDEX_HTML = Path(__file__).with_name("index.html")


class LabelingApp:
    def __init__(self, db_path: str, images_root: Path):
        self.conn = store.connect(db_path)
        self.images_root = images_root
        self.lock = threading.Lock()

    def handle(self, method: str, path: str, body: bytes) -> tuple[int, str, bytes]:
        """Dispatch a request; returns ``(status, content_type, payload)``."""
        try:
            return self._dispatch(method, path.split("?", 1)[0], body)
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        except sqlite3.Error as e:
            return self._json({"error": f"database error: {e}"}, 500)

    @staticmethod
    def _json(obj: Any, status: int = 200) -> tuple[int, str, bytes]:
        return status, "application/json", json.dumps(obj).encode()

    def _dispatch(self, method: str, path: str, body: bytes) -> tuple[int, str, bytes]:
        with self.lock:
            if method == "GET" and path == "/":
                return 200, "text/html; charset=utf-8", INDEX_HTML.read_bytes()
            if method == "GET" and path == "/api/queue":
                return self._json(store.build_queue(self.conn))
            if m := re.fullmatch(r"/api/bench/(\d+)", path):
                bench = (
                    store.get_bench(self.conn, int(m[1])) if method == "GET" else None
                )
                return (
                    self._json(bench)
                    if bench
                    else self._json({"error": "not found"}, 404)
                )
            if method == "GET" and (m := re.fullmatch(r"/api/image/(\d+)", path)):
                img = store.image_path(self.conn, int(m[1]), self.images_root)
                if img is None:
                    return self._json({"error": "image file not found"}, 404)
                ctype = mimetypes.guess_type(img.name)[0] or "application/octet-stream"
                return 200, ctype, img.read_bytes()
            if method == "POST" and path == "/api/label":
                data = json.loads(body or b"{}")
                n = store.save_labels(
                    self.conn, int(data["image_id"]), data.get("labels", {})
                )
                return self._json({"ok": True, "written": n})
        return self._json({"error": "not found"}, 404)


def make_server(
    app: LabelingApp, port: int, host: str = "127.0.0.1"
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _run(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            try:
                status, ctype, payload = app.handle(method, self.path, body)
            except (KeyError, TypeError, json.JSONDecodeError) as e:
                status, ctype, payload = app._json({"error": f"bad request: {e}"}, 400)
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header(
                "Cache-Control", "no-store" if ctype != "image/jpeg" else "max-age=3600"
            )
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            self._run("GET")

        def do_POST(self) -> None:
            self._run("POST")

        def log_message(self, fmt: str, *args: Any) -> None:
            pass

    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="bench_finder.labeling", description=__doc__)
    p.add_argument("--db", default="data/benches.db")
    p.add_argument("--images-root", default="images/")
    p.add_argument("--port", type=int, default=8877)
    p.add_argument(
        "--export", metavar="FILE", help="dump all human labels to JSONL and exit"
    )
    args = p.parse_args(argv)

    if args.export:
        conn = store.connect(args.db)
        print(
            f"wrote {store.export_gold(conn, args.export)} labeled images to {args.export}"
        )
        return

    app = LabelingApp(args.db, Path(args.images_root))
    server = make_server(app, args.port)
    print(f"Labeling {args.db} -> http://127.0.0.1:{args.port}/  (Ctrl-C to stop)")
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
