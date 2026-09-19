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
