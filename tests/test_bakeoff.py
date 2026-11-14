import json
import sqlite3
import sys
import types
from typing import ClassVar

import pytest
from PIL import Image

from bench_finder.bakeoff.detectors import (
    MODELS,
    Det,
    Sam3Detector,
    best_threshold,
    collect_image_ids,
    is_hit,
    load_gold,
    prf,
    run_model,
    score_model,
    target_score,
)


W, H = 1000, 800


def test_hit_box_contains_centre():
    assert is_hit(Det(400, 300, 600, 500, 0.9), W, H, radius=0.0)


def test_hit_by_radius_only():
    # Box centre at (650, 400): 150 px = 0.15 * width from the image centre.
    d = Det(620, 380, 680, 420, 0.9)
    assert not is_hit(d, W, H, radius=0.10)
    assert is_hit(d, W, H, radius=0.15)


def test_off_centre_detection_is_not_target():
    dets = [Det(0, 0, 100, 100, 0.95), Det(450, 350, 550, 450, 0.4)]
    assert target_score(dets, W, H, 0.15) == 0.4
    assert target_score(dets[:1], W, H, 0.15) == 0.0


def test_prf_and_best_threshold():
    scores = [0.9, 0.6, 0.3, 0.0]
    gold = [True, True, False, True]
    m = prf(scores, gold, 0.25)
    assert (m["tp"], m["fp"], m["fn"]) == (2, 1, 1)
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    best = best_threshold(scores, gold)
    assert best["threshold"] == 0.6
    assert best["f1"] == pytest.approx(0.8)


def test_load_gold_oracle_and_jsonl(tmp_path):
    db = tmp_path / "g.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE image_annotations (id INTEGER PRIMARY KEY, image_id INT, "
        "annotator TEXT, label_type TEXT, value JSON)"
    )
    conn.executemany(
        "INSERT INTO image_annotations (image_id, annotator, label_type, value) VALUES (?,?,?,?)",
        [
            (1, "oracle:x", "bench_present", json.dumps("yes")),
            (2, "oracle:x", "bench_present", json.dumps("no")),
            (2, "oracle:x", "bench_present", json.dumps("yes")),  # latest wins
            (3, "human", "bench_present", json.dumps("no")),
            (4, "oracle:x", "bench_type", json.dumps("backrest")),
        ],
    )
    conn.commit()
    conn.close()
    assert load_gold("oracle", str(db), "oracle:x") == {1: True, 2: True}

    f = tmp_path / "answers-0.jsonl"
    f.write_text(
        '{"image_id": 5, "labels": {"bench_present": "no"}}\n'
        '{"image_id": 6, "labels": {"bench_present": "yes"}}\n'
    )
    assert load_gold(str(tmp_path / "answers-*.jsonl"), str(db), "x") == {
        5: False,
        6: True,
    }
    assert collect_image_ids(str(tmp_path / "answers-*.jsonl")) == {5, 6}


def test_score_model_from_cache(tmp_path):
    (tmp_path / "m").mkdir()
    recs = {
        1: [{"x1": 450, "y1": 350, "x2": 550, "y2": 450, "conf": 0.8}],
        2: [{"x1": 0, "y1": 0, "x2": 50, "y2": 50, "conf": 0.9}],
        3: [],
    }
    for i, dets in recs.items():
        (tmp_path / "m" / f"{i}.json").write_text(
            json.dumps(
                {"image_id": i, "width": W, "height": H, "seconds": 0.1, "dets": dets}
            )
        )
    rows = score_model(tmp_path, "m", {1: True, 2: True, 3: False}, (0.15,))
    fixed = next(r for r in rows if r["mode"] == "fixed")
    assert (fixed["tp"], fixed["fp"], fixed["fn"], fixed["n"]) == (1, 0, 1, 3)


def test_horizontal_mode_ignores_vertical_offset():
    # Bench low in the frame, horizontally centred: not a radial hit, a horizontal one.
    d = Det(450, 650, 550, 750, 0.7)
    assert not is_hit(d, W, H, 0.15, "radial")
    assert is_hit(d, W, H, 0.15, "horizontal")
    assert not is_hit(Det(800, 380, 900, 420, 0.7), W, H, 0.15, "horizontal")


class _FakeBoxes:
    def __init__(self, xyxy, conf):
        self.xyxy = types.SimpleNamespace(tolist=lambda: xyxy)
        self.conf = types.SimpleNamespace(tolist=lambda: conf)


class _FakeSam3Predictor:
    instances: ClassVar[list] = []

    def __init__(self, overrides):
        self.overrides = overrides
        self.images: list[str] = []
        self.texts: list = []
        _FakeSam3Predictor.instances.append(self)

    def set_image(self, path):
        self.images.append(path)

    def __call__(self, text):
        self.texts.append(text)
        boxes = _FakeBoxes(
            [[450.0, 650.0, 550.0, 750.0], [0.0, 0.0, 40.0, 40.0]], [0.9, 0.3]
        )
        return [types.SimpleNamespace(boxes=boxes)]


def test_sam3_detector_with_fake_predictor(tmp_path, monkeypatch):
    sam = types.ModuleType("ultralytics.models.sam")
    sam.SAM3SemanticPredictor = _FakeSam3Predictor
    monkeypatch.setitem(sys.modules, "ultralytics", types.ModuleType("ultralytics"))
    monkeypatch.setitem(
        sys.modules, "ultralytics.models", types.ModuleType("ultralytics.models")
    )
    monkeypatch.setitem(sys.modules, "ultralytics.models.sam", sam)
    _FakeSam3Predictor.instances.clear()
    img = tmp_path / "a.jpg"
    Image.new("RGB", (W, H)).save(img)

    assert isinstance(MODELS["sam3"], Sam3Detector)
    det = Sam3Detector("sam3", "sam3.pt")
    run_model(det, {7: img}, tmp_path / "cache", tmp_path / "w", "mps")

    (pred,) = _FakeSam3Predictor.instances
    assert pred.overrides["model"] == str(tmp_path / "w" / "sam3.pt")
    assert pred.overrides["device"] == "mps"
    assert pred.overrides["quantize"] == 16
    assert pred.images == [str(img)] and pred.texts == [["bench"]]
    rec = json.loads((tmp_path / "cache" / "sam3" / "7.json").read_text())
    assert (rec["width"], rec["height"]) == (W, H)
    assert [d["conf"] for d in rec["dets"]] == [0.9, 0.3]
    rows = score_model(tmp_path / "cache", "sam3", {7: True}, (0.3,), ("horizontal",))
    best = next(r for r in rows if r["mode"] == "best")
    assert best["tp"] == 1 and best["threshold"] == 0.9
