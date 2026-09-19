from mylib import first_even


def test_no_even_returns_none():
    assert first_even([1, 3, 5]) is None
