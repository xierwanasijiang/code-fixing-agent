from calc import divide


def test_divide_by_zero():
    # 期望除以 0 返回 None，而不是抛异常
    assert divide(1, 0) is None
