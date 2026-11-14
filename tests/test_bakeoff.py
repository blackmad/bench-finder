import json
import sqlite3

import pytest

from bench_finder.bakeoff.detectors import (
    Det,
    best_threshold,
    collect_image_ids,
    is_hit,
    load_gold,
    prf,
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
