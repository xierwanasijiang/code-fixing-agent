"""对比实验：基线（直接问 LLM）vs 完整 agent，在同一批 bug 上比修复成功率。

用法：python scripts/compare.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

from code_agent.llm import LLMClient, parse_response
from code_agent.loop import run_agent
from code_agent.sandbox import subprocess_env
from code_agent.snippet import extract_code_block

def _scan_bugs(dirname):
    base = ROOT / dirname
    return [
        {"id": d.name, "repo": str(d.relative_to(ROOT))}
        for d in sorted(base.iterdir()) if d.is_dir()
    ]


def _reset(repo):
    subprocess.run(f"git checkout -- {repo}", shell=True, cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")


def _run_test(repo) -> bool:
    r = subprocess.run("pytest test_mylib.py -q", shell=True, cwd=str(ROOT / repo),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=subprocess_env())
    return r.returncode == 0


def baseline_fix(llm, repo) -> bool:
    """基线：单次 LLM 调用，把代码+测试塞进 prompt，直接让它给出修复。"""
    mylib = (ROOT / repo / "mylib.py").read_text(encoding="utf-8")
    test = (ROOT / repo / "test_mylib.py").read_text(encoding="utf-8")
    prompt = (
        "你是代码修复专家。下面的代码当前测试失败，请直接修复。\n\n"
        f"【mylib.py】\n```python\n{mylib}\n```\n\n"
        f"【test_mylib.py】\n```python\n{test}\n```\n\n"
        "只返回修复后的 mylib.py 完整代码（一个 ```python 代码块），不要任何解释。"
    )
    resp = llm.chat([{"role": "user", "content": prompt}])
    answer = parse_response(resp).get("content") or ""
    fixed = extract_code_block(answer)
    if not fixed:
        return False
    (ROOT / repo / "mylib.py").write_text(fixed, encoding="utf-8")
    return _run_test(repo)


def agent_fix(llm, repo) -> bool:
    out = run_agent(llm, {"repo_path": str(ROOT / repo)},
                    {"test_command": "pytest test_mylib.py -q"})
    return out["success"]


def main():
    dirname = sys.argv[1] if len(sys.argv) > 1 else "benchmark/real-bugs"
    bugs = _scan_bugs(dirname)
    if not bugs:
        print(f"目录 {dirname} 下没有 bug，请先运行 python scripts/make_real_bugs.py")
        return
    llm = LLMClient()
    base_ok = agent_ok = 0
    for b in bugs:
        _reset(b["repo"])
        bl = baseline_fix(llm, b["repo"])
        _reset(b["repo"])
        ag = agent_fix(llm, b["repo"])
        print(f"{b['id']}: 基线={'OK' if bl else 'FAIL'}  agent={'OK' if ag else 'FAIL'}")
        base_ok += bl
        agent_ok += ag
    n = len(bugs)
    print(f"\n基线（直接问 LLM）: {base_ok}/{n} = {base_ok / n * 100:.0f}%")
    print(f"agent（完整 ReAct 循环）: {agent_ok}/{n} = {agent_ok / n * 100:.0f}%")


if __name__ == "__main__":
    main()
