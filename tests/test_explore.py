"""Hero explorer: saving a framed view must never touch the bench's other views."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from bench_finder.core.pano_geometry import PanoCandidate
from bench_finder.explore import Explorer, newest_per_spot
from bench_finder.recut import job_from_row


def _db(tmp_path):
    from bench_finder.services.database import BenchDatabase

    path = tmp_path / "b.db"
    BenchDatabase(db_url=f"sqlite:///{path}")  # creates the schema
    c = sqlite3.connect(path)
    c.execute(
        "INSERT INTO images (id, bench_candidate_id, heading, filename, filepath, "
        "capture_success, kind, pano_id, camera_bearing_deg, fov_deg, image_source, created_at) "
        "VALUES (1, 7, 10, 'auto.jpg', 'images/auto.jpg', 1, 'aimed', 'P1', 10.0, 40.0, "
        "'STREETVIEW_STREETLEVEL', '2024-01-01')"
    )
    c.commit()
    c.close()
    return str(path)


def _base(name: str, aim: float, tilt: float = 0.0):
    return SimpleNamespace(
        heading=round(aim),
        filepath=f"images/{name}",
        filename=name,
        file_size=1,
        capture_success=True,
        capture_error=None,
        image_source="STREETVIEW_STREETLEVEL",
        panorama_lat=52.0,
        panorama_lng=5.0,
        panorama_metadata=None,
        panorama_heading=None,
        pano_id="P1",
        pano_date="2021-03",
        camera_bearing_deg=aim,
        camera_distance_m=12.0,
        fov_deg=30.0,
        pitch_deg=-tilt,
        kind="framed",
    )


def test_save_adds_a_framed_row_and_leaves_the_automatic_view(tmp_path):
    db = _db(tmp_path)
    ex = Explorer.__new__(Explorer)  # no event loop needed for the insert
    ex.db = db
    first = ex._insert(_base("framed_a.jpg", 160.0, 4.0), 7)
    assert first != 1
    # Re-framing from the same panorama replaces the explorer's own row only.
    second = ex._insert(_base("framed_b.jpg", 170.0), 7)
    assert second == first
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    rows = {r["id"]: dict(r) for r in c.execute("SELECT * FROM images")}
    assert len(rows) == 2
    assert rows[1]["kind"] == "aimed" and rows[1]["filename"] == "auto.jpg"
    assert rows[1]["camera_bearing_deg"] == 10.0
    assert rows[first]["filename"] == "framed_b.jpg"
    assert rows[first]["camera_bearing_deg"] == 170.0


def test_recut_reproduces_a_framed_view(tmp_path):
    db = _db(tmp_path)
    ex = Explorer.__new__(Explorer)
    ex.db = db
    iid = ex._insert(_base("framed.jpg", 160.0, tilt=6.0), 7)
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    job = job_from_row(
        dict(c.execute("SELECT * FROM images WHERE id=?", (iid,)).fetchone())
    )
    assert (job.aim_bearing_deg, job.fov_deg, job.tilt_deg) == (160.0, 30.0, 6.0)
    auto = job_from_row(dict(c.execute("SELECT * FROM images WHERE id=1").fetchone()))
    assert auto.tilt_deg == 0.0


def test_newest_city_panorama_per_spot():
    def pano(pid, lat, date):
        return PanoCandidate(
            pano_id=pid,
            lat=lat,
            lon=4.9,
            distance_m=5.0,
            bearing_deg=0.0,
            source="amsterdam",
            year=int(date[:4]),
            date_str=date,
        )

    kept = newest_per_spot(
        [
            pano("old", 52.0, "2019-05-01"),
            pano("new", 52.000005, "2024-05-01"),  # same spot, newer
            pano("other", 52.001, "2018-01-01"),  # ~110 m away
        ]
    )
    assert sorted(p.pano_id for p in kept) == ["new", "other"]
