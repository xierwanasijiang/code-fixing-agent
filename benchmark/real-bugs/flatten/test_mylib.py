from mylib import flatten


def test_flatten_deep():
    assert flatten([1, [2, [3, 4]]]) == [1, 2, 3, 4]
