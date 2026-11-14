"""Local detector bake-off for the target-bench-present question (task 2.7).

Each detector answers: is the TARGET bench present? Aimed views point at the bench,
so the target is the detection nearest the image centre. A detection is a *hit* if
its box contains the image centre or its box centre lies within ``radius`` x image
width of the image centre. An image's score is the highest confidence among hits
(0 if none); the image is predicted "present" when score >= threshold.

Detections are cached per model and image as JSON (at a low confidence floor), so
re-scoring with new gold labels, radii or thresholds needs no inference:

    uv run --group detect-extra python -m bench_finder.bakeoff.detectors \\
        --gold oracle --db /path/to/benches.db --images-root /path/to/repo \\
        --models yolo11n-seg,yolo11x-seg,yoloe,yolo-world,gdino,owlv2,sam3 \\
        --out results.json

Models that are not in the cache are run; pass ``--score-only`` to never run models.
The DB is opened read-only.
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import json
import logging
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

DEFAULT_ANNOTATOR = "oracle:claude-opus-5-5"
CONF_FLOOR = 0.05  # cached detections keep everything at or above this
COCO_BENCH = 13
DEFAULT_RADII = (0.15, 0.30)
FIXED_THRESHOLD = 0.25


# --------------------------------------------------------------------------- scoring


@dataclass(frozen=True)
class Det:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float


HIT_MODES = ("radial", "horizontal")


def is_hit(
    det: Det, width: int, height: int, radius: float, mode: str = "radial"
) -> bool:
    """True if ``det`` is the aimed-at target.

    ``radial``: box contains the image centre, or its centre is within ``radius`` x
    image width of the image centre.
    ``horizontal``: the same test on x only (box spans the centre column, or its
    centre x is within ``radius`` x width). Aimed views fix the heading, not the
    height: benches sit on the ground, typically ~0.17 x width below the centre.
    """
    cx, cy = width / 2.0, height / 2.0
    bx, by = (det.x1 + det.x2) / 2.0, (det.y1 + det.y2) / 2.0
    if mode == "horizontal":
        return det.x1 <= cx <= det.x2 or abs(bx - cx) <= radius * width
    if det.x1 <= cx <= det.x2 and det.y1 <= cy <= det.y2:
        return True
    return ((bx - cx) ** 2 + (by - cy) ** 2) ** 0.5 <= radius * width


def target_score(
    dets: list[Det], width: int, height: int, radius: float, mode: str = "radial"
) -> float:
    """Highest confidence among hits, 0.0 if no detection is a hit."""
    return max(
        (d.conf for d in dets if is_hit(d, width, height, radius, mode)), default=0.0
    )


def prf(scores: list[float], gold: list[bool], threshold: float) -> dict[str, float]:
    tp = sum(1 for s, g in zip(scores, gold, strict=True) if s >= threshold and g)
    fp = sum(1 for s, g in zip(scores, gold, strict=True) if s >= threshold and not g)
    fn = sum(1 for s, g in zip(scores, gold, strict=True) if s < threshold and g)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {
        "threshold": threshold,
        "precision": p,
        "recall": r,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def best_threshold(scores: list[float], gold: list[bool]) -> dict[str, float]:
    """Sweep every observed positive score as a threshold; return the max-F1 one."""
    candidates = sorted({s for s in scores if s > 0}) or [1.0]
    best = None
    for t in candidates:
        m = prf(scores, gold, t)
        if best is None or m["f1"] > best["f1"]:
            best = m
    return best  # type: ignore[return-value]


# ----------------------------------------------------------------------------- gold


def connect_ro(db: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(db).resolve()}?mode=ro", uri=True)


def _yes_no(v: Any) -> bool | None:
    if isinstance(v, str):
        with contextlib.suppress(json.JSONDecodeError):
            v = json.loads(v)
    if isinstance(v, bool):
        return v
    if v in ("yes", "no"):
        return v == "yes"
    return None


def load_gold(source: str, db: str, annotator: str) -> dict[int, bool]:
    """``oracle`` reads image_annotations (latest bench_present per image for
    ``annotator``); anything else is a glob of JSONL files with lines
    {"image_id": .., "labels": {"bench_present": "yes"|"no", ...}}."""
    gold: dict[int, bool] = {}
    if source == "oracle":
        with connect_ro(db) as conn:
            rows = conn.execute(
                "SELECT image_id, value FROM image_annotations "
                "WHERE annotator = ? AND label_type = 'bench_present' ORDER BY id",
                (annotator,),
            ).fetchall()
        for image_id, value in rows:
            yn = _yes_no(value)
            if yn is not None:
                gold[int(image_id)] = yn
        return gold
    for path in sorted(glob.glob(source)):
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            yn = _yes_no(rec.get("labels", {}).get("bench_present"))
            if yn is not None:
                gold[int(rec["image_id"])] = yn
    return gold


def collect_image_ids(pattern: str) -> set[int]:
    """Every ``image_id`` value found anywhere in the JSON / JSONL files."""
    found: set[int] = set()

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            if "image_id" in o:
                found.add(int(o["image_id"]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for path in sorted(glob.glob(pattern)):
        text = Path(path).read_text()
        try:
            walk(json.loads(text))
        except json.JSONDecodeError:
            for line in text.splitlines():
                if line.strip():
                    walk(json.loads(line))
    return found


def image_paths(db: str, ids: set[int], images_root: str) -> dict[int, Path]:
    out: dict[int, Path] = {}
    root = Path(images_root)
    with connect_ro(db) as conn:
        for image_id, filepath in conn.execute("SELECT id, filepath FROM images"):
            if image_id in ids and filepath:
                p = Path(filepath)
                out[image_id] = p if p.is_absolute() else root / p
    return out


# ------------------------------------------------------------------------ detectors


def pick_device() -> str:
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


class Detector:
    name = ""

    def load(self, weights_dir: Path, device: str) -> None:
        raise NotImplementedError

    def detect(self, path: Path) -> list[Det]:
        raise NotImplementedError


class UltralyticsDetector(Detector):
    def __init__(self, name: str, weights: str, kind: str = "yolo") -> None:
        self.name, self.weights, self.kind = name, weights, kind

    def load(self, weights_dir: Path, device: str) -> None:
        import ultralytics

        weights_dir.mkdir(parents=True, exist_ok=True)
        self.device = device
        # Ultralytics resolves and downloads weights (and the YOLOE / YOLO-World
        # text encoders) relative to the CWD, so load from inside weights_dir.
        with contextlib.chdir(weights_dir):
            if self.kind == "yoloe":
                self.model = ultralytics.YOLOE(self.weights)
                pe = self.model.get_text_pe(["bench"])
                self.model.set_classes(["bench"], pe)
                self.classes = None
            elif self.kind == "world":
                self.model = ultralytics.YOLOWorld(self.weights)
                self.model.set_classes(["bench"])
                self.classes = None
            else:
                self.model = ultralytics.YOLO(self.weights)
                self.classes = [COCO_BENCH]

    def detect(self, path: Path) -> list[Det]:
        r = self.model.predict(
            str(path),
            conf=CONF_FLOOR,
            classes=self.classes,
            device=self.device,
            verbose=False,
        )[0]
        boxes = r.boxes
        return [
            Det(*map(float, xyxy), conf=float(c))
            for xyxy, c in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), strict=True)
        ]


class HFDetector(Detector):
    """Grounding DINO / OWLv2 via transformers (``uv sync --group detect-extra``)."""

    def __init__(self, name: str, repo: str, kind: str) -> None:
        self.name, self.repo, self.kind = name, repo, kind

    def load(self, weights_dir: Path, device: str) -> None:
        import torch
        from transformers import (
            AutoModelForZeroShotObjectDetection,
            AutoProcessor,
        )

        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(self.repo)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(self.repo)
        self.device = device
        self.model.to(device).eval()

    def detect(self, path: Path) -> list[Det]:
        from PIL import Image

        image = Image.open(path).convert("RGB")
        size = [(image.height, image.width)]
        if self.kind == "gdino":
            inputs = self.processor(images=image, text="a bench.", return_tensors="pt")
        else:
            inputs = self.processor(
                text=[["a photo of a bench"]], images=image, return_tensors="pt"
            )
        inputs = inputs.to(self.device)
        with self.torch.no_grad():
            outputs = self.model(**inputs)
        if self.kind == "gdino":
            res = self.processor.post_process_grounded_object_detection(
                outputs,
                inputs.input_ids,
                threshold=CONF_FLOOR,
                text_threshold=0.0,
                target_sizes=size,
            )[0]
        else:
            # OWLv2 pads to a square; boxes are relative to the padded square.
            side = max(image.height, image.width)
            res = self.processor.post_process_object_detection(
                outputs, threshold=CONF_FLOOR, target_sizes=[(side, side)]
            )[0]
        return [
            Det(*map(float, b), conf=float(s))
            for b, s in zip(res["boxes"].tolist(), res["scores"].tolist(), strict=True)
        ]


class Sam3Detector(Detector):
    """SAM 3 with the text prompt "bench" (Ultralytics ``SAM3SemanticPredictor``).

    The weights are gated on Hugging Face (facebook/sam3); put ``sam3.pt`` in the
    weights dir. Needs Ultralytics' CLIP fork, which ``detect-extra`` installs.
    """

    def __init__(self, name: str, weights: str, imgsz: int = 1008) -> None:
        self.name, self.weights, self.imgsz = name, weights, imgsz

    def load(self, weights_dir: Path, device: str) -> None:
        from ultralytics.models.sam import SAM3SemanticPredictor

        self.predictor = SAM3SemanticPredictor(
            overrides={
                "conf": CONF_FLOOR,
                "task": "segment",
                "mode": "predict",
                "model": str(weights_dir / self.weights),
                "imgsz": self.imgsz,
                "quantize": 16 if device != "cpu" else 32,
                "save": False,
                "verbose": False,
                "device": device,
            }
        )

    def detect(self, path: Path) -> list[Det]:
        self.predictor.set_image(str(path))
        boxes = self.predictor(text=["bench"])[0].boxes
        return [
            Det(*map(float, xyxy), conf=float(c))
            for xyxy, c in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), strict=True)
        ]


MODELS: dict[str, Detector] = {
    "yolo11n-seg": UltralyticsDetector("yolo11n-seg", "yolo11n-seg.pt"),
    "yolo11x-seg": UltralyticsDetector("yolo11x-seg", "yolo11x-seg.pt"),
    "yoloe": UltralyticsDetector("yoloe", "yoloe-11l-seg.pt", kind="yoloe"),
    "yolo-world": UltralyticsDetector("yolo-world", "yolov8x-worldv2.pt", kind="world"),
    "gdino": HFDetector("gdino", "IDEA-Research/grounding-dino-base", kind="gdino"),
    "gdino-tiny": HFDetector(
        "gdino-tiny", "IDEA-Research/grounding-dino-tiny", kind="gdino"
    ),
    "owlv2": HFDetector("owlv2", "google/owlv2-base-patch16-ensemble", kind="owlv2"),
    "sam3": Sam3Detector("sam3", "sam3.pt"),
}


# ---------------------------------------------------------------------------- cache


def cache_file(cache_dir: Path, model: str, image_id: int) -> Path:
    return cache_dir / model / f"{image_id}.json"


def run_model(
    det: Detector,
    paths: dict[int, Path],
    cache_dir: Path,
    weights_dir: Path,
    device: str,
) -> None:
    todo = [i for i in sorted(paths) if not cache_file(cache_dir, det.name, i).exists()]
    if not todo:
        return
    from PIL import Image

    logger.info("%s: loading on %s, %d images to run", det.name, device, len(todo))
    det.load(weights_dir, device)
    (cache_dir / det.name).mkdir(parents=True, exist_ok=True)
    for n, image_id in enumerate(todo, 1):
        path = paths[image_id]
        with Image.open(path) as im:
            w, h = im.size
        t0 = time.perf_counter()
        dets = det.detect(path)
        dt = time.perf_counter() - t0
        rec = {
            "image_id": image_id,
            "width": w,
            "height": h,
            "seconds": dt,
            "device": device,
            "dets": [d.__dict__ for d in dets],
        }
        cache_file(cache_dir, det.name, image_id).write_text(json.dumps(rec))
        if n % 50 == 0 or n == len(todo):
            logger.info("%s: %d/%d (%.2fs last)", det.name, n, len(todo), dt)


def load_cached(cache_dir: Path, model: str, image_id: int) -> dict | None:
    f = cache_file(cache_dir, model, image_id)
    return json.loads(f.read_text()) if f.exists() else None


# ---------------------------------------------------------------------------- score


def score_model(
    cache_dir: Path,
    model: str,
    gold: dict[int, bool],
    radii: tuple[float, ...],
    hit_modes: tuple[str, ...] = ("radial",),
) -> list[dict]:
    recs = {i: load_cached(cache_dir, model, i) for i in gold}
    recs = {i: r for i, r in recs.items() if r is not None}
    if not recs:
        return []
    ids = sorted(recs)
    labels = [gold[i] for i in ids]
    # Drop the slowest call (model warm-up) when timing.
    secs = [r["seconds"] for r in recs.values()]
    mean_s = (sum(secs) - max(secs)) / (len(secs) - 1) if len(secs) > 1 else secs[0]
    rows = []
    for hit_mode, radius in ((h, r) for h in hit_modes for r in radii):
        scores = [
            target_score(
                [Det(**d) for d in recs[i]["dets"]],
                recs[i]["width"],
                recs[i]["height"],
                radius,
                hit_mode,
            )
            for i in ids
        ]
        for mode, m in (
            ("best", best_threshold(scores, labels)),
            ("fixed", prf(scores, labels, FIXED_THRESHOLD)),
        ):
            rows.append(
                {
                    "model": model,
                    "hit_mode": hit_mode,
                    "radius": radius,
                    "mode": mode,
                    **m,
                    "sec_per_image": mean_s,
                    "n": len(ids),
                    "n_positive": sum(labels),
                }
            )
    return rows


def format_table(rows: list[dict]) -> str:
    head = f"{'model':<12} {'hit':<10} {'radius':>6} {'thr':>10} {'P':>5} {'R':>5} {'F1':>5} {'s/img':>6} {'n':>5}"
    lines = [head, "-" * len(head)]
    for r in rows:
        thr = f"{r['mode']}={r['threshold']:.2f}"
        lines.append(
            f"{r['model']:<12} {r['hit_mode']:<10} {r['radius']:>6.2f} {thr:>10} {r['precision']:>5.2f} "
            f"{r['recall']:>5.2f} {r['f1']:>5.2f} {r['sec_per_image']:>6.3f} {r['n']:>5}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--gold",
        default="oracle",
        help="'oracle' (image_annotations) or a glob of answers JSONL",
    )
    ap.add_argument("--annotator", default=DEFAULT_ANNOTATOR)
    ap.add_argument("--db", default="data/benches.db")
    ap.add_argument(
        "--images-root",
        default=".",
        help="directory that relative images.filepath values resolve against",
    )
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument(
        "--extra-images",
        default=None,
        help="glob of JSON/JSONL files; their image_ids are also run "
        "(cached for later scoring) even if not yet labelled",
    )
    ap.add_argument(
        "--limit", type=int, default=None, help="max images to run per model"
    )
    ap.add_argument("--radii", default=",".join(map(str, DEFAULT_RADII)))
    ap.add_argument(
        "--hit-modes",
        default=",".join(HIT_MODES),
        help="comma list of radial,horizontal (see is_hit)",
    )
    ap.add_argument("--cache-dir", default="data/bakeoff_cache")
    ap.add_argument("--weights-dir", default="models")
    ap.add_argument("--device", default=None, help="default: mps if available else cpu")
    ap.add_argument("--score-only", action="store_true", help="never run models")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in MODELS]
    if unknown:
        ap.error(f"unknown models {unknown}; choose from {list(MODELS)}")
    radii = tuple(float(r) for r in args.radii.split(","))
    hit_modes = tuple(h.strip() for h in args.hit_modes.split(",") if h.strip())
    if set(hit_modes) - set(HIT_MODES):
        ap.error(f"--hit-modes must be from {HIT_MODES}")
    cache_dir = Path(args.cache_dir)
    weights_dir = Path(args.weights_dir).resolve()

    gold = load_gold(args.gold, args.db, args.annotator)
    logger.info("gold: %d images (%d positive)", len(gold), sum(gold.values()))

    if not args.score_only:
        run_ids = set(gold)
        if args.extra_images:
            run_ids |= collect_image_ids(args.extra_images)
        paths = image_paths(args.db, run_ids, args.images_root)
        paths = {i: p for i, p in paths.items() if p.exists()}
        if args.limit:  # labelled images first
            order = sorted(paths, key=lambda i: (i not in gold, i))[: args.limit]
            paths = {i: paths[i] for i in order}
        device = args.device or pick_device()
        for m in models:
            try:
                run_model(MODELS[m], paths, cache_dir, weights_dir, device)
            except Exception:
                logger.exception("%s failed; skipping", m)

    rows = [
        r for m in models for r in score_model(cache_dir, m, gold, radii, hit_modes)
    ]
    print(format_table(rows))
    if args.out:
        Path(args.out).write_text(
            json.dumps(
                {
                    "gold_source": args.gold,
                    "n_gold": len(gold),
                    "n_gold_positive": sum(gold.values()),
                    "radii": radii,
                    "hit_modes": hit_modes,
                    "fixed_threshold": FIXED_THRESHOLD,
                    "rows": rows,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
