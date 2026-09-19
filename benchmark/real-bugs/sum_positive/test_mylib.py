from mylib import sum_positive


def test_only_sums_positives():
    assert sum_positive([1, -2, 3]) == 4
    assert sum_positive([-1, -2]) == 0
