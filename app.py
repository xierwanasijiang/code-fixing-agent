"""代码修复 Agent 的可视化界面（Streamlit）。

运行方式（在项目根目录 D:/AIagent项目 下）：
    streamlit run app.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from code_agent.llm import LLMClient
from code_agent.loop import run_agent

st.set_page_config(page_title="代码修复 Agent", page_icon="🤖", layout="wide")

ICONS = {
    "read_file": "📖 读文件",
    "edit_file": "✏️ 改代码",
    "run_test": "🧪 跑测试",
    "list_files": "📂 列目录",
    "search_code": "🔍 搜代码",
}


def _reset(repo: str):
    """把仓库重置回已提交的 bug 状态。"""
    subprocess.run(
        f"git checkout -- {repo}",
        shell=True, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def _run(repo: str, test_cmd: str):
    """重置 → 跑 agent → 返回 run_agent 的结果 dict（含 trace）。"""
    _reset(repo)
    llm = LLMClient()
    env = {"repo_path": str(ROOT / repo)}
    instance = {"test_command": test_cmd}
    return run_agent(llm, env, instance)


def _render_trace(out: dict):
    """把 agent 的逐步 trace 渲染成可视化步骤。"""
    for entry in out["trace"]:
        if entry["type"] == "tool":
            name = entry["name"]
            label = ICONS.get(name, f"🔧 {name}")
            with st.container(border=True):
                st.markdown(f"**Step {entry['step']} — {label}**")
                if name == "edit_file":
                    a = entry["arguments"]
                    st.markdown(
                        f"文件 `{a.get('path', '')}` 里，把\n\n"
                        f"`{str(a.get('old', ''))[:120]}`\n\n"
                        f"改成\n\n`{str(a.get('new', ''))[:120]}`"
                    )
                elif name == "run_test":
                    passed = "returncode=0" in entry["result"]
                    st.markdown("✅ 测试通过" if passed else "❌ 测试失败")
                else:
                    st.caption("参数：" + str(entry["arguments"])[:200])
                with st.expander("查看完整返回"):
                    st.code(entry["result"])
        elif entry["type"] == "final":
            if entry["success"]:
                st.success(f"✅ 修复成功，共 {out['steps']} 步")
            else:
                st.error(f"❌ 未修复，共 {out['steps']} 步")
            with st.expander("查看 Agent 的总结"):
                st.write(entry.get("answer", ""))


# ============ 主界面 ============
st.title("🤖 代码修复 Agent")
st.caption("从零手写的 ReAct bug 修复 Agent —— 可视化每一步决策，不用任何 Agent 框架")

tab_demo, tab_eval = st.tabs(["🔧 单个修复演示", "📊 一键评测"])

with tab_demo:
    st.markdown("#### 让 agent 自己修复 `benchmark/demo` 里的 bug")
    st.markdown("测试期望 `divide(1, 0)` 返回 `None`，但当前代码会抛 `ZeroDivisionError`。点按钮看 agent 怎么一步步定位并修好它。")
    if st.button("🚀 运行修复", type="primary"):
        try:
            out = _run("benchmark/demo", "pytest test_calc.py -q")
            _render_trace(out)
            diff = subprocess.run(
                "git diff -- benchmark/demo/calc.py", shell=True, cwd=ROOT,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            ).stdout
            if diff:
                with st.expander("查看 agent 改动的代码（git diff）"):
                    st.code(diff, language="diff")
        except Exception as e:
            st.error(f"运行出错：{e}")

with tab_eval:
    st.markdown("#### 在 3 个小 bug 上跑评测，统计修复成功率")
    st.caption("每个 bug 都是一个独立小仓库，agent 需逐个定位并修复，最后汇总成功率。")
    instances = [
        {"id": "reverse（字符串反转）", "repo": "benchmark/demo-benchmark/reverse", "test": "pytest test_mylib.py -q"},
        {"id": "average（空列表求平均）", "repo": "benchmark/demo-benchmark/average", "test": "pytest test_mylib.py -q"},
        {"id": "vowels（大写元音计数）", "repo": "benchmark/demo-benchmark/vowels", "test": "pytest test_mylib.py -q"},
    ]
    if st.button("📊 开始评测", type="primary"):
        results = []
        progress = st.progress(0, text="评测中...")
        for i, inst in enumerate(instances):
            st.markdown(f"**正在评测：{inst['id']}**")
            try:
                out = _run(inst["repo"], inst["test"])
                results.append({"任务": inst["id"], "是否修复": "✅" if out["success"] else "❌", "步数": out["steps"]})
            except Exception as e:
                results.append({"任务": inst["id"], "是否修复": "❌（异常）", "步数": "-"})
            progress.progress((i + 1) / len(instances), text=f"已完成 {i + 1}/{len(instances)}")

        st.table(results)
        resolved = sum(1 for r in results if "✅" in r["是否修复"])
        total = len(results)
        st.metric("修复成功率", f"{resolved}/{total} = {resolved / total * 100:.0f}%")
