from mylib import fib


def test_fib_small():
    assert fib(1) == 1
    assert fib(5) == 5
