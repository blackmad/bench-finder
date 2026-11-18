import math

from bench_finder.triangulate import Ray, solve


def _ray(x, y, tx, ty, pano):
    """A ray from (x, y) towards (tx, ty)."""
    return Ray(x, y, math.degrees(math.atan2(tx - x, ty - y)) % 360, 0.9, pano)


def test_three_cameras_find_the_bench():
    bench = (3.0, 4.0)
    rays = [
        _ray(-10, 0, *bench, "a"),
        _ray(10, -5, *bench, "b"),
        _ray(0, 15, *bench, "c"),
    ]
    s = solve(rays)
    assert s and abs(s["dx"] - 3) < 0.01 and abs(s["dy"] - 4) < 0.01
    assert s["rays"] == 3


def test_cameras_facing_each_other_cannot_fix_a_point():
    # Across a canal, looking at each other: the rays are one line.
    rays = [
        _ray(-15, 0, 15, 0.2, "a"),
        _ray(15, 0, -15, 0.1, "b"),
        _ray(-20, 0, 20, 0, "c"),
    ]
    assert solve(rays) is None


def test_odd_ray_out_is_ignored():
    bench = (2.0, -1.0)
    rays = [
        _ray(-10, 0, *bench, "a"),
        _ray(10, -5, *bench, "b"),
        _ray(0, 15, *bench, "c"),
        _ray(5, 10, 9, 20, "d"),  # saw something else
    ]
    s = solve(rays)
    assert s and s["rays"] == 3 and s["of"] == 4
