"""在 benchmark 上全量跑 agent，统计修复成功率。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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
