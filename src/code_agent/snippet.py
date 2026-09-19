"""粘贴代码片段修复：让 agent 用「运行验证」的方式真调试一段报错代码。

与仓库修复共用同一套 ReAct 循环思路，只是工具不同：
仓库修复用 read/edit/run_test 操作文件，这里用 run_snippet 直接执行代码验证。
"""
import re
import subprocess
import sys

from .context import Context
from .llm import parse_response
from .prompts import THOUGHT_PROMPT


def extract_code_block(text):
    """从回答里提取 ```python ... ``` 代码块，找不到则原样返回。"""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _usage_of(response):
    usage = getattr(response, "usage", None)
    if not usage:
        return {"prompt": 0, "completion": 0, "total": 0}
    return {
        "prompt": getattr(usage, "prompt_tokens", 0) or 0,
        "completion": getattr(usage, "completion_tokens", 0) or 0,
        "total": getattr(usage, "total_tokens", 0) or 0,
    }


def _run_snippet(code: str, timeout: int = 20) -> str:
    """真的执行一段 Python 代码，返回运行结果或报错。"""
    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        out = f"returncode={r.returncode}\n"
        if r.stdout:
            out += f"[stdout]\n{r.stdout[-3000:]}"
        if r.stderr:
            out += f"[stderr]\n{r.stderr[-3000:]}"
        return out
    except subprocess.TimeoutExpired:
        return "运行超时（>20 秒），代码可能有死循环"


SNIPPET_TOOL_SCHEMA = [{
    "type": "function",
    "function": {
        "name": "run_snippet",
        "description": "执行你修复后的完整 Python 代码，返回运行结果或报错。用来验证修复是否成功。",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "修复后的完整 Python 代码"},
            },
            "required": ["code"],
        },
    },
}]

SNIPPET_SYSTEM_PROMPT = (
    "你是代码修复专家。给定一段报错的 Python 代码，你要反复迭代直到修复成功：\n"
    "1. 思考：分析 bug 原因、决定下一步怎么做；\n"
    "2. 行动：用 run_snippet 工具运行你修复后的【完整代码】来验证；\n"
    "3. 观察：查看运行结果，若仍报错就继续修改。\n"
    "注意：每次 run_snippet 都要传【完整代码】，不要省略。最后用一句话总结你改了什么。"
)


def run_snippet_agent(llm, code, error, max_steps=8):
    """让 agent 用「运行验证」真调试一段报错代码，返回修复后代码与决策日志。"""
    task = (
        f"【原始代码】\n```python\n{code}\n```\n\n"
        f"【报错信息 / 期望行为】\n{error}\n\n"
        f"请修复这段代码，并用 run_snippet 验证修复后的完整代码能正常运行。"
    )
    ctx = Context(SNIPPET_SYSTEM_PROMPT, task)
    trace = []
    tokens = {"prompt": 0, "completion": 0, "total": 0}
    last_good_code = None
    last_run_ok = False
    steps = 0

    while steps < max_steps:
        steps += 1

        # 1. 思考
        ctx.add_user(THOUGHT_PROMPT)
        thought_resp = llm.chat(ctx.messages, tools=None)
        u = _usage_of(thought_resp)
        for k in tokens:
            tokens[k] += u[k]
        thought = parse_response(thought_resp).get("content") or ""
        ctx.add_assistant_text(thought)
        trace.append({"type": "thought", "step": steps, "content": thought})

        # 2. 行动
        action_resp = llm.chat(ctx.messages, tools=SNIPPET_TOOL_SCHEMA)
        u = _usage_of(action_resp)
        for k in tokens:
            tokens[k] += u[k]
        parsed = parse_response(action_resp)

        if "content" in parsed:  # 模型给出最终总结
            answer = parsed["content"] or ""
            if last_good_code is not None:
                fixed = last_good_code
            else:
                # 没成功运行过代码：只接受回答里明确的代码块，没有则视为无修复
                m = re.search(r"```(?:python|py)?\s*\n(.*?)```", answer, re.DOTALL)
                fixed = m.group(1).strip() if m else ""
            trace.append({"type": "final", "step": steps, "answer": answer,
                          "success": last_run_ok})
            return {"answer": answer, "fixed_code": fixed,
                    "trace": trace, "tokens": tokens, "success": last_run_ok}

        # 3. 执行工具
        ctx.add_assistant_tool_call(parsed["tool_calls"])
        for tc in parsed["tool_calls"]:
            if tc["name"] == "run_snippet":
                run_code = tc["arguments"].get("code", "")
                result = _run_snippet(run_code)
                ok = "returncode=0" in result
                last_run_ok = ok
                if ok:
                    last_good_code = run_code
            else:
                result = f"未知工具：{tc['name']}"
            ctx.add_tool_result(tc["id"], result)
            trace.append({"type": "tool", "step": steps, "name": tc["name"],
                          "arguments": tc["arguments"], "result": result})

    fixed = last_good_code if last_good_code is not None else ""
    trace.append({"type": "final", "step": steps, "answer": "达到最大步数上限",
                  "success": last_run_ok})
    return {"answer": "达到最大步数上限", "fixed_code": fixed,
            "trace": trace, "tokens": tokens, "success": last_run_ok}
