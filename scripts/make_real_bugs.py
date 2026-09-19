"""生成一批「真实世界的 bug 模式」，用于评测 agent vs 基线。

每个 bug 都是现实代码里反复出现的典型错误，配一条会失败的测试。
"""
from pathlib import Path

BUGS = {
    "add_to_list": {
        "code": "def add_to_list(item, lst=[]):\n    lst.append(item)\n    return lst\n",
        "test": "from mylib import add_to_list\n\n\ndef test_fresh_list_each_call():\n    assert add_to_list(1) == [1]\n    assert add_to_list(2) == [2]\n",
    },
    "dedup": {
        "code": "def dedup(items):\n    return list(set(items))\n",
        "test": "from mylib import dedup\n\n\ndef test_dedup_keeps_order():\n    assert dedup([3, 1, 3, 2, 1]) == [3, 1, 2]\n",
    },
    "count_letter": {
        "code": "def count_letter(s, letter):\n    return s.count(letter)\n",
        "test": "from mylib import count_letter\n\n\ndef test_count_case_insensitive():\n    assert count_letter('Hello', 'h') == 1\n    assert count_letter('Hello', 'L') == 2\n",
    },
    "range_inclusive": {
        "code": "def range_inclusive(a, b):\n    return list(range(a, b))\n",
        "test": "from mylib import range_inclusive\n\n\ndef test_includes_both_ends():\n    assert range_inclusive(1, 3) == [1, 2, 3]\n",
    },
    "fib": {
        "code": "def fib(n):\n    if n == 0:\n        return 0\n    return fib(n - 1) + fib(n - 2)\n",
        "test": "from mylib import fib\n\n\ndef test_fib_small():\n    assert fib(1) == 1\n    assert fib(5) == 5\n",
    },
    "sum_positive": {
        "code": "def sum_positive(nums):\n    return sum(nums)\n",
        "test": "from mylib import sum_positive\n\n\ndef test_only_sums_positives():\n    assert sum_positive([1, -2, 3]) == 4\n    assert sum_positive([-1, -2]) == 0\n",
    },
    "flatten": {
        "code": "def flatten(nested):\n    result = []\n    for item in nested:\n        if isinstance(item, list):\n            result.extend(item)\n        else:\n            result.append(item)\n    return result\n",
        "test": "from mylib import flatten\n\n\ndef test_flatten_deep():\n    assert flatten([1, [2, [3, 4]]]) == [1, 2, 3, 4]\n",
    },
    "first_even": {
        "code": "def first_even(nums):\n    for n in nums:\n        if n % 2 == 0:\n            return n\n    return 0\n",
        "test": "from mylib import first_even\n\n\ndef test_no_even_returns_none():\n    assert first_even([1, 3, 5]) is None\n",
    },
}


def main():
    base = Path(__file__).resolve().parent.parent / "benchmark" / "real-bugs"
    for name, b in BUGS.items():
        d = base / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "mylib.py").write_text(b["code"], encoding="utf-8")
        (d / "test_mylib.py").write_text(b["test"], encoding="utf-8")
    print(f"已生成 {len(BUGS)} 个真实 bug 到 {base}")


if __name__ == "__main__":
    main()
