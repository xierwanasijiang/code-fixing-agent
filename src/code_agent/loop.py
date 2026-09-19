"""ReAct 循环：LLM 决策 → 调工具 → 观察 → 再决策。"""
from .context import Context
from .llm import parse_response
from .prompts import SYSTEM_PROMPT, build_task
from .tools import TOOL_SCHEMAS, execute_tool


def run_agent(llm, env, instance, max_steps=15):
    ctx = Context(SYSTEM_PROMPT, build_task(instance, env.get("repo_path")))
    trace = []
    steps = 0
    while steps < max_steps:
        steps += 1
        response = llm.chat(ctx.messages, tools=TOOL_SCHEMAS)
        parsed = parse_response(response)

        if "content" in parsed:  # 模型给出最终答案
            answer = parsed["content"] or ""
            # 最终验证：跑一次验证命令，看测试是否真的通过
            test_out = execute_tool("run_test",
                                    {"test_cmd": instance["test_command"]}, env)
            success = "returncode=0" in test_out
            trace.append({"type": "final", "step": steps, "answer": answer,
                          "success": success, "verification": test_out})
            return {"success": success, "steps": steps,
                    "messages": ctx.messages, "answer": answer, "trace": trace}

        # 按 OpenAI 工具调用协议回传：assistant.tool_calls + role:"tool"
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
            "messages": ctx.messages, "answer": "达到最大步数上限", "trace": trace}
