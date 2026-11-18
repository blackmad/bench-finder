from bench_finder.publish.exclude import at_stops


def test_at_stops_uses_metres():
    stops = [(52.37, 4.89)]
    benches = [(1, 52.37005, 4.89), (2, 52.3702, 4.89)]  # ~5.6 m and ~22 m north
    assert at_stops(benches, stops) == {1}
