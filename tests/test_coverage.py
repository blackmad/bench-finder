"""City coverage boxes and the tiled OSM import."""

import pytest

from bench_finder.coverage import CITIES, parse_bbox
from bench_finder.import_osm import tiles


def test_parse_bbox_names_all_and_numbers():
    assert parse_bbox("amsterdam") == CITIES["amsterdam"]
    assert parse_bbox("utrecht") == CITIES["utrecht"]
    assert parse_bbox("all") is None
    assert parse_bbox("1,2,3,4") == (1.0, 2.0, 3.0, 4.0)


def test_amsterdam_box_unchanged():
    from bench_finder.publish.build import AMSTERDAM_BBOX

    assert AMSTERDAM_BBOX == (4.62, 52.26, 5.15, 52.53)


@pytest.mark.parametrize("grid", [1, 3, 4])
def test_tiles_cover_the_box_exactly(grid):
    w, s, e, n = box = CITIES["utrecht"]
    ts = tiles(box, grid)
    assert len(ts) == grid * grid
    assert min(t[0] for t in ts) == w and min(t[1] for t in ts) == s
    assert max(t[2] for t in ts) == pytest.approx(e)
    assert max(t[3] for t in ts) == pytest.approx(n)
    area = sum((t[2] - t[0]) * (t[3] - t[1]) for t in ts)
    assert area == pytest.approx((e - w) * (n - s))
