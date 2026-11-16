from bench_finder.core.pano_geometry import PanoCandidate
from bench_finder.vantage import Bench, choose, fov_for, score


def _c(pid, bearing, d, year=2024, source="google"):
    return PanoCandidate(
        pano_id=pid,
        lat=0,
        lon=0,
        distance_m=d,
        bearing_deg=bearing,
        source=source,
        year=year,
    )


B = Bench(1, 52.37, 4.9, facing=90.0, water=False, have=frozenset({"old"}))
W = Bench(2, 52.37, 4.9, facing=90.0, water=True, have=frozenset())


def test_behind_beats_front_beats_side():
    behind, front, side = _c("b", 90, 10), _c("f", 270, 10), _c("s", 0, 10)
    assert score(behind, B) > score(front, B)
    assert score(side, B) is None


def test_far_front_view_only_for_water():
    far_front = _c("x", 270, 45)
    assert score(far_front, B) is None
    assert score(far_front, W) is not None
    assert score(_c("y", 90, 45), W) is None  # far behind: still capped at 30 m


def test_choose_one_per_side_and_skips_known_panos():
    cands = [_c("old", 90, 8), _c("b1", 95, 9), _c("b2", 85, 7), _c("f1", 260, 12)]
    ids = [c.pano_id for c in choose(cands, B)]
    assert ids[1] == "f1" and ids[0] in {"b1", "b2"}


def test_fov_narrows_with_distance():
    assert 70 < fov_for(4) < 80
    assert fov_for(45) == 18.0
