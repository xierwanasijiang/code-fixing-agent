from code_agent.snippet import extract_code_block


def test_extract_code_block():
    text = "bug 原因是 xxx\n```python\ndef f():\n    return 1\n```"
    assert extract_code_block(text) == "def f():\n    return 1"


def test_extract_code_block_without_lang():
    text = "```\ndef g():\n    pass\n```"
    assert extract_code_block(text) == "def g():\n    pass"


def test_extract_no_block_returns_original():
    assert extract_code_block("没有代码块，直接返回原文") == "没有代码块，直接返回原文"
