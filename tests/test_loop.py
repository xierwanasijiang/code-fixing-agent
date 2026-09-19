import json

from code_agent.loop import run_agent


class FakeLLM:
    """按脚本顺序返回响应：先两次工具调用，最后给最终答案。"""
    def __init__(self, script):
        self.script = script
        self.calls = []

    def chat(self, messages, tools=None, **kwargs):
        self.calls.append(messages)
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


def test_loop_reaches_success(tmp_path):
    # 一个"读文件→编辑→跑测试"的最小成功路径
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    (tmp_path / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f() == 2\n"
    )
    llm = FakeLLM([
        _resp_tool("read_file", {"path": "m.py"}),
        _resp_tool("edit_file", {"path": "m.py", "old": "return 1", "new": "return 2"}),
        _resp_tool("run_test", {"test_cmd": "pytest test_m.py -q"}),
        _resp_text("已修复，测试通过"),
    ])
    out = run_agent(llm, {"repo_path": str(tmp_path)},
                    {"test_command": "pytest test_m.py -q"})
    assert out["success"] is True
    assert out["steps"] == 4
