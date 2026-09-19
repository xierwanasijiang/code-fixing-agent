"""粘贴代码片段修复：直接用 LLM 修复用户粘贴的报错代码。"""
import re

from .llm import parse_response


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


def fix_snippet(llm, code, error):
    """给定一段报错代码 + 报错信息，返回修复后的代码与说明。"""
    prompt = (
        "你是代码修复专家。下面这段 Python 代码运行时报错了。\n\n"
        "【代码】\n```python\n" + code + "\n```\n\n"
        "【报错信息 / 期望行为】\n" + error + "\n\n"
        "请按以下格式回答：\n"
        "1. 先用一两句话说明 bug 原因；\n"
        "2. 然后用一个 ```python 代码块返回修复后的完整代码（不要省略任何部分，不要加额外解释）。"
    )
    response = llm.chat([{"role": "user", "content": prompt}])
    parsed = parse_response(response)
    answer = parsed.get("content") or ""
    return {"answer": answer, "fixed_code": extract_code_block(answer),
            "tokens": _usage_of(response)}
