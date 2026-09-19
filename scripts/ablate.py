"""消融实验：改变单一变量，观察修复成功率的变化。

用法：python scripts/ablate.py <变量名> <值>
变量名可选：
  no_search       —— 去掉 search_code 工具
  model           —— 换模型（值为模型名，如 deepseek-reasoner）
  max_steps       —— 限制最大步数（值为整数）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from code_agent.llm import LLMClient
from code_agent.loop import run_agent
import code_agent.tools as tools_mod


def main():
    var, val = sys.argv[1], sys.argv[2]
    llm = LLMClient(model=val if var == "model" else "deepseek-chat")
    max_steps = int(val) if var == "max_steps" else 15

    if var == "no_search":
        # 原地切片赋值，保证 loop.py 里 from .tools import TOOL_SCHEMAS 绑定的
        # 同一个 list 对象被原地修改，消融才真正生效。
        tools_mod.TOOL_SCHEMAS[:] = [t for t in tools_mod.TOOL_SCHEMAS
                                     if t["function"]["name"] != "search_code"]

    # 复用 evaluate.py 的逻辑（简单起见，这里只跑第一个实例示意）
    import json
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent.parent
    inst = json.loads(next((ROOT / "benchmark" / "instances").glob("*.json")).read_text())
    env = {"repo_path": str(ROOT / "benchmark" / "repos" / inst["repo"])}
    # 切到实例的 bug 状态（否则在已修好的提交上跑，消融无意义）
    import subprocess
    subprocess.run(f"git checkout {inst['bug_commit']}", shell=True,
                   cwd=env["repo_path"], capture_output=True, text=True)
    out = run_agent(llm, env, inst, max_steps=max_steps)
    print(f"变量={var} 值={val} -> success={out['success']} steps={out['steps']}")


if __name__ == "__main__":
    main()
