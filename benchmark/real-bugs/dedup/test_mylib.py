from mylib import dedup


def test_dedup_keeps_order():
    assert dedup([3, 1, 3, 2, 1]) == [3, 1, 2]
