from mylib import range_inclusive


def test_includes_both_ends():
    assert range_inclusive(1, 3) == [1, 2, 3]
