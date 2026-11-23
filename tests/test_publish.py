import gzip
import json
import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from bench_finder.migrate import migrate
from bench_finder.publish import CapacityError, check_capacity, publish, upload_dir
from bench_finder.publish.build import (
    image_rank,
    parse_direction,
    target_gate,
    view_label,
)
from bench_finder.publish.images import (
    hires_path,
    process_image,
    render_source,
    target_widths,
)
from bench_finder.recut import hero_image_ids


def _make_image(path: Path, size=(1000, 600), color=(120, 90, 40)):
    Image.effect_noise(size, 40).convert("RGB").save(path, "JPEG")
    return path


@pytest.fixture
def world(tmp_path):
    db = str(tmp_path / "t.db")
    migrate(db)
    images = tmp_path / "images"
    images.mkdir()
    _make_image(images / "a.jpg", (1000, 600))
    _make_image(images / "small.jpg", (300, 200))
    _make_image(images / "aimed.jpg", (900, 500))
    c = sqlite3.connect(db)
    cols = {r[1] for r in c.execute("PRAGMA table_info(searches)")}
    vals = {
        "id": 1,
        "query": "q",
        "start_lat": 0,
        "start_lng": 0,
        "search_radius": 1,
        "status": "completed",
        "created_at": "2024-01-01",
        "updated_at": "2024-01-01",
    }
    use = {k: v for k, v in vals.items() if k in cols}
    c.execute(
        f"INSERT INTO searches ({','.join(use)}) VALUES ({','.join('?' * len(use))})",
        list(use.values()),
    )
    for cid, tags in [
        (
            1,
            {
                "direction": "SSW",
                "backrest": "yes",
                "material": "Wood",
                "seats": "4",
                "lit": "no",
            },
        ),
        (2, {}),
        (3, {}),
    ]:
        c.execute(
            "INSERT INTO bench_candidates (id, search_id, provider_id, lat, lng, tags, source, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                cid,
                1,
                f"n{cid}",
                52.1234567 + cid,
                4.9876543,
                json.dumps(tags),
                "OSM",
                "PENDING",
                "2024-01-01",
            ),
        )
        c.execute(
            "INSERT INTO reverse_geocodes (bench_candidate_id, formatted_address, street_name, street_number, created_at) "
            "VALUES (?,?,?,?,?)",
            (cid, f"Main St {cid}, Town", "Main St", str(cid), "2024-01-01"),
        )
    imgs = [
        (1, 1, "a.jpg", "legacy", None),
        (2, 1, "small.jpg", "legacy", None),
        (3, 1, "aimed.jpg", "aimed", "PANO1PANO1PANO1PANO1AB"),
        (4, 2, "small.jpg", "legacy", None),
        (5, 3, "small.jpg", "legacy", None),
    ]
    for iid, cid, fn, kind, pano in imgs:
        c.execute(
            "INSERT INTO images (id, bench_candidate_id, heading, filename, filepath, capture_success, kind, pano_id, "
            "camera_bearing_deg, created_at) VALUES (?,?,?,?,?,1,?,?,?,'2024-01-01')",
            (iid, cid, 90, fn, f"images/{fn}", kind, pano, 123.0 if pano else None),
        )
    c.execute(
        "INSERT INTO detections (id,image_id,has_bench,bench_count,max_confidence,detection_success,model_id,"
        "confidence_threshold,source,created_at) VALUES (1,1,1,1,0.9,1,'m',0.5,'ROBOFLOW','2024-01-01')"
    )
    c.execute(
        "INSERT INTO bench_attributes (bench_candidate_id, facing_deg, facing_confidence, facing_method, axis_only,"
        " bench_type, backrest, faces_category, hero_image_id, embed_pano_id, embed_heading_deg, updated_at)"
        " VALUES (3, 200, 0.8, 'vlm', 0, 'backrest', 1, 'water', 5, '9524987388017545573', 10, '2024-01-01')"
    )
    c.commit()
    c.close()
    return db, images, tmp_path / "out"


def test_parse_direction():
    assert parse_direction("SSW") == 202.5
    assert parse_direction("120") == 120
    assert parse_direction("forward") is None
    assert parse_direction(None) is None


def test_no_upscale_and_incremental(tmp_path):
    src = _make_image(tmp_path / "s.jpg", (900, 500))
    out = tmp_path / "o"
    r1 = process_image(str(src), str(out))
    assert r1.widths == (400, 800)  # 1600 would upscale
    assert r1.generated == 4
    for f in (out / "img").glob("*"):
        assert Image.open(f).width <= 900
    assert not list((out / "img").glob("*-1600.*"))
    r2 = process_image(str(src), str(out))
    assert r2.generated == 0 and r2.hash == r1.hash
    assert target_widths(640) == (400,)
    assert target_widths(1600) == (400, 800, 1600)
    # a tiny source keeps its native width
    tiny = _make_image(tmp_path / "t.jpg", (300, 200))
    assert process_image(str(tiny), str(out)).widths == (300,)
    # different content -> different hash
    other = _make_image(tmp_path / "u.jpg", (900, 500))
    assert process_image(str(other), str(out)).hash != r1.hash


def test_publish_outputs(world):
    db, images, out = world
    with pytest.raises(Exception, match=r"unable|no such"):
        publish(db + "x", images, out)
    res = publish(db, images, out, include_unclassified=True, workers=2)
    assert res.benches == 3
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["version"] == 1 and manifest["count"] == 3
    assert manifest["bench_dir"] == "bench"
    gj = json.loads((out / "data" / manifest["benches"]).read_text())
    assert gj["type"] == "FeatureCollection"
    feats = {f["id"]: f for f in gj["features"]}
    p1 = feats[1]["properties"]
    assert (
        p1["facing"] == 202.5
        and p1["facing_method"] == "osm_tag"
        and p1["backrest"] is True
    )
    assert (p1["material"], p1["seats"], p1["lit"]) == ("wood", 4, False)
    p2 = feats[2]["properties"]
    assert (p2["material"], p2["seats"], p2["lit"]) == (None, None, None)
    assert p1["hero_key"] and set(p1["hero_urls"]) == {"400", "800"}
    assert p1["hero_urls"]["400"] == f"img/{p1['hero_key']}-400.avif"
    assert p1["address"] == "Main St 1"
    assert feats[1]["geometry"]["coordinates"] == [p1["lng"], p1["lat"]]
    assert feats[2]["properties"]["hero_urls"] is None  # no detection -> no hero
    assert feats[2]["properties"]["facing"] is None
    p3 = feats[3]["properties"]
    # The labeller's own facings are kept in the db but not published.
    assert (
        p3["facing"] is None
        and p3["facing_method"] is None
        and p3["bench_type"] == "backrest"
    )
    assert set(p3["hero_urls"]) == {"300"}  # small source is never upscaled
    d1 = json.loads((out / "data" / "bench" / "1.json").read_text())
    assert d1["material"] == "wood"
    assert d1["gallery"][0]["urls"] == p1["hero_urls"]
    assert [g["kind"] for g in d1["gallery"]][:2] == ["legacy", "aimed"]
    assert d1["embed_pano_id"] == "PANO1PANO1PANO1PANO1AB"
    assert d1["embed_heading_deg"] == 123.0
    assert d1["address_full"]["street"] == "Main St"
    d3 = json.loads((out / "data" / "bench" / "3.json").read_text())
    # An Apple panorama id never reaches Google's embed; without a camera
    # position there is nothing to open.
    assert d3["embed_pano_id"] is None and d3["embed_lat"] is None
    # incremental: second run writes no derivatives
    assert (
        publish(
            db, images, out, include_unclassified=True, workers=2
        ).derivatives_written
        == 0
    )


def test_classified_only_by_default(world):
    db, images, out = world
    res = publish(db, images, out, workers=1)
    assert res.benches == 1 and res.eligible == 1


def test_limit_projects_full_size(world):
    db, images, out = world
    res = publish(db, images, out, include_unclassified=True, limit=1, workers=1)
    assert res.benches == 1 and res.eligible == 3
    assert res.projected_total_bytes == pytest.approx(res.total_bytes * 3, rel=0.01)


def test_capacity_guard():
    assert check_capacity(1, 1) == []
    assert check_capacity(10 * 10**9, 1)
    assert check_capacity(1, 600_000)


def test_capacity_guard_trips(world):
    db, images, out = world
    with pytest.raises(CapacityError, match="exceeds budget"):
        publish(db, images, out, include_unclassified=True, workers=1, budget_bytes=100)


class FakeS3:
    def __init__(self):
        self.objects: dict[str, dict] = {}

    def list_objects_v2(self, Bucket, ContinuationToken=None):
        return {
            "Contents": [
                {"Key": k, "ETag": f'"{v["etag"]}"'} for k, v in self.objects.items()
            ],
            "IsTruncated": False,
        }

    def put_object(self, Bucket, Key, Body, ContentType, CacheControl):
        import hashlib

        self.objects[Key] = {
            "etag": hashlib.md5(Body).hexdigest(),
            "cc": CacheControl,
            "ct": ContentType,
        }


def test_upload_only_new(world):
    db, images, out = world
    publish(db, images, out, include_unclassified=True, workers=1)
    s3 = FakeS3()
    first = upload_dir(out, s3, "b", prune=False)
    assert first["skipped"] == 0 and first["uploaded"] > 0
    assert list(s3.objects)[-1] == "manifest.json"
    assert s3.objects["manifest.json"]["cc"] == "public, max-age=60"
    img_key = next(k for k in s3.objects if k.startswith("img/"))
    assert "immutable" in s3.objects[img_key]["cc"]
    assert s3.objects[img_key]["ct"] in ("image/avif", "image/webp")
    again = upload_dir(out, s3, "b", prune=False)
    assert again["uploaded"] == 0
    # a changed mutable file is re-uploaded, hashed files are not
    (out / "data" / "bench" / "1.json").write_text("{}")
    third = upload_dir(out, s3, "b", prune=False)
    assert third["uploaded"] == 1


def test_geojson_gz_size_reported(world):
    db, images, out = world
    res = publish(db, images, out, include_unclassified=True, workers=1)
    raw = (out / "data" / res.geojson_name).read_bytes()
    assert res.geojson_bytes == len(raw)
    assert res.geojson_gz_bytes <= len(gzip.compress(raw, 9)) + 1


def test_bbox_limits_coverage(world):
    db, images, out = world
    # Fixture benches sit at lat 53.12.., 54.12.., 55.12..; keep only the first.
    res = publish(
        db,
        images,
        out,
        include_unclassified=True,
        bbox=(4.9, 53.0, 5.0, 53.5),
        workers=1,
    )
    assert res.benches == 1


# --------------------------------------------------------------------------- hero ranking


def _img(iid, bearing, *, sam3=None, yolo=None, labels=None, box=None, date=None):
    targets = {}
    if sam3 is not None:
        targets["sam3"] = (sam3, box)
    if yolo is not None:
        targets["yolo11x-seg"] = (yolo, box)
    return {
        "id": iid,
        "kind": "aimed",
        "heading": round(bearing),
        "camera_bearing_deg": bearing,
        "conf": max(sam3 or 0, yolo or 0),
        "pano_date": date,
        "targets": targets,
        "view_labels": labels or {},
    }


def test_target_gate_prefers_sam3_verdict():
    assert target_gate(_img(1, 0, sam3=0.7))[0] == 0
    assert target_gate(_img(1, 0, sam3=0.5))[0] == 0  # cutoff 0.5 since owner review
    # sam3 ran and stayed under the cutoff: its miss counts, whatever yolo said
    assert target_gate(_img(1, 0, sam3=0.45, yolo=0.9))[0] == 2
    assert target_gate(_img(1, 0, yolo=0.3))[0] == 1.5  # gallery until SAM 3 checks
    assert target_gate(_img(1, 0, yolo=0.1))[0] == 2
    assert target_gate({"id": 1, "conf": 0.4})[0] == 1  # legacy: older detector only
    assert target_gate({"id": 1, "conf": None})[0] == 2


def test_view_label_trusts_oracle_first():
    img = _img(
        1,
        0,
        labels={
            "gemini-decision-1@low": "front",
            "anthropic/claude-sonnet-5.5": "front-left",
            "oracle:claude-opus-5-5": "back",
        },
    )
    assert view_label(img) == "back"
    img["view_labels"]["oracle:claude-opus-5-5"] = "unknown"
    assert view_label(img) == "front-left"  # next trusted annotator
    assert view_label(_img(1, 0, labels={"qwen3-vl:8b": "back"})) is None


def test_rank_behind_the_bench_wins():
    # Bench 1356 in miniature: faces S, two back-corner labels; the camera
    # looking with the bench (213 deg) beats the one looking across it (88 deg).
    side = _img(1, 88, sam3=0.74, labels={"oracle:x": "back-right"})
    behind = _img(2, 213, sam3=0.73, labels={"oracle:x": "back-left"})
    front = _img(3, 10, sam3=0.95, labels={"oracle:x": "front"})
    ranked = sorted([front, side, behind], key=lambda i: image_rank(i, 180.0))
    assert [i["id"] for i in ranked] == [2, 1, 3]


def test_rank_geometry_without_labels():
    behind = _img(1, 170, yolo=0.3)
    beside = _img(2, 90, yolo=0.9)
    facing_camera = _img(3, 0, yolo=0.9)
    ranked = sorted([facing_camera, beside, behind], key=lambda i: image_rank(i, 180.0))
    assert [i["id"] for i in ranked] == [1, 2, 3]
    # No facing and no labels: box size and centrality, then confidence.
    small = _img(4, 0, yolo=0.9, box={"x1": 0, "y1": 0, "x2": 50, "y2": 50})
    big = _img(5, 0, yolo=0.5, box={"x1": 300, "y1": 300, "x2": 700, "y2": 700})
    assert sorted([small, big], key=lambda i: image_rank(i, None))[0] is big


def test_publish_picks_behind_view(world):
    db, images, out = world
    _make_image(images / "behind.jpg", (900, 500))
    _make_image(images / "side.jpg", (900, 500))
    c = sqlite3.connect(db)
    # Bench 1 faces SSW (202.5). Image 6 looks 210 (behind it), image 7 looks 110.
    for iid, fn, bearing in [(6, "behind.jpg", 210.0), (7, "side.jpg", 110.0)]:
        c.execute(
            "INSERT INTO images (id, bench_candidate_id, heading, filename, filepath, capture_success,"
            " kind, pano_id, camera_bearing_deg, created_at)"
            " VALUES (?,1,?,?,?,1,'aimed',?,?,'2024-01-01')",
            (iid, round(bearing), fn, f"images/{fn}", f"P{iid}", bearing),
        )
        c.execute(
            "INSERT INTO detections (id,image_id,has_bench,bench_count,max_confidence,"
            "detection_success,model_id,confidence_threshold,source,created_at)"
            " VALUES (?,?,1,1,0.8,1,'sam3',0.3,'LOCAL','2024-01-01')",
            (iid * 10, iid),
        )
        c.execute(
            "INSERT INTO detection_items (detection_id, confidence, bbox, class_name,"
            " created_at, is_target) VALUES (?, 0.8, ?, 'bench', '2024-01-01', 1)",
            (iid * 10, json.dumps({"x1": 300, "y1": 200, "x2": 600, "y2": 400})),
        )
    c.execute(
        "INSERT INTO image_annotations (image_id, annotator, label_type, value, created_at)"
        " VALUES (7, 'oracle:test', 'view_relation', '\"unknown\"', '2024-01-01')"
    )
    c.commit()
    c.close()
    publish(db, images, out, include_unclassified=True, workers=1)
    d1 = json.loads((out / "data" / "bench" / "1.json").read_text())
    assert [g["camera_bearing_deg"] for g in d1["gallery"][:2]] == [210.0, 110.0]
    assert d1["gallery"][0]["urls"] == d1["hero_urls"]


def test_render_source_prefers_hires(tmp_path):
    orig = _make_image(tmp_path / "v.jpg", (100, 100))
    assert render_source(orig) == orig
    (tmp_path / "hires").mkdir()
    (tmp_path / "hires" / "v.jpg").write_bytes(b"")  # an empty file is ignored
    assert render_source(orig) == orig
    hires = _make_image(tmp_path / "hires" / "v.jpg", (200, 200))
    assert hires_path(orig) == hires
    assert render_source(orig) == hires


def test_publish_uses_hires_without_upscaling(world):
    db, images, out = world
    (images / "hires").mkdir()
    _make_image(images / "hires" / "aimed.jpg", (1800, 1000))
    publish(db, images, out, include_unclassified=True, workers=1)
    d1 = json.loads((out / "data" / "bench" / "1.json").read_text())
    aimed = next(g for g in d1["gallery"] if g["kind"] == "aimed")
    assert set(aimed["urls"]) == {"400", "800", "1600"}  # 1600 is real now
    assert aimed["width"] == 1600
    legacy = next(g for g in d1["gallery"] if g["kind"] == "legacy")
    assert set(legacy["urls"]) == {"400", "800"}  # no hi-res: never upscaled


def test_hero_image_ids_match_publish(world):
    db, images, _ = world
    conn = sqlite3.connect(db)
    try:
        ids = hero_image_ids(conn, images, include_unclassified=True)
    finally:
        conn.close()
    # bench 1: the detected legacy view; bench 2: no bench seen; bench 3: manual hero
    assert ids == [1, 5]


def test_source_is_fixed_once_decided(tmp_path):
    """A re-cut landing mid-publish must not change an image's source (KeyError)."""
    from bench_finder.publish.build import _source

    _make_image(tmp_path / "v.jpg", (100, 100))
    img = {"filepath": "v.jpg", "filename": "v.jpg"}
    first = _source(img, tmp_path)
    (tmp_path / "hires").mkdir()
    _make_image(tmp_path / "hires" / "v.jpg", (200, 200))
    assert _source(img, tmp_path) == first


def test_webp_capped_at_800():
    from bench_finder.publish.images import format_widths

    assert format_widths((400, 800, 1600), "avif") == (400, 800, 1600)
    assert format_widths((400, 800, 1600), "webp") == (400, 800)
    assert format_widths((1000,), "webp") == (1000,)


def test_benches_metres_apart_publish_as_one_place(world):
    db, images, out = world
    c = sqlite3.connect(db)
    # Bench 2 (no photo) sits 5 m north of bench 1 (photo): one place, led by 1.
    c.execute(
        "UPDATE bench_candidates SET lat = 52.1234567 + 1 + 5 / 111320.0 WHERE id = 2"
    )
    c.commit()
    res = publish(db, images, out, include_unclassified=True, workers=1)
    assert res.benches == 3
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["count"] == 2
    assert manifest["counts"]["benches"] == 3 and manifest["counts"]["places"] == 2
    gj = json.loads((out / "data" / manifest["benches"]).read_text())
    feats = {f["id"]: f["properties"] for f in gj["features"]}
    assert set(feats) == {1, 3}
    assert feats[1]["bench_ids"] == [1, 2] and feats[1]["count"] == 2
    assert feats[3]["bench_ids"] == [3] and feats[3]["count"] == 1
    d2 = json.loads((out / "data" / "bench" / "2.json").read_text())
    assert d2["place"]["id"] == 1 and d2["place"]["count"] == 2
    assert [b["id"] for b in d2["place"]["benches"]] == [1]
    assert d2["place"]["benches"][0]["hero_urls"] == feats[1]["hero_urls"]


def test_render_source_prefers_centred(tmp_path):
    from bench_finder.publish.images import render_source

    orig = tmp_path / "v.jpg"
    _make_image(orig, (100, 100))
    for sub in ("hires", "centred"):
        (tmp_path / sub).mkdir()
        _make_image(tmp_path / sub / "v.jpg", (200, 200))
    assert render_source(orig) == tmp_path / "centred" / "v.jpg"


def test_rank_blocked_view_loses_to_clear_one():
    behind_blocked = {**_img(1, 90, sam3=0.9), "occluded": True}
    side_clear = _img(2, 180, sam3=0.9)
    ranked = sorted([behind_blocked, side_clear], key=lambda i: image_rank(i, 90.0))
    assert [i["id"] for i in ranked] == [2, 1]


def test_prune_remote_deletes_only_unused():
    from bench_finder.publish.upload import prune_remote

    class S3:
        deleted: list[str] = []

        def delete_objects(self, Bucket, Delete):
            self.deleted += [o["Key"] for o in Delete["Objects"]]

    live = {f"data/bench/{i}.json" for i in range(120)} | {
        "data/benches.a.geojson",
        "manifest.json",
        "img/aaaaaaaaaaaaaaaa-400.avif",
    }
    s3 = S3()
    n = prune_remote(s3, "b", live, live | {"img/bbbbbbbbbbbbbbbb-400.avif"})
    assert n == 1 and s3.deleted == ["img/bbbbbbbbbbbbbbbb-400.avif"]


def test_winter_view_ranks_after_summer():
    from bench_finder.publish.build import image_rank

    base = {"id": 1, "image_source": "AMSTERDAM_PANORAMA", "detections": []}
    summer = {**base, "id": 2, "pano_date": "2019-07-01T10:00:00Z"}
    winter = {**base, "id": 1, "pano_date": "2021-02-17T12:52:48Z"}
    assert image_rank(summer, None) < image_rank(winter, None)


def test_vetoed_view_is_never_a_hero():
    assert target_gate({**_img(1, 0, sam3=0.9), "vetoed": True})[0] == 2


def test_confirmed_near_miss_can_be_hero():
    assert target_gate({**_img(1, 0, sam3=0.5), "confirmed": True})[0] == 0
    assert target_gate({**_img(1, 0, sam3=0.3), "confirmed": True})[0] == 2


def test_embed_view_sources():
    from bench_finder.publish.build import embed_view

    g = "bQ0tE2V_7xLWaMmD3LYDTA"
    # Google: keeps the pano id, heading from the camera to the bench (due east).
    pano, at, h = embed_view(
        g, 10.0, ("STREETVIEW_STREETLEVEL", 52.0, 4.9999), 52.0, 5.0
    )
    assert pano == g and at == (52.0, 4.9999) and round(h) == 90
    # Apple / city panoramas: no pano id, camera position + heading instead.
    for src, pid in (
        ("APPLE_STREETLEVEL", "9524987388017545573"),
        ("AMSTERDAM_PANORAMA", "TMX7316010203-001085_pano_0006_000012"),
    ):
        pano, at, h = embed_view(pid, 10.0, (src, 52.0001, 5.0), 52.0, 5.0)
        assert pano is None and at == (52.0001, 5.0) and round(h) == 180
    # Unknown source, no position: only a Google-shaped id survives.
    assert embed_view(g, 10.0, None, 52.0, 5.0) == (g, None, 10.0)
    assert embed_view("recording_2025-07-02_11-44-00_01950", 10.0, None, 52.0, 5.0) == (
        None,
        None,
        None,
    )


# --- 2026-11: label vs geometry, site picks ---------------------------

BOX = {"x1": 380, "y1": 420, "x2": 640, "y2": 640}  # mid-frame, clear of the edges


def test_rank_geometry_overrules_contradicting_label():
    """Bench 2160: the view along the facing was labelled "front" by a model."""
    flash = "gemini-3.1-flash-lite@v2"
    along = _img(1, 229.0, sam3=0.95, box=BOX, labels={flash: "front"})
    side = _img(2, 195.0 + 90, sam3=0.97, box=BOX, labels={flash: "right"})
    assert sorted([side, along], key=lambda i: image_rank(i, 230.0))[0] is along
    # A label that roughly agrees with geometry still decides (back-left vs geometry back).
    corner = _img(3, 229.0, sam3=0.95, box=BOX, labels={flash: "back-left"})
    assert image_rank(corner, 230.0)[4] == 1.0
    # The owner's label always stands, even against geometry.
    owner = _img(4, 229.0, sam3=0.95, box=BOX, labels={"oracle:owner": "front"})
    assert image_rank(owner, 230.0)[4] == 4.0
    # No facing: the label is all there is.
    assert image_rank(along, None)[4] == 4.0


def test_gallery_entries_carry_the_image_id():
    from bench_finder.publish.build import _image_entry

    res = type(
        "R", (), {"hash": "ab" * 8, "widths": [400, 800], "width": 800, "height": 800}
    )()
    img = {
        "id": 54438,
        "heading": 229,
        "camera_bearing_deg": 228.94,
        "kind": "aimed",
        "pano_date": "2023-04",
    }
    assert _image_entry(res, img)["id"] == 54438


def test_picked_images_one_per_bench_site_wins(tmp_path):
    from bench_finder.publish.exclude import picked_images

    (tmp_path / "review.json").write_text(
        json.dumps({"hero_pick": {"2160": 54437, "7": 70}})
    )
    (tmp_path / "site.json").write_text(json.dumps({"hero_pick": {"2160": 54438}}))
    assert picked_images(tmp_path) == {54438, 70}


def test_site_picks_latest_wins_and_moderator_views_count(tmp_path):
    from bench_finder.publish import site_picks

    out = json.dumps(
        [
            {
                "results": [
                    {"bench_id": 1356, "image_id": 10, "t": "2026-11-20T10:00:00Z"},
                    {"bench_id": 1356, "image_id": 99, "t": "2026-11-23T09:00:00Z"},
                    {"bench_id": 7, "image_id": 5, "t": None},
                ]
            }
        ]
    )
    assert site_picks.parse(out) == {"1356": 99, "7": 5}
    cfg = tmp_path / "wrangler.jsonc"
    cfg.write_text('{ "vars": { "ADMIN_UIDS": "abc, d\'e" } }')
    assert site_picks.admin_uids(cfg) == ["abc", "d'e"]
    q = site_picks.query(["abc", "d'e"])
    assert "view_suggestions" in q and "'d''e'" in q
    assert "view_suggestions" not in site_picks.query([])


def test_site_picks_parse_and_fallback(tmp_path):
    from bench_finder.publish import site_picks

    out = '[{"results": [{"bench_id": 2160, "image_id": 54438}], "success": true}]'
    assert site_picks.parse(out) == {"2160": 54438}
    path = tmp_path / "site.json"
    path.write_text('{"hero_pick": {"1": 2}}')
    # wrangler missing: the last synced file stands.
    assert site_picks.sync(path, worker_dir=tmp_path / "nowhere") is None
    assert json.loads(path.read_text()) == {"hero_pick": {"1": 2}}


def test_suggested_view_takes_second_slot_and_leads_only_when_picked(tmp_path):
    from bench_finder.publish.build import _order_images

    def img(iid, kind, bearing, **kw):
        name = f"{kind}_{iid}.jpg"
        Image.new("RGB", (64, 48)).save(tmp_path / name)
        return {
            **_img(iid, bearing, **kw),
            "kind": kind,
            "filename": name,
            "filepath": name,
        }

    lead = img(1, "aimed", 180.0, sam3=0.9, box=BOX)
    other = img(2, "aimed", 90.0, sam3=0.9, box=BOX)
    scenic = img(3, "suggested", 190.0)
    out, has_hero = _order_images([other, scenic, lead], None, 4, tmp_path, 180.0)
    assert has_hero and [i["id"] for i in out] == [1, 3, 2]
    # Scenic views stay out of the gallery until vetted.
    unvetted = img(4, "scenic", 185.0)
    out, _ = _order_images([other, unvetted, lead], None, 4, tmp_path, 180.0)
    assert [i["id"] for i in out] == [1, 2]
    scenic["picked"] = True  # chosen on the site
    out, _ = _order_images([other, scenic, lead], None, 4, tmp_path, 180.0)
    assert [i["id"] for i in out] == [3, 1, 2]


def test_scenic_aim_turns_toward_the_facing():
    from bench_finder.scenic import scenic_aim

    assert scenic_aim(54.0, 109.0) == 79.0  # bench 1743: capped at 25 degrees
    assert scenic_aim(100.0, 109.0) == 109.0  # already close: look along the facing
    assert scenic_aim(350.0, 20.0) == 15.0  # across north


def test_view_suggestion_sql_quoting_and_render_args(monkeypatch):
    from bench_finder import view_suggestions as vs

    assert vs.sql_text("it's") == "'it''s'"
    calls = []

    class Ex:
        def bench(self, bid, r):
            calls.append(("bench", bid, r))

        def _cand(self, bid, key):
            if key != "google:PANO_ID_ABCDEFGHIJKL":
                raise KeyError(key)

        def _save(self, *a, **kw):
            calls.append(("save", a, kw))
            return a

        def run(self, x):
            return 7

    row = {
        "bench_id": 1743,
        "pano_id": "PANO_ID_ABCDEFGHIJKL",
        "heading": 169.0,
        "pitch": -4.0,
        "fov": 75.0,
    }
    assert vs.render_one(Ex(), row, "images") == 7
    assert calls[1] == (
        "save",
        (1743, "google:PANO_ID_ABCDEFGHIJKL", 169.0, 75.0, 4.0, "images"),
        {"kind": "suggested"},
    )
    with pytest.raises(ValueError, match="not within"):
        vs.render_one(Ex(), {**row, "pano_id": "elsewhere"}, "images")


def test_hero_outline_maps_into_the_frame_and_simplifies():
    # A dense ring around a bench in the middle of the frame.
    import math

    from bench_finder.publish.build import OUTLINE_POINTS, hero_outline

    ring = [
        [
            0.5 + 0.2 * math.cos(t / 100 * 2 * math.pi),
            0.6 + 0.1 * math.sin(t / 100 * 2 * math.pi),
        ]
        for t in range(400)
    ]
    out = hero_outline(ring)
    assert out is not None and 3 <= len(out) <= OUTLINE_POINTS
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in out)
    assert hero_outline([[0.1, 0.1], [0.2, 0.2]]) is None


def test_scenic_prefers_standing_back_along_the_facing():
    from bench_finder.scenic import scenic_score

    close_behind = scenic_score(10, 4.9, 2024)
    back_along = scenic_score(20, 13.3, 2021)
    assert back_along < close_behind
    assert scenic_score(10, 15, 2025) < scenic_score(80, 15, 2025)
    assert scenic_score(10, 15, 2025) < scenic_score(10, 60, 2025)
