"""Re-running a search or an image fetch must not add rows."""

import pytest
from sqlalchemy import func, select

from bench_finder.models.enums import DataSource, ImageSource
from bench_finder.models.unified_models import (
    BenchCandidate,
    Image,
    ImageBase,
    SearchBase,
)
from bench_finder.services.database import BenchDatabase


@pytest.fixture
def db(tmp_path):
    return BenchDatabase(db_url=f"sqlite:///{tmp_path / 'test.db'}")


def _count(db, model):
    with db.get_session() as session:
        return session.execute(select(func.count()).select_from(model)).scalar_one()


def _search(db):
    return db.create_search(
        SearchBase(query="q", start_lat=52.0, start_lng=4.0, search_radius=100)
    )


def _add_candidate(db, search_id, **kw):
    args = {
        "search_id": search_id,
        "provider_id": "123_node",
        "lat": 52.0,
        "lng": 4.0,
        "tags": {"amenity": "bench"},
        "source": DataSource.OSM,
        "external_id": "123",
    }
    args.update(kw)
    return db.add_bench_candidate(**args)


def test_add_bench_candidate_twice_adds_no_rows(db):
    search_id = _search(db)
    first = _add_candidate(db, search_id)
    assert first is not None
    assert _count(db, BenchCandidate) == 1

    second = _add_candidate(db, search_id, tags={"amenity": "bench", "backrest": "yes"})
    assert second == first
    assert _count(db, BenchCandidate) == 1
    with db.get_session() as session:
        assert session.get(BenchCandidate, first).tags["backrest"] == "yes"


def test_add_bench_candidate_from_new_search_reuses_row(db):
    first = _add_candidate(db, _search(db))
    assert _add_candidate(db, _search(db)) == first
    assert _count(db, BenchCandidate) == 1


def test_provider_id_is_unique_in_schema(db):
    from sqlalchemy.exc import IntegrityError

    search_id = _search(db)
    _add_candidate(db, search_id)
    with db.get_session() as session, pytest.raises(IntegrityError):
        session.add(
            BenchCandidate(search_id=search_id, provider_id="123_node", lat=1, lng=1)
        )
        session.commit()


def test_add_image_twice_adds_no_rows(db):
    cand = _add_candidate(db, _search(db))

    def image(size):
        return ImageBase(
            heading=0,
            filepath="images/a.jpg",
            filename="a.jpg",
            file_size=size,
            capture_success=True,
            image_source=ImageSource.STREETVIEW_STREETLEVEL,
        )

    first = db.add_image(image(100), cand)
    second = db.add_image(image(200), cand)
    assert first == second
    assert _count(db, Image) == 1
    with db.get_session() as session:
        assert session.get(Image, first).file_size == 200

    # A different view (filename) is a new row.
    other = image(1)
    other.filename = "b.jpg"
    db.add_image(other, cand)
    assert _count(db, Image) == 2
