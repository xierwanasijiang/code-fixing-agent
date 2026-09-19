import json

from code_agent.snippet import extract_code_block, run_snippet_agent


def test_extract_code_block():
    text = "bug 原因是 xxx\n```python\ndef f():\n    return 1\n```"
    assert extract_code_block(text) == "def f():\n    return 1"


def test_extract_code_block_without_lang():
    text = "```\ndef g():\n    pass\n```"
    assert extract_code_block(text) == "def g():\n    pass"


def test_extract_no_block_returns_original():
    assert extract_code_block("没有代码块，直接返回原文") == "没有代码块，直接返回原文"


class FakeLLM:
    def __init__(self, script):
        self.script = script

    def chat(self, messages, tools=None, **kwargs):
        return self.script.pop(0)


def _resp_tool(name, args):
    return type("R", (), {"choices": [type("C", (), {
        "message": type("M", (), {
            "tool_calls": [type("T", (), {
                "id": "c1", "function": type("F", (), {
                    "name": name, "arguments": json.dumps(args),
                })(),
            })()],
            "content": None,
        })(),
    })()]})()


def _resp_text(text):
    return type("R", (), {"choices": [type("C", (), {
        "message": type("M", (), {"tool_calls": None, "content": text})(),
    })()]})()


def test_run_snippet_agent_fixes_code():
    """agent 用 run_snippet 真运行验证，最终返回修复后的代码。"""
    fixed_code = "def f():\n    return 2\n"
    llm = FakeLLM([
        _resp_text("观察：函数返回 1。决策：改成返回 2 并运行验证"),
        _resp_tool("run_snippet", {"code": fixed_code}),
        _resp_text("观察：运行成功。决策：结束"),
        _resp_text("修复完成，函数现在返回 2"),
    ])
    out = run_snippet_agent(llm, "def f():\n    return 1\n", "测试期望返回 2")
    assert out["success"] is True
    assert out["fixed_code"] == fixed_code
    tool_steps = [t for t in out["trace"] if t["type"] == "tool"]
    thought_steps = [t for t in out["trace"] if t["type"] == "thought"]
    assert len(tool_steps) == 1
    assert tool_steps[0]["name"] == "run_snippet"
    assert len(thought_steps) == 2


def test_run_snippet_agent_keeps_failing_code_out():
    """若最后一次运行失败，fixed_code 应为空（不把坏代码当修复结果）。"""
    llm = FakeLLM([
        _resp_text("观察：代码除零。决策：先运行看报错"),
        _resp_tool("run_snippet", {"code": "1 / 0\n"}),
        _resp_text("观察：还是除零。决策：结束"),
        _resp_text("还没修好"),
    ])
    out = run_snippet_agent(llm, "1 / 0\n", "除零错误")
    assert out["success"] is False
    assert out["fixed_code"] == ""
