"""上下文（消息列表）管理，遵循 OpenAI 工具调用协议，控制 token 增长。"""
import json

MAX_OBSERVATION_CHARS = 6000


class Context:
    def __init__(self, system_prompt, task):
        self._messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

    @property
    def messages(self):
        return self._messages

    def add_user(self, text):
        """追加一条用户消息（如引导思考的提问）。"""
        self._messages.append({"role": "user", "content": text})

    def add_assistant_text(self, text):
        """追加一条助手纯文本消息（如思考内容）。"""
        self._messages.append({"role": "assistant", "content": text})

    def add_assistant_tool_call(self, tool_calls):
        """追加模型发起的工具调用（assistant 角色 + tool_calls）。"""
        self._messages.append({
            "role": "assistant",
            "tool_calls": [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"],
                              "arguments": json.dumps(tc["arguments"], ensure_ascii=False)}}
                for tc in tool_calls
            ],
        })

    def add_tool_result(self, tool_call_id, result):
        """追加某次工具调用的结果（tool 角色），超长自动截断。"""
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(result)[:MAX_OBSERVATION_CHARS],
        })
