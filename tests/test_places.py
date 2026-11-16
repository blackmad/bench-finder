from bench_finder.publish.places import group_places, metres


LAT = 52.372
M_LAT = 1 / 111_320  # degrees per metre north


def _row(n: int, spacing_m: float, start: int = 1):
    return [(start + k, LAT + k * spacing_m * M_LAT, 4.893) for k in range(n)]


def test_rokin_benches_are_one_place():
    # The six "Rokin 18-A" OSM nodes: two rows of three, ~15 m by ~8 m.
    rokin = [
        (5596, 52.372109, 4.893063),
        (5597, 52.372043, 4.893065),
        (5598, 52.371977, 4.893058),
        (5599, 52.372078, 4.893179),
        (5600, 52.372037, 4.893166),
        (5601, 52.371998, 4.893155),
    ]
    assert [sorted(p) for p in group_places(rokin)] == [
        [5596, 5597, 5598, 5599, 5600, 5601]
    ]


def test_triple_is_one_place_and_seed_first():
    benches = [(9, LAT, 4.893717), (8, LAT, 4.893762), (7, LAT, 4.89367)]
    (place,) = group_places(benches)
    assert place[0] == 9 and sorted(place) == [7, 8, 9]


def test_promenade_splits_and_no_place_is_wider_than_25m():
    benches = _row(10, 8)  # 72 m at 8 m spacing would chain into one
    places = group_places(benches)
    pos = {i: (lat, lng) for i, lat, lng in benches}
    assert len(places) > 1
    assert sorted(i for p in places for i in p) == list(range(1, 11))
    for p in places:
        assert all(metres(pos[a], pos[b]) <= 25 for a in p for b in p)


def test_far_benches_stay_apart():
    assert group_places([(1, LAT, 4.893), (2, LAT + 20 * M_LAT, 4.893)]) == [[1], [2]]
