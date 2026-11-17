from bench_finder.whats_new import diff


def _b(i, **kw):
    return {
        "id": i,
        "lat": 52.37,
        "lng": 4.89,
        "hero_key": "h",
        "facing": 90.0,
        "faces_category": "water",
        **kw,
    }


def test_diff_sorts_changes_into_kinds():
    old = {1: _b(1), 2: _b(2), 3: _b(3, hero_key=None), 4: _b(4), 5: _b(5)}
    new = {
        1: _b(1),
        3: _b(3),  # got a photo
        4: _b(4, hero_key="other", facing=150.0),  # new photo, turned 60°
        5: _b(5, hero_key=None, faces_category="park"),  # lost photo, looks elsewhere
        6: _b(6),  # new bench
    }
    d = {
        k: [(it.get("new") or it["old"])["id"] for it in v]
        for k, v in diff(old, new).items()
    }
    assert d == {
        "new_bench": [6],
        "lost_bench": [2],
        "photo_gained": [3],
        "photo_lost": [5],
        "photo_changed": [4],
        "facing_moved": [4],
        "looks_changed": [5],
    }
