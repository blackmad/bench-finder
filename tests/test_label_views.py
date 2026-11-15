import json
import sqlite3

from bench_finder import label_views as lv
from bench_finder.migrate import migrate


def _db(tmp_path):
    db = str(tmp_path / "t.db")
    migrate(db)
    c = sqlite3.connect(db)
    c.execute(
        "INSERT INTO searches (id, query, start_lat, start_lng, search_radius, status, created_at) "
        "VALUES (1,'q',0,0,1,'done','2025-01-01')"
    )
    c.execute(
        "INSERT INTO bench_candidates (id, search_id, lat, lng, tags, source, status, created_at) "
        "VALUES (7,1,1,1,'{}','overpass','pending','2025-01-01')"
    )
    for iid, bearing in ((1, 90.0), (2, 270.0), (3, 0.0)):
        c.execute(
            "INSERT INTO images (id, bench_candidate_id, heading, filepath, capture_success, "
            "created_at, kind, camera_bearing_deg) VALUES (?,7,0,'x.jpg',1,'2025-01-01','aimed',?)",
            (iid, bearing),
        )
    return db, c


def _det(c, iid, model, conf, target=1):
    cur = c.execute(
        "INSERT INTO detections (image_id, model_id, has_bench, bench_count, max_confidence, confidence_threshold, source, "
        "detection_success, created_at) VALUES (?,?,1,1,?,0.1,'local',1,'2025-01-01')",
        (iid, model, conf),
    )
    c.execute(
        "INSERT INTO detection_items (detection_id, confidence, bbox, class_name, created_at, is_target) "
        "VALUES (?,?,'[0,0,1,1]','bench','2025-01-01',?)",
        (cur.lastrowid, conf, target),
    )


def _label(c, iid, **kv):
    for k, v in kv.items():
        c.execute(
            "INSERT INTO image_annotations (image_id, annotator, label_type, value, confidence, created_at) "
            "VALUES (?,?,?,?,0.9,'2025-01-01')",
            (iid, lv.ANNOTATOR, k, json.dumps(v)),
        )


def test_gate_prefers_sam3_verdict(tmp_path):
    _, c = _db(tmp_path)
    _det(c, 1, "sam3", 0.7)  # sam3 confirms
    _det(c, 2, "yolo11x-seg", 0.9)
    _det(c, 2, "sam3", 0.3)  # sam3 ran and rejected: its miss wins over yolo
    _det(c, 3, "yolo11x-seg", 0.3)  # no sam3: yolo decides
    assert [i for i, _ in lv.gated_images(c)] == [1, 3]


def test_fuse_writes_looks_at_and_facing(tmp_path):
    db, c = _db(tmp_path)
    common = {"bench_present": "yes", "bench_type": "backrest", "quality": 3}
    _label(c, 1, view_relation="back", faces_category="water", **common)
    _label(c, 2, view_relation="front", faces_category="water", **common)
    _label(c, 3, view_relation="left", faces_category="park", **common)
    c.commit()
    assert lv.fuse(db) == {"benches": 1, "with_looks_at": 1}
    row = c.execute(
        "SELECT faces_category, facing_method, hero_image_id, round(facing_deg) "
        "FROM bench_attributes WHERE bench_candidate_id = 7"
    ).fetchone()
    # back at 90 -> 90, front at 270 -> 90, left at 0 -> 270: two of three say 90.
    assert row[0] == "water" and row[1] == "vlm" and row[2] is None
    assert row[3] == 90
