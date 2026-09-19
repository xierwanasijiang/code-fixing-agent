from code_agent.context import Context


def test_context_starts_with_system_and_user():
    ctx = Context("你是工程师", "修一个 bug")
    assert ctx.messages == [
        {"role": "system", "content": "你是工程师"},
        {"role": "user", "content": "修一个 bug"},
    ]


def test_tool_call_roundtrip():
    ctx = Context("s", "t")
    ctx.add_assistant_tool_call([{"id": "c1", "name": "read_file",
                                  "arguments": {"path": "a.py"}}])
    ctx.add_tool_result("c1", "文件内容...")
    assert ctx.messages[-2]["role"] == "assistant"
    assert ctx.messages[-2]["tool_calls"][0]["function"]["name"] == "read_file"
    assert ctx.messages[-1]["role"] == "tool"
    assert ctx.messages[-1]["tool_call_id"] == "c1"


def test_tool_result_truncates():
    ctx = Context("s", "t")
    ctx.add_tool_result("c1", "x" * 10000)
    assert len(ctx.messages[-1]["content"]) <= 6000
