from mylib import add_to_list


def test_fresh_list_each_call():
    assert add_to_list(1) == [1]
    assert add_to_list(2) == [2]
