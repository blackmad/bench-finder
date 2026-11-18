from bench_finder.hero_fade import frame_box


def test_small_off_centre_bench_is_centred_and_zoomed():
    cx, cy, side = frame_box([(0.75, 0.80), (0.85, 0.80), (0.85, 0.88), (0.75, 0.88)])
    assert side == 0.45  # bench 10% wide: zoom capped at the minimum crop
    assert cx == 1 - side / 2 and cy == 1 - side / 2  # pushed as far as the edge allows


def test_big_centred_bench_keeps_the_full_frame():
    assert frame_box([(0.05, 0.3), (0.95, 0.3), (0.95, 0.7), (0.05, 0.7)]) is None


def test_recut_is_not_zoomed_again():
    # A small bench in a re-aimed cut: centre it at most, never crop below 85%.
    _, _, side = frame_box(
        [(0.45, 0.6), (0.55, 0.6), (0.55, 0.66), (0.45, 0.66)], recut=True
    )
    assert side >= 0.85
