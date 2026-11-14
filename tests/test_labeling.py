import json
import sqlite3
from collections import Counter

import pytest

from bench_finder.labeling import store
from bench_finder.labeling.server import LabelingApp
from bench_finder.migrate import migrate


def _make_db(tmp_path, benches):
    """benches: list of (direction_or_None, image_source, camera_distance_m)."""
    db = str(tmp_path / "t.db")
    migrate(db)
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(searches)")}
    assert "id" in cols
    conn.execute(
        "INSERT INTO searches (id, query, start_lat, start_lng, search_radius, status, created_at) "
        "VALUES (1, 'q', 0, 0, 100, 'done', '2025-01-01')"
    )
    for n, (direction, src, dist) in enumerate(benches, start=1):
        tags = {"amenity": "bench", "direction": direction}
        conn.execute(
            "INSERT INTO bench_candidates (id, search_id, lat, lng, tags, source, status, created_at) "
            "VALUES (?, 1, 1.0, 1.0, ?, 'overpass', 'pending', '2025-01-01')",
            (n, json.dumps(tags)),
        )
        conn.execute(
            "INSERT INTO images (id, bench_candidate_id, heading, filepath, capture_success, "
            "created_at, image_source, camera_distance_m, kind) VALUES (?, ?, 0, ?, 1, '2025-01-01', ?, ?, 'legacy')",
            (n, n, f"images/{n}.jpg", src, dist),
        )
    conn.commit()
    conn.close()
    return db


def test_queue_stratified_and_direction_first(tmp_path):
    benches = [("90", "A", 5.0)] * 2  # direction benches
    benches += [(None, "A", 5.0)] * 10 + [(None, "B", 50.0)] * 10
    db = _make_db(tmp_path, benches)
    q = store.build_queue(store.connect(db))
    order = q["order"]
    assert len(order) == 22 and q["total"] == 22
    assert set(order[:2]) == {1, 2}  # direction-tagged first
    # the first 8 non-direction benches alternate between the two strata
    strata = Counter("A" if b <= 12 else "B" for b in order[2:10])
    assert strata == {"A": 4, "B": 4}


def test_queue_excludes_labeled_but_counts_them(tmp_path):
    db = _make_db(tmp_path, [(None, "A", 5.0)] * 3)
    conn = store.connect(db)
    store.save_labels(conn, 2, {"bench_present": "yes"})
    q = store.build_queue(conn)
    assert 2 not in q["order"] and q["labeled"] == 1 and q["total"] == 3


def test_save_labels_upserts_one_row_per_type(tmp_path):
    db = _make_db(tmp_path, [(None, "A", 5.0)])
    conn = store.connect(db)
    store.save_labels(conn, 1, {"bench_present": "yes", "view_relation": "back-left"})
    store.save_labels(conn, 1, {"view_relation": "front", "bench_type": "picnic"})
    rows = {
        r["label_type"]: (json.loads(r["value"]), r["annotator"])
        for r in conn.execute("SELECT * FROM image_annotations")
    }
    assert rows == {
        "bench_present": ("yes", "human:owner"),
        "view_relation": ("front", "human:owner"),
        "bench_type": ("picnic", "human:owner"),
    }
    assert conn.execute("SELECT COUNT(*) FROM image_annotations").fetchone()[0] == 3


def test_save_labels_validates(tmp_path):
    db = _make_db(tmp_path, [(None, "A", 5.0)])
    conn = store.connect(db)
    with pytest.raises(ValueError):
        store.save_labels(conn, 1, {"view_relation": "sideways"})
    with pytest.raises(ValueError):
        store.save_labels(conn, 99, {"bench_present": "yes"})
    assert conn.execute("SELECT COUNT(*) FROM image_annotations").fetchone()[0] == 0


def test_export_only_human_labels(tmp_path):
    db = _make_db(tmp_path, [("180", "A", 5.0), (None, "A", 5.0)])
    conn = store.connect(db)
    store.save_labels(conn, 1, {"bench_present": "yes", "bench_type": "backrest"})
    conn.execute(
        "INSERT INTO image_annotations (image_id, annotator, label_type, value, created_at) "
        "VALUES (2, 'model:x', 'bench_present', '\"yes\"', '2025-01-01')"
    )
    conn.commit()
    out = tmp_path / "gold.jsonl"
    assert store.export_gold(conn, str(out)) == 1
    rec = json.loads(out.read_text().splitlines()[0])
    assert rec["image_id"] == 1 and rec["osm_direction"] == "180"
    assert rec["labels"] == {"bench_present": "yes", "bench_type": "backrest"}


def test_http_label_roundtrip(tmp_path):
    db = _make_db(tmp_path, [(None, "A", 5.0)])
    app = LabelingApp(db, tmp_path)
    status, _, payload = app.handle(
        "POST",
        "/api/label",
        json.dumps({"image_id": 1, "labels": {"bench_type": "other"}}).encode(),
    )
    assert status == 200 and json.loads(payload)["written"] == 1
    status, _, payload = app.handle("GET", "/api/bench/1", b"")
    assert json.loads(payload)["images"][0]["labels"] == {"bench_type": "other"}
    assert (
        app.handle(
            "POST", "/api/label", b'{"image_id": 1, "labels": {"bench_type": "x"}}'
        )[0]
        == 400
    )


def test_image_served_from_images_root(tmp_path):
    db = _make_db(tmp_path, [(None, "A", 5.0)])
    root = tmp_path / "images"
    root.mkdir()
    (root / "1.jpg").write_bytes(b"\xff\xd8jpeg")
    app = LabelingApp(db, root)
    status, ctype, payload = app.handle("GET", "/api/image/1", b"")
    assert (status, ctype, payload) == (200, "image/jpeg", b"\xff\xd8jpeg")
