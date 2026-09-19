import json

from code_agent.loop import run_agent


class FakeLLM:
    """按脚本顺序返回响应：思考(文本) 与 行动(工具调用/最终答案) 交替。"""
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
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    (tmp_path / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f() == 2\n"
    )
    llm = FakeLLM([
        _resp_text("观察：还没看代码。决策：读 m.py"),
        _resp_tool("read_file", {"path": "m.py"}),
        _resp_text("观察：f 返回 1 但测试要 2。决策：改成返回 2"),
        _resp_tool("edit_file", {"path": "m.py", "old": "return 1", "new": "return 2"}),
        _resp_text("观察：已改。决策：跑测试验证"),
        _resp_tool("run_test", {"test_cmd": "pytest test_m.py -q"}),
        _resp_text("观察：测试通过。决策：结束"),
        _resp_text("已修复，测试通过"),
    ])
    out = run_agent(llm, {"repo_path": str(tmp_path)},
                    {"test_command": "pytest test_m.py -q"})
    assert out["success"] is True
    assert out["steps"] == 4


def test_loop_survives_tool_exception(tmp_path, monkeypatch):
    """工具抛异常时，run_agent 应把错误作为 observation 回传，而不是崩溃。"""
    import code_agent.loop as loop_mod
    from code_agent.tools import execute_tool as real_execute

    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    (tmp_path / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f() == 1\n"
    )

    def flaky(name, args, env):
        if name == "read_file":
            raise RuntimeError("boom")
        return real_execute(name, args, env)

    monkeypatch.setattr(loop_mod, "execute_tool", flaky)

    llm = FakeLLM([
        _resp_text("观察：读代码。决策：读 m.py"),
        _resp_tool("read_file", {"path": "m.py"}),
        _resp_text("观察：读失败但继续。决策：跑测试"),
        _resp_tool("run_test", {"test_cmd": "pytest test_m.py -q"}),
        _resp_text("观察：测试通过。决策：结束"),
        _resp_text("已修复"),
    ])
    out = run_agent(llm, {"repo_path": str(tmp_path)},
                    {"test_command": "pytest test_m.py -q"})
    assert out["success"] is True
    tool_messages = [m for m in out["messages"] if m["role"] == "tool"]
    assert any("工具执行出错" in m["content"] for m in tool_messages)


def test_loop_collects_trace(tmp_path):
    """run_agent 应收集逐步 trace（含思考/工具/最终），供 UI 可视化展示。"""
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    (tmp_path / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f() == 2\n"
    )
    llm = FakeLLM([
        _resp_text("t1"),
        _resp_tool("read_file", {"path": "m.py"}),
        _resp_text("t2"),
        _resp_tool("edit_file", {"path": "m.py", "old": "return 1", "new": "return 2"}),
        _resp_text("t3"),
        _resp_tool("run_test", {"test_cmd": "pytest test_m.py -q"}),
        _resp_text("t4"),
        _resp_text("已修复"),
    ])
    out = run_agent(llm, {"repo_path": str(tmp_path)},
                    {"test_command": "pytest test_m.py -q"})
    tool_steps = [t for t in out["trace"] if t["type"] == "tool"]
    thought_steps = [t for t in out["trace"] if t["type"] == "thought"]
    final_steps = [t for t in out["trace"] if t["type"] == "final"]
    assert len(tool_steps) == 3
    assert tool_steps[0]["name"] == "read_file"
    assert len(thought_steps) == 4
    assert len(final_steps) == 1
    assert final_steps[0]["success"] is True


def test_loop_accumulates_tokens(tmp_path):
    """run_agent 应累加每次调用（含思考）的 token 用量。"""
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    (tmp_path / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f() == 2\n"
    )

    def with_usage(resp, pt, ct):
        resp.usage = type("U", (), {
            "prompt_tokens": pt, "completion_tokens": ct,
            "total_tokens": pt + ct,
        })()
        return resp

    llm = FakeLLM([
        with_usage(_resp_text("t1"), 10, 1),
        with_usage(_resp_tool("read_file", {"path": "m.py"}), 100, 10),
        with_usage(_resp_text("t2"), 20, 2),
        with_usage(_resp_tool("edit_file", {"path": "m.py", "old": "return 1", "new": "return 2"}), 200, 20),
        with_usage(_resp_text("t3"), 30, 3),
        with_usage(_resp_tool("run_test", {"test_cmd": "pytest test_m.py -q"}), 300, 30),
        with_usage(_resp_text("t4"), 40, 4),
        with_usage(_resp_text("已修复"), 400, 40),
    ])
    out = run_agent(llm, {"repo_path": str(tmp_path)},
                    {"test_command": "pytest test_m.py -q"})
    assert out["tokens"]["prompt"] == 1100
    assert out["tokens"]["completion"] == 110
    assert out["tokens"]["total"] == 1210
