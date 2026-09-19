from mylib import count_vowels


def test_vowels_uppercase():
    assert count_vowels("AEIOU") == 5
