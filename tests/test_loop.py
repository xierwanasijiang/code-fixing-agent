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
        _resp_tool("read_file", {"path": "m.py"}),
        _resp_tool("run_test", {"test_cmd": "pytest test_m.py -q"}),
        _resp_text("已修复"),
    ])
    out = run_agent(llm, {"repo_path": str(tmp_path)},
                    {"test_command": "pytest test_m.py -q"})
    # 异常被捕获，循环继续到最终答案，整体不崩溃
    assert out["success"] is True
    tool_messages = [m for m in out["messages"] if m["role"] == "tool"]
    assert any("工具执行出错" in m["content"] for m in tool_messages)


def test_loop_collects_trace(tmp_path):
    """run_agent 应收集逐步 trace，供 UI 可视化展示。"""
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    (tmp_path / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f() == 2\n"
    )
    llm = FakeLLM([
        _resp_tool("read_file", {"path": "m.py"}),
        _resp_tool("edit_file", {"path": "m.py", "old": "return 1", "new": "return 2"}),
        _resp_tool("run_test", {"test_cmd": "pytest test_m.py -q"}),
        _resp_text("已修复"),
    ])
    out = run_agent(llm, {"repo_path": str(tmp_path)},
                    {"test_command": "pytest test_m.py -q"})
    tool_steps = [t for t in out["trace"] if t["type"] == "tool"]
    final_steps = [t for t in out["trace"] if t["type"] == "final"]
    assert len(tool_steps) == 3
    assert tool_steps[0]["name"] == "read_file"
    assert tool_steps[1]["name"] == "edit_file"
    assert tool_steps[2]["name"] == "run_test"
    assert len(final_steps) == 1
    assert final_steps[0]["success"] is True


def test_loop_accumulates_tokens(tmp_path):
    """run_agent 应累加每次调用的 token 用量（供 UI 显示花费）。"""
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
        with_usage(_resp_tool("read_file", {"path": "m.py"}), 100, 10),
        with_usage(_resp_tool("edit_file", {"path": "m.py", "old": "return 1", "new": "return 2"}), 200, 20),
        with_usage(_resp_tool("run_test", {"test_cmd": "pytest test_m.py -q"}), 300, 30),
        with_usage(_resp_text("已修复"), 400, 40),
    ])
    out = run_agent(llm, {"repo_path": str(tmp_path)},
                    {"test_command": "pytest test_m.py -q"})
    assert out["tokens"]["prompt"] == 100 + 200 + 300 + 400
    assert out["tokens"]["completion"] == 10 + 20 + 30 + 40
    assert out["tokens"]["total"] == 1100
