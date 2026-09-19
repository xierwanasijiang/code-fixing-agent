"""ReAct 循环：思考 → 行动 → 观察，LLM 决策 → 调工具 → 观察 → 再决策。"""
from .context import Context
from .llm import parse_response
from .prompts import SYSTEM_PROMPT, THOUGHT_PROMPT, build_task
from .tools import TOOL_SCHEMAS, execute_tool


def _add_usage(tokens, response):
    """从 OpenAI 兼容响应里累加 token 用量。"""
    usage = getattr(response, "usage", None)
    if usage:
        tokens["prompt"] += getattr(usage, "prompt_tokens", 0) or 0
        tokens["completion"] += getattr(usage, "completion_tokens", 0) or 0
        tokens["total"] += getattr(usage, "total_tokens", 0) or 0


def run_agent(llm, env, instance, max_steps=15):
    ctx = Context(SYSTEM_PROMPT, build_task(instance, env.get("repo_path")))
    trace = []
    tokens = {"prompt": 0, "completion": 0, "total": 0}
    steps = 0
    while steps < max_steps:
        steps += 1

        # 1. 思考（观察 + 决策），不带工具，让模型先说推理
        ctx.add_user(THOUGHT_PROMPT)
        thought_resp = llm.chat(ctx.messages, tools=None)
        _add_usage(tokens, thought_resp)
        thought = parse_response(thought_resp).get("content") or ""
        ctx.add_assistant_text(thought)
        trace.append({"type": "thought", "step": steps, "content": thought})

        # 2. 行动：调用工具，或给出最终答案
        action_resp = llm.chat(ctx.messages, tools=TOOL_SCHEMAS)
        _add_usage(tokens, action_resp)
        parsed = parse_response(action_resp)

        if "content" in parsed:  # 模型给出最终答案
            answer = parsed["content"] or ""
            # 最终验证：跑一次验证命令，看测试是否真的通过
            test_out = execute_tool("run_test",
                                    {"test_cmd": instance["test_command"]}, env)
            success = "returncode=0" in test_out
            trace.append({"type": "final", "step": steps, "answer": answer,
                          "success": success, "verification": test_out})
            return {"success": success, "steps": steps,
                    "messages": ctx.messages, "answer": answer,
                    "trace": trace, "tokens": tokens}

        # 3. 执行工具并观察结果
        ctx.add_assistant_tool_call(parsed["tool_calls"])
        for tc in parsed["tool_calls"]:
            try:
                result = execute_tool(tc["name"], tc["arguments"], env)
            except Exception as e:
                result = f"工具执行出错：{e}"
            ctx.add_tool_result(tc["id"], result)
            trace.append({"type": "tool", "step": steps, "name": tc["name"],
                          "arguments": tc["arguments"], "result": result})

    trace.append({"type": "final", "step": steps, "answer": "达到最大步数上限",
                  "success": False, "verification": ""})
    return {"success": False, "steps": steps,
            "messages": ctx.messages, "answer": "达到最大步数上限",
            "trace": trace, "tokens": tokens}
