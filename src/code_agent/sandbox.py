"""执行环境：在仓库目录里跑命令、重置仓库状态。"""
import os
import shlex
import subprocess
import sys


def subprocess_env():
    """返回补上 Python console scripts 目录（pytest 等）的子进程环境。

    Windows 商店版 Python 等安装方式下，pip 安装的命令行工具（pytest.exe）
    所在目录往往不在系统 PATH 里，直接 shell=True 跑 `pytest` 会报找不到命令。
    这里把 `sys.executable` 所在目录和用户 Scripts 目录补进 PATH，跨平台安全
    （不存在的目录会被 isdir 过滤掉）。
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


# shell 元字符：即使 shell=False 也会被 shlex 保留成 token，这里直接拒绝，双保险
_SHELL_METACHARS = "&|;><`$\n\r"


def parse_test_cmd(test_cmd):
    """解析并校验测试命令，返回参数列表；非法时返回 None。

    只允许 `pytest ...` 形态，且不能包含 shell 元字符，防止命令注入。
    """
    try:
        parts = shlex.split(test_cmd)
    except ValueError:
        return None
    if not parts or parts[0] != "pytest":
        return None
    if any(ch in _SHELL_METACHARS for tok in parts for ch in tok):
        return None
    return parts


def pytest_argv(parts):
    """把校验过的 `pytest ...` parts 转成可直接执行的 argv。

    Windows 商店版 Python 下 CreateProcess 无法从用户 Scripts 目录解析裸
    `pytest`，改用 `sys.executable -m pytest`，跨平台且始终可解析。
    """
    return [sys.executable, "-m", "pytest"] + parts[1:]


def run_test(repo_path, test_cmd, timeout=60):
    """在 repo_path 下运行 test_cmd（如 'pytest tests/test_x.py -q'），返回结构化结果。"""
    parts = parse_test_cmd(test_cmd)
    if parts is None:
        return {"returncode": -1, "stdout": "", "stderr": "错误：只允许运行 pytest 测试命令"}
    try:
        result = subprocess.run(
            pytest_argv(parts),
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=subprocess_env(),
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
        encoding="utf-8",
        errors="replace",
        env=subprocess_env(),
    )
