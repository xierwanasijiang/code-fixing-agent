from code_agent.llm import LLMClient, parse_response


def test_parse_response_with_tool_calls():
    class Msg:
        tool_calls = [
            type("TC", (), {
                "id": "call_1",
                "function": type("F", (), {
                    "name": "read_file",
                    "arguments": '{"path": "src/a.py"}',
                })(),
            })(),
        ]
        content = None

    class Choice:
        message = Msg()

    class Resp:
        choices = [Choice()]

    out = parse_response(Resp())
    assert out["tool_calls"] == [
        {"id": "call_1", "name": "read_file", "arguments": {"path": "src/a.py"}}
    ]


def test_parse_response_with_plain_text():
    class Msg:
        tool_calls = None
        content = "修复完成"

    class Choice:
        message = Msg()

    class Resp:
        choices = [Choice()]

    out = parse_response(Resp())
    assert out["content"] == "修复完成"
