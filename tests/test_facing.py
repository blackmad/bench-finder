import sqlite3

import pytest

from bench_finder import facing as f
from bench_finder.migrate import migrate


def V(i, bearing, rel, q=1.0, conf=None, btype="backrest", **kw):
    return f.ViewInput(
        image_id=i,
        camera_bearing_deg=bearing,
        view_relation=rel,
        quality=q,
        confidence=conf,
        bench_type=btype,
        **kw,
    )


def test_sign_convention_each_relation():
    # Camera looks north (bearing 0).
    assert f.view_facing(0, "back") == 0  # sitter looks north too
    assert f.view_facing(0, "front") == 180  # sitter looks at camera (south)
    # Camera on sitter's left: camera is west of a north... derive: bearing 90 (camera looks east)
    # and the sitter's left is the camera side -> sitter faces north (facing = 90 - 90).
    assert f.view_facing(90, "left") == 0
    assert (
        f.view_facing(270, "right") == 0
    )  # camera looks west, on sitter's right -> faces north
    assert f.view_facing(0, "back-left") == 315
    assert f.view_facing(0, "back-right") == 45
    assert f.view_facing(0, "front-left") == 225
    assert f.view_facing(0, "front-right") == 135
    assert f.view_facing(10, "unknown") is None


def test_wraparound_mean_350_and_10():
    mean, r = f.circular_mean([350, 10], [1, 1])
    assert mean == pytest.approx(0, abs=1e-6) or mean == pytest.approx(360, abs=1e-6)
    assert r == pytest.approx(0.985, abs=1e-3)
    res = f.fuse_views([V(1, 350, "back"), V(2, 10, "back")])
    assert min(res.facing_deg, 360 - res.facing_deg) < 1e-6
    assert res.facing_method == "vlm"


def test_single_view():
    res = f.fuse_views([V(1, 120, "front", q=0.8, conf=0.5)])
    assert res.facing_deg == pytest.approx(300)
    assert res.facing_confidence == pytest.approx(1.0)  # one vector: R = 1
    assert res.embed_heading_deg == res.facing_deg
    assert res.hero_image_id == 1 and res.hero_reason == "backrest_no_rear_best_front"


def test_weights_pull_toward_better_view():
    res = f.fuse_views([V(1, 0, "back", q=0.9), V(2, 90, "back", q=0.1)])
    assert 0 < res.facing_deg < 45


def test_backless_axis_only():
    # Facing 0 and 180 are the same axis: backless fuses to an axis with R=1.
    views = [V(1, 0, "back", btype="backless"), V(2, 0, "front", btype="backless")]
    res = f.fuse_views(views)
    assert res.axis_only is True and res.backrest is False
    assert res.facing_deg == pytest.approx(
        0, abs=1e-6
    ) or res.facing_deg == pytest.approx(180)
    assert res.facing_deg < 180
    assert res.facing_confidence == pytest.approx(1.0)
    assert res.embed_heading_deg is None
    # The same views as a backrest bench cancel out (R ~ 0).
    rb = f.fuse_views([V(1, 0, "back"), V(2, 0, "front")])
    assert rb.facing_confidence == pytest.approx(0, abs=1e-6)


def test_osm_direction_parsing():
    assert f.parse_osm_direction("90") == 90
    assert f.parse_osm_direction("370") == 10
    assert f.parse_osm_direction("NNE") == 22.5
    assert f.parse_osm_direction("sw") == 225
    assert f.parse_osm_direction("north") == 0
    assert f.parse_osm_direction("forward") is None
    assert f.parse_osm_direction(None) is None


def test_osm_override_and_disagreement_flag():
    views = [V(1, 0, "back")]  # vlm says 0
    ok = f.fuse_views(views, osm_direction="30")
    assert ok.facing_deg == 30 and ok.facing_method == "osm_tag"
    assert ok.facing_confidence == 1.0 and not ok.needs_review
    assert ok.disagreement_deg == pytest.approx(30)
    bad = f.fuse_views(views, osm_direction="S")
    assert bad.facing_deg == 180 and bad.needs_review and bad.disagreement_deg == 180
    no_views = f.fuse_views([], osm_direction="E")
    assert no_views.facing_deg == 90 and no_views.hero_image_id is None


def test_geometry_prior_hook_and_flag():
    assert f.geometry_prior_check(10, None) == (None, False)
    d, flag = f.geometry_prior_check(10, 355)
    assert d == 15 and not flag
    d, flag = f.geometry_prior_check(0, 100)
    assert flag
    assert f.geometry_prior_check(0, 100, axis_only=True) == (80, True)
    # Agreeing prior leaves VLM answer; disagreeing prior flags it.
    res = f.fuse_views([V(1, 0, "back")], geometry_prior_deg=120)
    assert res.facing_method == "vlm" and res.needs_review
    # Low-confidence VLM (opposing views) hands over to the prior.
    res = f.fuse_views([V(1, 0, "back"), V(2, 0, "front")], geometry_prior_deg=45)
    assert res.facing_method == "geometry" and res.facing_deg == 45


def test_distribution_voting_uses_whole_distribution():
    probs = {"back": 0.45, "back-right": 0.45, "unknown": 0.1}
    dist = V(1, 0, "back", view_relation_probs=probs)
    res = f.fuse_views([dist])
    # Top answer alone would say 0; the distribution splits 0 / 45 -> 22.5.
    assert res.facing_deg == pytest.approx(22.5, abs=1e-6)
    assert res.facing_confidence < 1.0
    # A flat unknown-only distribution carries no facing.
    assert (
        f.fuse_views(
            [V(1, 0, "unknown", view_relation_probs={"unknown": 1.0})]
        ).facing_deg
        is None
    )


def test_hero_choice():
    views = [
        V(1, 0, "front", q=0.95),
        V(2, 0, "back-left", q=0.6),
        V(3, 0, "back-right", q=0.8),
        V(4, 0, "left", q=0.99),
    ]
    res = f.fuse_views(views)
    assert (res.hero_image_id, res.hero_reason) == (3, "backrest_rear_view")
    backless = [
        V(i.image_id, 0, i.view_relation, i.quality, btype="backless") for i in views
    ]
    res = f.fuse_views(backless)
    assert (res.hero_image_id, res.hero_reason) == (1, "best_front_view")
    only_side = f.fuse_views([V(9, 0, "left", q=0.5)])
    assert only_side.hero_reason == "best_quality_fallback"
    invisible = f.fuse_views([V(1, 0, "back", bench_visible=False)])
    assert invisible.hero_image_id is None and invisible.facing_deg is None


def test_attribute_fields_and_pano():
    res = f.fuse_views(
        [
            V(
                1,
                0,
                "back",
                q=0.9,
                faces_category="water",
                faces_text="river",
                pano_id="P1",
            ),
            V(2, 0, "back", q=0.2, faces_category="park"),
        ]
    )
    assert res.faces_category == "water" and res.faces_text == "river"
    assert res.embed_pano_id == "P1" and res.bench_type == "backrest"


def test_write_bench_attributes_upsert(tmp_path):
    db = str(tmp_path / "t.db")
    migrate(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO searches (id, query, start_lat, start_lng, search_radius, status, created_at) "
        "VALUES (1,'q',0,0,1,'done','2025-01-01')"
    )
    conn.execute(
        "INSERT INTO bench_candidates (id, search_id, lat, lng, tags, source, status, created_at) "
        "VALUES (7,1,1,1,'{}','overpass','pending','2025-01-01')"
    )
    conn.execute(
        "INSERT INTO images (id, bench_candidate_id, heading, filepath, capture_success, created_at, kind) "
        "VALUES (3,7,0,'x.jpg',1,'2025-01-01','legacy')"
    )
    res = f.fuse_views([V(3, 90, "left", pano_id="PX", faces_category="street")])
    f.write_bench_attributes(conn, 7, res)
    row = conn.execute(
        "SELECT facing_deg, facing_method, axis_only, backrest, hero_image_id, hero_reason, "
        "embed_pano_id, embed_heading_deg, faces_category FROM bench_attributes WHERE bench_candidate_id=7"
    ).fetchone()
    assert (
        row[0] == pytest.approx(0) and row[1] == "vlm" and row[2] == 0 and row[3] == 1
    )
    assert row[4] == 3 and row[5] == "best_quality_fallback"
    assert row[6] == "PX" and row[7] == pytest.approx(0) and row[8] == "street"
    # Second write updates the same row.
    f.write_bench_attributes(
        conn, 7, f.fuse_views([V(3, 90, "right")], osm_direction="180")
    )
    rows = conn.execute(
        "SELECT facing_deg, facing_method FROM bench_attributes"
    ).fetchall()
    assert rows == [(180.0, "osm_tag")]
