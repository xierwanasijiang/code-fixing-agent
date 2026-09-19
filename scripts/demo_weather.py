"""阶段 0 demo：让模型调用一个 get_weather 工具，体会 function calling 的完整闭环。"""
import json
import os

from code_agent.llm import LLMClient, parse_response

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某城市今天的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 Beijing"}
                },
                "required": ["city"],
            },
        },
    }
]


def get_weather(city: str) -> str:
    return f"{city} 今天晴，25 摄氏度"


def main():
    client = LLMClient()
    messages = [{"role": "user", "content": "北京今天天气怎么样？"}]
    # 第一轮：模型应返回 tool_call
    resp = client.chat(messages, tools=TOOLS)
    parsed = parse_response(resp)
    print("第一轮响应:", parsed)
    # 第二轮：把工具结果回传，模型应给出最终答案
    messages.append({
        "role": "assistant",
        "tool_calls": [
            {"id": tc["id"], "type": "function",
             "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"], ensure_ascii=False)}}
            for tc in parsed["tool_calls"]
        ],
    })
    for tc in parsed["tool_calls"]:
        result = get_weather(**tc["arguments"])
        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    resp2 = client.chat(messages, tools=TOOLS)
    print("第二轮响应:", parse_response(resp2))


if __name__ == "__main__":
    main()
