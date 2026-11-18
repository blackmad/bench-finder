from bench_finder.publish.exclude import at_stops


def test_at_stops_uses_metres():
    stops = [(52.37, 4.89)]
    benches = [(1, 52.37005, 4.89), (2, 52.3702, 4.89)]  # ~5.6 m and ~22 m north
    assert at_stops(benches, stops) == {1}


def test_on_platforms_measures_to_the_outline(tmp_path):
    import json

    from bench_finder.publish.exclude import on_platforms

    line = [
        {"lat": 52.37, "lon": 4.89},
        {"lat": 52.37, "lon": 4.895},
    ]  # ~340 m east-west
    f = tmp_path / "p.json"
    f.write_text(
        json.dumps({"elements": [{"type": "way", "tags": {}, "geometry": line}]})
    )
    benches = [(1, 52.37004, 4.8925), (2, 52.3702, 4.8925)]  # mid-platform: ~4 m, ~22 m
    assert on_platforms(benches, f) == {1}
    f.write_text(
        json.dumps(
            {"elements": [{"type": "way", "tags": {"tram": "yes"}, "geometry": line}]}
        )
    )
    assert on_platforms(benches, f) == set()
