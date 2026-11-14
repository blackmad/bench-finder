"""Unit tests for panorama enumeration rules and aimed-view geometry (tasks 2.1-2.2)."""

import itertools

import pytest

from bench_finder.core.pano_geometry import (
    PanoCandidate,
    angular_diff_deg,
    bearing_deg,
    ccw_to_cw_heading,
    filter_candidates,
    haversine_m,
    select_views,
)


def cand(pano_id, bearing, distance=10.0, year=2022, month=6, **kw):
    return PanoCandidate(
        pano_id=pano_id,
        lat=0.0,
        lon=0.0,
        distance_m=distance,
        bearing_deg=bearing,
        source="google",
        year=year,
        month=month,
        **kw,
    )


# ------------------------------------------------------------------ basic geometry


def test_bearing_cardinals():
    assert bearing_deg(0, 0, 1, 0) == pytest.approx(0, abs=1e-6)
    assert bearing_deg(0, 0, 0, 1) == pytest.approx(90, abs=1e-6)
    assert bearing_deg(0, 0, -1, 0) == pytest.approx(180, abs=1e-6)
    assert bearing_deg(0, 0, 0, -1) == pytest.approx(270, abs=1e-6)


def test_haversine_one_degree_latitude():
    assert haversine_m(0, 0, 1, 0) == pytest.approx(111_195, rel=1e-3)


def test_angular_diff_wraps():
    assert angular_diff_deg(350, 10) == 20
    assert angular_diff_deg(0, 180) == 180
    assert angular_diff_deg(90, 90) == 0


def test_ccw_to_cw():
    assert ccw_to_cw_heading(90) == 270
    assert ccw_to_cw_heading(0) == 0
    assert ccw_to_cw_heading(270) == 90


# ---------------------------------------------------------------- filtering rules


def test_filter_distance_window():
    kept = filter_candidates(
        [
            cand("near", 0, distance=3.9),
            cand("ok", 0, distance=4.0),
            cand("far", 0, distance=30.1),
        ]
    )
    assert [c.pano_id for c in kept] == ["ok"]


def test_filter_drops_third_party_and_indoor():
    kept = filter_candidates(
        [
            cand("good", 0),
            cand("tp", 10, is_third_party=True),
            cand("in", 20, is_indoor_meta=True),
        ]
    )
    assert [c.pano_id for c in kept] == ["good"]


def test_filter_drops_pre_2016_only_when_newer_exists():
    old = cand("old", 0, year=2012)
    new = cand("new", 90, year=2021)
    assert [c.pano_id for c in filter_candidates([old, new])] == ["new"]
    # Only old coverage available: keep it.
    assert [c.pano_id for c in filter_candidates([old])] == ["old"]
    # 2016 itself counts as recent.
    assert (
        len(filter_candidates([cand("a", 0, year=2016), cand("b", 90, year=2016)])) == 2
    )


def test_filter_pre_2016_checked_after_other_rules():
    # The only newer pano is too close, so it must not cause the old one to be dropped.
    kept = filter_candidates(
        [cand("old", 0, year=2012), cand("new", 90, year=2021, distance=2.0)]
    )
    assert [c.pano_id for c in kept] == ["old"]


def test_filter_collapses_duplicate_ids():
    assert len(filter_candidates([cand("a", 0), cand("a", 0)])) == 1


# ---------------------------------------------------------------- sector selection


def test_select_one_per_sector_prefers_newest():
    cands = [
        cand("a_old", 10, year=2018),
        cand("a_new", 20, year=2024),  # same 0-60 sector, newer
        cand("b", 100, year=2019),
        cand("c", 200, year=2020),
    ]
    picked = {c.pano_id for c in select_views(cands)}
    assert "a_new" in picked
    assert "a_old" not in picked  # 10 deg from a_new: below the fill separation
    assert {"b", "c"} <= picked


def test_select_tie_breaks_on_distance():
    cands = [
        cand("far", 10, distance=25, year=2022),
        cand("close", 20, distance=8, year=2022),
    ]
    assert select_views(cands, max_views=1)[0].pano_id == "close"


def test_select_caps_at_six_across_sectors():
    cands = [cand(f"p{i}", i * 12.0) for i in range(30)]  # 0..348 deg
    picked = select_views(cands)
    assert len(picked) == 6
    sectors = {int(c.bearing_deg // 60) for c in picked}
    assert sectors == {0, 1, 2, 3, 4, 5}


def test_select_spreads_rather_than_clustering():
    # Lots of panoramas clustered in one sector plus one on the opposite side.
    cands = [cand(f"c{i}", 5 + i * 3.0, year=2024) for i in range(8)] + [
        cand("opp", 200, year=2015)
    ]
    picked = select_views(cands)
    assert "opp" in picked_ids(picked)
    # Cluster members only fill extra slots when 20 deg apart.
    bearings = sorted(c.bearing_deg for c in picked)
    for a, b in itertools.pairwise(bearings):
        assert angular_diff_deg(a, b) >= 20 or {a, b} & {200}


def picked_ids(picked):
    return {c.pano_id for c in picked}


def test_select_fill_pass_adds_distinct_bearings_in_same_sector():
    # Both in sector 0 but 40 deg apart: the second fills a spare slot.
    cands = [cand("x", 2), cand("y", 45)]
    assert picked_ids(select_views(cands)) == {"x", "y"}


def test_select_empty_and_single():
    assert select_views([]) == []
    assert [c.pano_id for c in select_views([cand("only", 123)])] == ["only"]


def test_select_output_sorted_by_bearing():
    cands = [cand("a", 300), cand("b", 10), cand("c", 150)]
    assert [c.bearing_deg for c in select_views(cands)] == [10, 150, 300]
