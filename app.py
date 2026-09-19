"""代码修复 Agent 的可视化界面（Streamlit）。

运行：双击「启动界面.bat」，或 `python -m streamlit run app.py`
"""
import html
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from code_agent.llm import LLMClient
from code_agent.loop import run_agent

st.set_page_config(page_title="代码修复 Agent", page_icon="🤖", layout="wide")

# ================= 主题 CSS =================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root{
  --ink:#16181D; --muted:#6E7687; --line:#E4E6EC;
  --accent:#4F46E5; --ok:#0E9F6E; --warn:#C27803; --err:#D64545;
  --code:#F0F1F4;
}
html, body, [class*="css"]{ font-family:'Inter',-apple-system,sans-serif; color:var(--ink); }
h1,h2,h3,h4{ font-family:'Space Grotesk',sans-serif; letter-spacing:-0.02em; }
code,kbd,pre{ font-family:'JetBrains Mono',monospace; }

.block-container{ padding-top:2.4rem; padding-bottom:3rem; max-width:1060px; }

.hero{ border-bottom:1px solid var(--line); padding-bottom:1.1rem; margin-bottom:1.1rem; }
.hero .kicker{ font-family:'JetBrains Mono',monospace; font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); font-weight:700; }
.hero h1{ font-size:1.9rem; margin:.2rem 0 .35rem; font-weight:700; }
.hero .sub{ color:var(--muted); font-size:.94rem; margin:0; }

.flow{ display:flex; gap:.55rem; margin:1rem 0 1.5rem; }
.flow .fstep{ flex:1; background:#fff; border:1px solid var(--line); border-radius:8px; padding:.55rem .75rem; }
.flow .fstep .n{ font-family:'JetBrains Mono',monospace; font-size:.68rem; color:var(--accent); font-weight:700; }
.flow .fstep .t{ font-weight:600; font-size:.88rem; }

.step{ display:flex; gap:.95rem; border-left:3px solid var(--line); padding:.45rem 0 .45rem 1rem; margin-bottom:.85rem; }
.step.tool{ border-left-color:var(--accent); }
.step.ok{ border-left-color:var(--ok); }
.step.err{ border-left-color:var(--err); }
.step .gutter{ font-family:'JetBrains Mono',monospace; color:var(--muted); font-size:.8rem; padding-top:.14rem; min-width:1.5rem; }
.step .body{ flex:1; min-width:0; }
.step .prompt{ font-family:'JetBrains Mono',monospace; font-weight:500; font-size:.92rem; }
.step .prompt .cmd{ color:var(--accent); font-weight:700; }
.step .prompt .arg{ color:var(--muted); }
.step .tag{ display:inline-block; font-size:.7rem; padding:.05rem .45rem; border-radius:4px; margin-left:.5rem; vertical-align:middle; border:1px solid var(--line); color:var(--muted); }
.step .detail{ color:var(--muted); font-size:.84rem; margin-top:.18rem; }
.step .result{ margin-top:.55rem; background:var(--code); border:1px solid var(--line); border-radius:6px; padding:.55rem .7rem; font-family:'JetBrains Mono',monospace; font-size:.78rem; white-space:pre-wrap; word-break:break-word; }

.stButton > button{ font-family:'Space Grotesk',sans-serif; font-weight:600; border-radius:8px; border:1px solid var(--accent); background:var(--accent); color:#fff; padding:.45rem 1.1rem; }
.stButton > button:hover{ background:#3D35C9; border-color:#3D35C9; }

.stTabs [data-baseweb="tab"]{ font-family:'Space Grotesk',sans-serif; font-weight:600; }
[data-testid="stMetric"]{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:1rem; }
</style>
""",
    unsafe_allow_html=True,
)

TOOL_CN = {
    "read_file": "读文件", "edit_file": "改代码", "run_test": "跑测试",
    "list_files": "列目录", "search_code": "搜代码",
}


def _reset(repo: str):
    subprocess.run(
        f"git checkout -- {repo}", shell=True, cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _run(repo: str, test_cmd: str):
    _reset(repo)
    llm = LLMClient()
    env = {"repo_path": str(ROOT / repo)}
    return run_agent(llm, env, {"test_command": test_cmd})


def _render_trace(out: dict):
    """决策日志：把 agent 每一步渲染成带行号、带状态色的终端命令。"""
    for entry in out["trace"]:
        if entry["type"] == "tool":
            name = entry["name"]
            args = html.escape(str(entry["arguments"])[:160])
            result = html.escape(str(entry["result"])[:900])
            if name == "run_test":
                passed = "returncode=0" in str(entry["result"])
                cls, tag = ("step ok", "通过") if passed else ("step err", "失败")
            else:
                cls, tag = "step tool", TOOL_CN.get(name, name)
            st.markdown(
                f'<div class="{cls}">'
                f'<div class="gutter">{entry["step"]:02d}</div>'
                f'<div class="body">'
                f'<div class="prompt"><span class="cmd">{html.escape(name)}</span> '
                f'<span class="arg">{args}</span><span class="tag">{html.escape(tag)}</span></div>'
                f'<div class="result">{result}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        elif entry["type"] == "final":
            cls = "step ok" if entry["success"] else "step err"
            label = "✓ 修复成功" if entry["success"] else "✕ 未修复"
            answer = html.escape(str(entry.get("answer", ""))[:500])
            st.markdown(
                f'<div class="{cls}"><div class="gutter">✓</div>'
                f'<div class="body"><div class="prompt">{label}</div>'
                f'<div class="detail">{answer}</div></div></div>',
                unsafe_allow_html=True,
            )


# ================= 头部 =================
st.markdown(
    """
<div class="hero">
  <div class="kicker">ReAct · Bug-Fixing Agent</div>
  <h1>代码修复 Agent</h1>
  <p class="sub">从零手写的 ReAct 智能体 —— 观察、决策、执行、验证，一步步自己修好代码里的 bug。不使用任何 Agent 框架。</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="flow">
  <div class="fstep"><div class="n">01</div><div class="t">观察</div></div>
  <div class="fstep"><div class="n">02</div><div class="t">决策</div></div>
  <div class="fstep"><div class="n">03</div><div class="t">执行</div></div>
  <div class="fstep"><div class="n">04</div><div class="t">验证</div></div>
</div>
""",
    unsafe_allow_html=True,
)

# ================= 标签页 =================
tab_demo, tab_eval = st.tabs(["🔧 单个修复演示", "📊 一键评测"])

with tab_demo:
    st.markdown("**让 agent 自己修好 `benchmark/demo` 里的 bug。**")
    st.markdown("测试期望 `divide(1, 0)` 返回 `None`，但当前代码会抛 `ZeroDivisionError`。点按钮，看它一步步定位并修复。")
    if st.button("🚀 运行修复", type="primary"):
        try:
            out = _run("benchmark/demo", "pytest test_calc.py -q")
            _render_trace(out)
            diff = subprocess.run(
                "git diff -- benchmark/demo/calc.py", shell=True, cwd=ROOT,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            ).stdout
            if diff:
                st.markdown("**改动的代码（diff）**")
                st.code(diff, language="diff")
        except Exception as e:
            st.error(f"运行出错：{e}")

with tab_eval:
    st.markdown("**在 3 个不同的小 bug 上跑评测，统计修复成功率。**")
    st.markdown("每个都是独立小仓库：字符串反转、空列表求平均、大写元音计数。")
    instances = [
        {"id": "字符串反转", "repo": "benchmark/demo-benchmark/reverse", "test": "pytest test_mylib.py -q"},
        {"id": "空列表求平均", "repo": "benchmark/demo-benchmark/average", "test": "pytest test_mylib.py -q"},
        {"id": "大写元音计数", "repo": "benchmark/demo-benchmark/vowels", "test": "pytest test_mylib.py -q"},
    ]
    if st.button("📊 开始评测", type="primary"):
        results = []
        progress = st.progress(0, text="评测中...")
        for i, inst in enumerate(instances):
            st.markdown(f"**正在评测：{inst['id']}**")
            try:
                out = _run(inst["repo"], inst["test"])
                results.append({"任务": inst["id"], "结果": "✅ 修复" if out["success"] else "❌ 未修复", "步数": out["steps"]})
            except Exception as e:
                results.append({"任务": inst["id"], "结果": "❌ 异常", "步数": "-"})
            progress.progress((i + 1) / len(instances), text=f"已完成 {i + 1}/{len(instances)}")

        st.table(results)
        resolved = sum(1 for r in results if "✅" in r["结果"])
        total = len(results)
        st.metric("修复成功率", f"{resolved}/{total} = {resolved / total * 100:.0f}%")
