# 代码修复 Agent（Code Bug-Fixing Agent）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零手写一个能"定位并修复 Python 仓库中真实 bug"的 ReAct Agent，配自建 benchmark 和评测。

**Architecture:** 四层结构 —— 手写 ReAct 循环（`loop.py`）通过工具集（`tools.py`）在沙盒（`sandbox.py`）里操作被修仓库，评测层（`scripts/evaluate.py`）在自建 benchmark 上计算修复成功率。不用 LangChain/LangGraph，只用 DeepSeek 的 function calling。

**Tech Stack:** Python 3.10+ / `openai` SDK（指向 DeepSeek）/ `pytest` / `git` / `subprocess`。

**Spec:** `docs/superpowers/specs/2026-09-19-code-agent-design.md`

## Global Constraints

- Python 版本：3.10+
- 模型：DeepSeek `deepseek-chat`；SDK：`openai`，`base_url="https://api.deepseek.com"`
- API key 通过环境变量 `DEEPSEEK_API_KEY` 注入，**禁止硬编码进代码**
- 禁止使用 LangChain / LangGraph / AutoGPT 等 Agent 框架
- 项目根目录：`D:\AIagent项目`，所有命令在该目录下执行
- 测试框架：`pytest`
- Agent 循环默认 `MAX_STEPS=15`
- **版本管理**：`git init` 是否执行**待用户决定**；本计划中的 `git commit` 步骤仅在已初始化 git 时执行，未初始化则跳过该步（不报错）

---

## 文件结构总览

```
D:\AIagent项目\
├── requirements.txt
├── .gitignore
├── README.md
├── src\code_agent\
│   ├── __init__.py
│   ├── llm.py          # DeepSeek 客户端 + 工具调用响应解析
│   ├── prompts.py      # 系统提示词 / 任务提示词模板
│   ├── context.py      # 上下文（消息列表）管理
│   ├── sandbox.py      # 执行环境：跑 pytest、reset 仓库
│   ├── tools.py        # 工具 schema + 实现 + 分发执行
│   └── loop.py         # ReAct 循环
├── scripts\
│   ├── demo_weather.py # 阶段 0：工具调用最小 demo
│   ├── demo_fix.py     # 阶段 1：端到端修一个预制 bug
│   ├── mine_bugs.py    # 阶段 2：从 git 历史挖 benchmark
│   ├── evaluate.py     # 阶段 3：全量评测 + 指标
│   └── ablate.py       # 阶段 3：消融实验
├── benchmark\          # 挖掘出的 bug 实例（脚本生成）
└── tests\
    ├── test_llm.py
    ├── test_context.py
    ├── test_tools.py
    ├── test_sandbox.py
    └── test_loop.py
```

---

### Task 1: 项目脚手架 + LLM 客户端

**Files:**
- Create: `requirements.txt`, `.gitignore`, `src/code_agent/__init__.py`, `src/code_agent/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces: `LLMClient(model, api_key=None, base_url=...)`，方法 `.chat(messages, tools=None, temperature=0.0, max_tokens=4096)` 返回 OpenAI 响应对象；模块级函数 `parse_response(response) -> dict`，返回 `{"tool_calls": [...]}` 或 `{"content": "..."}`。

- [ ] **Step 1: 写 `requirements.txt` 与 `.gitignore`**

`requirements.txt`:
```
openai>=1.40.0
pytest>=8.0.0
```

`.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
.venv/
benchmark/repos/
```

- [ ] **Step 2: 写 `src/code_agent/__init__.py`（空文件即可）**

```python
# 包标记文件，可为空
```

- [ ] **Step 3: 写失败测试 `tests/test_llm.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认失败**

Run: `python -m pytest tests/test_llm.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'code_agent'` 或 `cannot import name`）

- [ ] **Step 5: 写 `src/code_agent/llm.py`**

```python
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
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `python -m pytest tests/test_llm.py -v`
Expected: PASS（2 passed）

- [ ] **Step 7: 安装依赖**

Run: `python -m pip install -r requirements.txt`

- [ ] **Step 8: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: 项目脚手架 + LLM 客户端"
```

---

### Task 2: 工具调用最小 demo（阶段 0 收官）

**Files:**
- Create: `scripts/demo_weather.py`

**Interfaces:**
- Consumes: `LLMClient.chat`、`parse_response`（Task 1）

- [ ] **Step 1: 写 `scripts/demo_weather.py`**

```python
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
```

- [ ] **Step 2: 运行 demo**

Run: `python scripts/demo_weather.py`
Expected: 第一轮打印出含 `get_weather` 的 `tool_calls`；第二轮打印出含天气描述的自然语言答案。

> 如果这里报 `未设置 DEEPSEEK_API_KEY`，先在终端设置：`export DEEPSEEK_API_KEY=你的key`（Windows Git Bash）。

- [ ] **Step 3: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: 工具调用最小 demo"
```

---

### Task 3: 沙盒（执行环境）

**Files:**
- Create: `src/code_agent/sandbox.py`
- Test: `tests/test_sandbox.py`

**Interfaces:**
- Produces: `run_test(repo_path, test_cmd, timeout=60) -> dict`（含 `returncode`/`stdout`/`stderr`）；`reset_repo(repo_path) -> None`

- [ ] **Step 1: 写失败测试 `tests/test_sandbox.py`**

```python
import os
import subprocess

from code_agent.sandbox import run_test


def _make_tiny_repo(tmp_path):
    (tmp_path / "mylib.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "test_mylib.py").write_text(
        "from mylib import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    return str(tmp_path)


def test_run_test_passes(tmp_path):
    repo = _make_tiny_repo(tmp_path)
    out = run_test(repo, "pytest test_mylib.py -q")
    assert out["returncode"] == 0
    assert "1 passed" in out["stdout"]


def test_run_test_fails(tmp_path):
    repo = _make_tiny_repo(tmp_path)
    (tmp_path / "mylib.py").write_text("def add(a, b):\n    return a - b\n")
    out = run_test(repo, "pytest test_mylib.py -q")
    assert out["returncode"] == 1
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_sandbox.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 写 `src/code_agent/sandbox.py`**

```python
"""执行环境：在仓库目录里跑命令、重置仓库状态。"""
import subprocess


def run_test(repo_path, test_cmd, timeout=60):
    """在 repo_path 下运行 test_cmd（如 'pytest tests/test_x.py -q'），返回结构化结果。"""
    try:
        result = subprocess.run(
            test_cmd,
            shell=True,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "测试执行超时"}


def reset_repo(repo_path):
    """丢弃仓库里的未提交改动，让每个 bug 实例从干净状态开始。"""
    subprocess.run(
        "git checkout -- . && git clean -fd",
        shell=True,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_sandbox.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: 沙盒执行环境"
```

---

### Task 4: 上下文管理

**Files:**
- Create: `src/code_agent/context.py`
- Test: `tests/test_context.py`

**Interfaces:**
- Produces: `Context(system_prompt, task)`，方法 `.messages`（只读属性）、`.add_assistant_tool_call(tool_calls)`、`.add_tool_result(tool_call_id, result)`。遵循 OpenAI 工具调用协议：assistant 消息带 `tool_calls`，结果用 `role:"tool"` + `tool_call_id` 回传。

- [ ] **Step 1: 写失败测试 `tests/test_context.py`**

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_context.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 写 `src/code_agent/context.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_context.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: 上下文管理"
```

---

### Task 5: 工具集（5 个工具 + 分发执行）

**Files:**
- Create: `src/code_agent/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Produces: 常量 `TOOL_SCHEMAS`（OpenAI tools 格式的列表，5 个工具）；函数 `execute_tool(name, args, env) -> str`，其中 `env` 是含 `repo_path` 的 dict。工具名：`list_files`、`read_file`、`search_code`、`edit_file`、`run_test`。

- [ ] **Step 1: 写失败测试 `tests/test_tools.py`**

```python
from code_agent.tools import TOOL_SCHEMAS, execute_tool


def test_schema_has_five_tools():
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert names == {"list_files", "read_file", "search_code", "edit_file", "run_test"}


def test_read_file(tmp_path):
    (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
    out = execute_tool("read_file", {"path": "a.py"}, {"repo_path": str(tmp_path)})
    assert "line2" in out


def test_edit_file_roundtrip(tmp_path):
    (tmp_path / "a.py").write_text("old text here\n")
    execute_tool(
        "edit_file",
        {"path": "a.py", "old": "old text", "new": "new text"},
        {"repo_path": str(tmp_path)},
    )
    assert (tmp_path / "a.py").read_text() == "new text here\n"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 写 `src/code_agent/tools.py`**

```python
"""工具集：OpenAI tools schema + 实际执行。"""
import os
import subprocess
from pathlib import Path

MAX_READ_CHARS = 8000


def _read_file(repo_path, path, start=None, end=None):
    p = Path(repo_path) / path
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if start is not None or end is not None:
        start = (start or 1) - 1
        end = end or len(lines)
        lines = lines[start:end]
    body = "\n".join(lines)
    return body[:MAX_READ_CHARS]


def _list_files(repo_path, path="."):
    p = Path(repo_path) / path
    entries = []
    for f in sorted(p.rglob("*")):
        if any(part in {".git", "__pycache__", ".venv"} for part in f.parts):
            continue
        entries.append(str(f.relative_to(repo_path)))
    return "\n".join(entries[:200])


def _search_code(repo_path, pattern):
    result = subprocess.run(
        ["grep", "-rn", "--include=*.py", pattern, "."],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return (result.stdout or "无匹配")[:6000]


def _edit_file(repo_path, path, old, new):
    p = Path(repo_path) / path
    text = p.read_text(encoding="utf-8", errors="replace")
    if old not in text:
        return f"错误：文件中找不到要替换的内容：{old[:100]!r}"
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return f"已修改 {path}"


def _run_test(repo_path, test_cmd, timeout=60):
    try:
        r = subprocess.run(
            test_cmd, shell=True, cwd=repo_path,
            capture_output=True, text=True, timeout=timeout,
        )
        return f"returncode={r.returncode}\n{r.stdout[-4000:]}"
    except subprocess.TimeoutExpired:
        return "测试执行超时"


TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "list_files",
        "description": "列出仓库目录下的文件", "parameters": {"type": "object",
        "properties": {"path": {"type": "string", "description": "相对路径，默认 '.'"}},
        "required": []}}},
    {"type": "function", "function": {"name": "read_file",
        "description": "读取文件内容", "parameters": {"type": "object",
        "properties": {"path": {"type": "string"}, "start": {"type": "integer"},
        "end": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_code",
        "description": "按关键字搜索代码", "parameters": {"type": "object",
        "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "edit_file",
        "description": "修改文件：把 old 字符串替换成 new", "parameters": {"type": "object",
        "properties": {"path": {"type": "string"}, "old": {"type": "string"},
        "new": {"type": "string"}}, "required": ["path", "old", "new"]}}},
    {"type": "function", "function": {"name": "run_test",
        "description": "运行测试命令", "parameters": {"type": "object",
        "properties": {"test_cmd": {"type": "string"}}, "required": ["test_cmd"]}}},
]


def execute_tool(name, args, env):
    repo_path = env["repo_path"]
    if name == "list_files":
        return _list_files(repo_path, args.get("path", "."))
    if name == "read_file":
        return _read_file(repo_path, args["path"], args.get("start"), args.get("end"))
    if name == "search_code":
        return _search_code(repo_path, args["pattern"])
    if name == "edit_file":
        return _edit_file(repo_path, args["path"], args["old"], args["new"])
    if name == "run_test":
        return _run_test(repo_path, args["test_cmd"])
    return f"未知工具：{name}"
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_tools.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: 五个工具 + 分发执行"
```

---

### Task 6: ReAct 循环

**Files:**
- Create: `src/code_agent/prompts.py`, `src/code_agent/loop.py`
- Test: `tests/test_loop.py`

**Interfaces:**
- Consumes: `LLMClient`、`parse_response`（Task 1）、`Context`（Task 4）、`execute_tool`/`TOOL_SCHEMAS`（Task 5）
- Produces: `prompts.SYSTEM_PROMPT`、`prompts.build_task(instance)`；`loop.run_agent(llm, env, instance, max_steps=15) -> dict`，返回 `{"success": bool, "steps": int, "messages": [...], "answer": str}`

- [ ] **Step 1: 写 `src/code_agent/prompts.py`**

```python
"""提示词模板。"""
SYSTEM_PROMPT = """你是专业的软件工程师 Agent，任务是修复代码仓库中的 bug。
工作方式：
1. 先 read_file / search_code 定位问题
2. 用 edit_file 修改代码
3. 用 run_test 验证修改是否让失败的测试通过
4. 重复直到测试通过
约束：只改与 bug 相关的代码，不做无关重构；每次修改后都要运行测试验证。"""


def build_task(instance):
    return (
        f"请修复仓库中的 bug。仓库根目录为 {instance['repo_path']}。\n"
        f"验证命令：{instance['test_command']}\n"
        f"先运行这个测试看到报错，然后定位并修复代码，直到测试通过。"
    )
```

- [ ] **Step 2: 写失败测试 `tests/test_loop.py`（用 FakeLLM 模拟模型）**

```python
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
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `python -m pytest tests/test_loop.py -v`
Expected: FAIL（import error）

- [ ] **Step 4: 写 `src/code_agent/loop.py`**

```python
"""ReAct 循环：LLM 决策 → 调工具 → 观察 → 再决策。"""
from .context import Context
from .llm import parse_response
from .prompts import SYSTEM_PROMPT, build_task
from .tools import TOOL_SCHEMAS, execute_tool


def run_agent(llm, env, instance, max_steps=15):
    ctx = Context(SYSTEM_PROMPT, build_task(instance))
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
            return {"success": success, "steps": steps,
                    "messages": ctx.messages, "answer": answer}

        # 按 OpenAI 工具调用协议回传：assistant.tool_calls + role:"tool"
        ctx.add_assistant_tool_call(parsed["tool_calls"])
        for tc in parsed["tool_calls"]:
            result = execute_tool(tc["name"], tc["arguments"], env)
            ctx.add_tool_result(tc["id"], result)

    return {"success": False, "steps": steps,
            "messages": ctx.messages, "answer": "达到最大步数上限"}
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python -m pytest tests/test_loop.py -v`
Expected: PASS（1 passed）

- [ ] **Step 6: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: ReAct 循环"
```

---

### Task 7: 端到端 demo（修一个预制 bug，阶段 1 收官）

**Files:**
- Create: `scripts/demo_fix.py`

- [ ] **Step 1: 准备一个带 bug 的小仓库 `benchmark/demo/`**

`benchmark/demo/calc.py`:
```python
def divide(a, b):
    return a / b
```

`benchmark/demo/test_calc.py`:
```python
from calc import divide


def test_divide_by_zero():
    # 期望除以 0 返回 None，而不是抛异常
    assert divide(1, 0) is None
```

- [ ] **Step 2: 写 `scripts/demo_fix.py`**

```python
"""阶段 1 demo：让 agent 端到端修好 benchmark/demo 里的 bug。"""
from code_agent.llm import LLMClient
from code_agent.loop import run_agent


def main():
    llm = LLMClient()
    env = {"repo_path": "benchmark/demo"}
    instance = {"test_command": "pytest test_calc.py -q"}
    out = run_agent(llm, env, instance)
    print("success:", out["success"])
    print("steps:", out["steps"])
    print("answer:", out["answer"])


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 运行 demo**

Run: `python scripts/demo_fix.py`
Expected: `success: True`（agent 把 `divide` 改成除以 0 返回 None 的版本，测试通过）。首次跑可能因步数或模型波动失败，属正常，多跑几次观察。

- [ ] **Step 4: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: 端到端修复 demo"
```

---

### Task 8: benchmark 挖掘脚本（阶段 2）

**Files:**
- Create: `scripts/mine_bugs.py`

**Interfaces:**
- Produces: `benchmark/instances/*.json`，每个实例字段：`id`、`repo`、`bug_commit`、`fix_commit`、`test_command`、`fail_to_pass`（列表）

- [ ] **Step 1: 写 `scripts/mine_bugs.py`**

```python
"""从目标 Python 库的 git 历史中挖出真实 bug 修复实例。

用法：python scripts/mine_bugs.py <repo_url> <repo_name> <max_bugs>
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOS_DIR = ROOT / "benchmark" / "repos"
OUT_DIR = ROOT / "benchmark" / "instances"


def run(cmd, cwd):
    return subprocess.run(cmd, shell=True, cwd=cwd,
                          capture_output=True, text=True)


def changed_test_files(commit, cwd):
    out = run(f"git show --name-only --oneline {commit}", cwd)
    return [l for l in out.stdout.splitlines()
            if l.startswith("test") and l.endswith(".py")]


def tests_to_ids(test_file, cwd):
    # 用 pytest --collect-only 列出该测试文件里所有的 test id
    out = run(f"pytest {test_file} --collect-only -q", cwd)
    ids = [l.strip() for l in out.stdout.splitlines()
           if "::" in l and not l.strip().startswith(("=", "-", "no"))]
    return ids


def main():
    repo_url, repo_name, max_bugs = sys.argv[1], sys.argv[2], int(sys.argv[3])
    repo_dir = REPOS_DIR / repo_name
    if not repo_dir.exists():
        run(f"git clone {repo_url} {repo_dir}", ROOT)

    # 找含 fix 的提交
    out = run("git log --oneline -n 200 --grep=fix", repo_dir)
    candidates = [l.split()[0] for l in out.stdout.splitlines() if l]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    found = 0
    for fix_commit in candidates:
        if found >= max_bugs:
            break
        test_files = changed_test_files(fix_commit, repo_dir)
        if not test_files:
            continue
        bug_commit = f"{fix_commit}^"
        run(f"git checkout {bug_commit}", repo_dir)
        fail_to_pass = []
        for tf in test_files:
            ids = tests_to_ids(tf, repo_dir)
            for tid in ids:
                r = run(f"pytest {tid} -q", repo_dir)
                if r.returncode != 0:
                    fail_to_pass.append(tid)
        run(f"git checkout {fix_commit}", repo_dir)
        if not fail_to_pass:
            continue
        inst = {
            "id": f"{repo_name}-{found:03d}",
            "repo": repo_name,
            "bug_commit": bug_commit,
            "fix_commit": fix_commit,
            "test_command": f"pytest {' '.join(fail_to_pass)} -q",
            "fail_to_pass": fail_to_pass,
        }
        (OUT_DIR / f"{inst['id']}.json").write_text(
            json.dumps(inst, ensure_ascii=False, indent=2))
        print("挖到:", inst["id"], fail_to_pass)
        found += 1
    run("git checkout main || git checkout master", repo_dir)
    print(f"完成，共 {found} 个实例，输出到 {OUT_DIR}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行挖 bug（在计划执行阶段，选一个仓库）**

Run: `python scripts/mine_bugs.py https://github.com/Textualize/rich rich 20`
Expected: 输出若干"挖到: rich-000 ..."行，最终 `benchmark/instances/` 下出现 json 文件。

> 首次建议先用 `rich` 试。若某仓库挖出的 bug 太少或太杂，换 `click` 再试。这一步依赖网络 clone，耗时较长属正常。

- [ ] **Step 3: 人工抽查 2-3 个实例**

打开 `benchmark/instances/*.json`，确认 `test_command` 里的测试在 `bug_commit` 状态下确实失败、`fix_commit` 状态下通过（可用 `git checkout` 手动验证一个）。

- [ ] **Step 4: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: benchmark 挖掘脚本 + 首批实例"
```

---

### Task 9: 全量评测脚本 + 指标（阶段 3）

**Files:**
- Create: `scripts/evaluate.py`

**Interfaces:**
- Consumes: `run_agent`（Task 6）、`LLMClient`（Task 1）、`sandbox`（Task 3）
- Produces: 控制台打印每个实例结果 + 汇总 `resolved` 成功率，并写入 `benchmark/results.json`

- [ ] **Step 1: 写 `scripts/evaluate.py`**

```python
"""在 benchmark 上全量跑 agent，统计修复成功率。"""
import json
from pathlib import Path

from code_agent.llm import LLMClient
from code_agent.loop import run_agent
from code_agent.sandbox import reset_repo

ROOT = Path(__file__).resolve().parent.parent
INST_DIR = ROOT / "benchmark" / "instances"
REPOS_DIR = ROOT / "benchmark" / "repos"


def main():
    llm = LLMClient()
    results = []
    for inst_path in sorted(INST_DIR.glob("*.json")):
        inst = json.loads(inst_path.read_text())
        repo_path = REPOS_DIR / inst["repo"]
        # 切到 bug 状态
        import subprocess
        subprocess.run(f"git checkout {inst['bug_commit']}", shell=True,
                       cwd=repo_path, capture_output=True, text=True)
        env = {"repo_path": str(repo_path)}
        out = run_agent(llm, env, inst)
        reset_repo(str(repo_path))
        results.append({"id": inst["id"], "success": out["success"],
                        "steps": out["steps"], "answer": out["answer"]})
        print(f"{inst['id']}: success={out['success']} steps={out['steps']}")

    resolved = sum(1 for r in results if r["success"])
    total = len(results)
    print(f"\n修复成功率: {resolved}/{total} = {resolved/total*100:.1f}%" if total else "无实例")
    (ROOT / "benchmark" / "results.json").write_text(
        json.dumps({"results": results, "resolved": resolved, "total": total},
                   ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行评测**

Run: `python scripts/evaluate.py`
Expected: 逐条打印每个实例结果，最后打印修复成功率，并生成 `benchmark/results.json`。

- [ ] **Step 3: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: 全量评测脚本"
```

---

### Task 10: 消融实验（阶段 3）

**Files:**
- Create: `scripts/ablate.py`

- [ ] **Step 1: 写 `scripts/ablate.py`**

```python
"""消融实验：改变单一变量，观察修复成功率的变化。

用法：python scripts/ablate.py <变量名> <值>
变量名可选：
  no_search       —— 去掉 search_code 工具
  model           —— 换模型（值为模型名，如 deepseek-reasoner）
  max_steps       —— 限制最大步数（值为整数）
"""
import sys

from code_agent.llm import LLMClient
from code_agent.loop import run_agent
import code_agent.loop as loop_mod
import code_agent.tools as tools_mod


def main():
    var, val = sys.argv[1], sys.argv[2]
    llm = LLMClient(model=val if var == "model" else "deepseek-chat")
    max_steps = int(val) if var == "max_steps" else 15

    if var == "no_search":
        tools_mod.TOOL_SCHEMAS = [t for t in tools_mod.TOOL_SCHEMAS
                                  if t["function"]["name"] != "search_code"]

    # 复用 evaluate.py 的逻辑（简单起见，这里只跑第一个实例示意）
    import json
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent.parent
    inst = json.loads(next((ROOT / "benchmark" / "instances").glob("*.json")).read_text())
    env = {"repo_path": str(ROOT / "benchmark" / "repos" / inst["repo"])}
    out = run_agent(llm, env, inst, max_steps=max_steps)
    print(f"变量={var} 值={val} -> success={out['success']} steps={out['steps']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 依次跑消融并记录对比**

Run:
- `python scripts/ablate.py no_search 1`
- `python scripts/ablate.py model deepseek-reasoner`
- `python scripts/ablate.py max_steps 5`

Expected: 每条打印该变量下的 success/steps，和 baseline（Task 9 的成功率）对比，得出"哪个设计贡献最大"的结论。

- [ ] **Step 3: Commit（若已 git init）**

```bash
git add -A && git commit -m "feat: 消融实验脚本"
```

---

### Task 11: README 与打磨（阶段 3 收官）

**Files:**
- Create: `README.md`

- [ ] **Step 1: 写 `README.md`**

包含以下小节（用真实数字替换占位）：

```markdown
# 代码修复 Agent

从零手写的 ReAct 代码 bug 修复 Agent，不用 LangChain/LangGraph，
只用 DeepSeek 的 function calling。

## 架构
四层：Agent 循环 / 工具集 / 沙盒 / 评测层（详见 docs/superpowers/specs/...）。

## 快速开始
1. pip install -r requirements.txt
2. export DEEPSEEK_API_KEY=你的key
3. python scripts/demo_weather.py   # 阶段 0
4. python scripts/demo_fix.py       # 阶段 1
5. python scripts/mine_bugs.py ...  # 阶段 2
6. python scripts/evaluate.py       # 阶段 3

## 结果
- 修复成功率：X/30 = Y%
- 消融：去掉 search_code 后降 Z%；换 deepseek-reasoner 后 ±W%；max_steps=5 时 ±V%

## 亮点
- 300 行手写 ReAct 循环
- 自建真实 bug benchmark（从 git 历史挖掘）
- 可复现评测 + 消融实验
```

- [ ] **Step 2: 用真实评测数字填进 README 的"结果"段**

- [ ] **Step 3: 全量跑一遍测试套件，确认绿**

Run: `python -m pytest -q`
Expected: 所有 tests/ 下的测试通过。

- [ ] **Step 4: Commit（若已 git init）**

```bash
git add -A && git commit -m "docs: README 与结果"
```

---

## 执行顺序小结

1. Task 1-2（阶段 0）：LLM 客户端 + 工具调用 demo —— 地基
2. Task 3-7（阶段 1）：沙盒 → 上下文 → 工具 → 循环 → 端到端 demo
3. Task 8（阶段 2）：挖 benchmark
4. Task 9-11（阶段 3）：评测 → 消融 → README

**依赖关系**：Task 1 是唯一前置；Task 3/4/5 无相互依赖可并行；Task 6 依赖 1/4/5；Task 7 依赖 6；Task 8-9 依赖 6；Task 10-11 依赖 9。
