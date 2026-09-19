"""执行环境：在仓库目录里跑命令、重置仓库状态。"""
import os
import subprocess
import sys


def _env_with_scripts():
    """构造子进程环境：把 Python console scripts 目录（pytest 等）加入 PATH。

    Windows 商店版 Python 等安装方式下，pip 安装的命令行工具（pytest.exe）
    所在目录往往不在系统 PATH 里，直接 shell=True 跑 `pytest` 会报找不到命令。
    """
    env = dict(os.environ)
    dirs = [os.path.dirname(sys.executable)]
    try:
        import site
        dirs.append(os.path.join(os.path.dirname(site.getusersitepackages()), "Scripts"))
    except Exception:
        pass
    for d in dirs:
        if os.path.isdir(d):
            env["PATH"] = d + os.pathsep + env.get("PATH", "")
    return env


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
            env=_env_with_scripts(),
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
