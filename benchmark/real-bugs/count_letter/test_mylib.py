from mylib import count_letter


def test_count_case_insensitive():
    assert count_letter('Hello', 'h') == 1
    assert count_letter('Hello', 'L') == 2
