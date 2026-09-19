"""工具集：OpenAI tools schema + 实际执行。"""
import re
import subprocess
from pathlib import Path

from .sandbox import subprocess_env

MAX_READ_CHARS = 8000
_EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "venv", ".pytest_cache"}


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
        if any(part in _EXCLUDED_DIRS for part in f.parts):
            continue
        entries.append(str(f.relative_to(repo_path)))
    return "\n".join(entries[:200])


def _search_code(repo_path, pattern):
    """在仓库的 .py 文件里按关键字/正则搜索，返回 '文件:行号:内容' 列表。

    纯 Python 实现，不依赖系统 grep（Windows 上没有 grep 会抛 FileNotFoundError）。
    """
    try:
        rx = re.compile(pattern)
    except re.error:
        rx = None
    root = Path(repo_path)
    hits = []
    for f in sorted(root.rglob("*.py")):
        if any(part in _EXCLUDED_DIRS for part in f.parts):
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        rel = f.relative_to(root)
        for lineno, line in enumerate(lines, 1):
            matched = rx.search(line) if rx else pattern in line
            if matched:
                hits.append(f"{rel}:{lineno}:{line}")
    if not hits:
        return "无匹配"
    return "\n".join(hits)[:6000]


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
            env=subprocess_env(),
        )
        out = f"returncode={r.returncode}\n{r.stdout[-4000:]}"
        if r.stderr:
            out += f"\nSTDERR:\n{r.stderr[-2000:]}"
        return out
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
