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
