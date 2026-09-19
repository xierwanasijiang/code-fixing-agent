"""DeepSeek（OpenAI 兼容）客户端与工具调用响应解析。"""
import json
import os
import time

from openai import OpenAI


class LLMClient:
    def __init__(self, model="deepseek-chat", api_key=None,
                 base_url="https://api.deepseek.com"):
        api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("未设置 DEEPSEEK_API_KEY 环境变量")
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages, tools=None, temperature=0.0, max_tokens=4096, retries=3):
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
        for attempt in range(retries):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)  # 1s, 2s 退避重试


def parse_response(response):
    """把 OpenAI 响应解析成统一结构。"""
    msg = response.choices[0].message
    if msg.tool_calls:
        return {
            "tool_calls": [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
                for tc in msg.tool_calls
            ]
        }
    return {"content": msg.content}
