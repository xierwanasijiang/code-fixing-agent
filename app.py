"""代码修复 Agent 的可视化界面（Streamlit）。

运行：双击「启动界面.bat」，或 `python -m streamlit run app.py`
"""
import html
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from code_agent.llm import LLMClient
from code_agent.loop import run_agent
from code_agent.snippet import run_snippet_agent

st.set_page_config(page_title="代码修复 Agent", page_icon="🤖", layout="wide")

# ================= 侧边栏：API Key =================
with st.sidebar:
    st.markdown("### 🔑 模型 API Key")
    st.markdown("填入**你自己的** DeepSeek API Key（只存当前会话，不保存、不上传）。")
    api_key_input = st.text_input(
        "DeepSeek API Key", type="password", placeholder="sk-...",
        value=st.session_state.get("api_key", ""),
    )
    if api_key_input.strip():
        st.session_state["api_key"] = api_key_input.strip()
    if st.session_state.get("api_key", "").strip() or os.environ.get("DEEPSEEK_API_KEY"):
        st.success("✅ 已就绪，可以运行。")
    else:
        st.warning("⚠️ 尚未设置 API Key。\n\n去 [platform.deepseek.com](https://platform.deepseek.com) 免费申请一个，粘贴到上方输入框。")
    st.caption("默认模型：deepseek-chat（OpenAI 兼容，也可换成你自己的 OpenAI key）")

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

.block-container{ padding-top:2.4rem; padding-bottom:3rem; max-width:1080px; }

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
.step.thought{ border-left-color:var(--warn); }
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

.tokbar{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:.8rem 1rem; margin-top:1rem; display:flex; gap:2rem; align-items:center; font-family:'JetBrains Mono',monospace; font-size:.85rem; }
.tokbar b{ color:var(--accent); }
</style>
""",
    unsafe_allow_html=True,
)

TOOL_CN = {
    "read_file": "读文件", "edit_file": "改代码", "run_test": "跑测试",
    "list_files": "列目录", "search_code": "搜代码", "run_snippet": "运行验证",
}


# ================= 工具函数 =================
def _reset(repo: str):
    subprocess.run(
        f"git checkout -- {repo}", shell=True, cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8", errors="replace")


def _write_text(rel_path: str, content: str):
    (ROOT / rel_path).write_text(content, encoding="utf-8")


def _get_llm():
    key = st.session_state.get("api_key", "").strip() or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        return None
    return LLMClient(api_key=key)


def _run(llm, repo: str, test_cmd: str, reset: bool = True):
    if reset:
        _reset(repo)
    env = {"repo_path": str(ROOT / repo)}
    return run_agent(llm, env, {"test_command": test_cmd})


def _render_tokens(tokens: dict):
    """显示 token 用量 + 粗略花费。"""
    if not tokens or not tokens.get("total"):
        return
    prompt = tokens.get("prompt", 0)
    completion = tokens.get("completion", 0)
    total = tokens.get("total", 0)
    cost = prompt / 1e6 * 2 + completion / 1e6 * 8  # 粗略：输入¥2/百万、输出¥8/百万
    st.markdown(
        f'<div class="tokbar">'
        f'<span>输入 <b>{prompt:,}</b></span>'
        f'<span>输出 <b>{completion:,}</b></span>'
        f'<span>总计 <b>{total:,}</b> tokens</span>'
        f'<span>≈ ¥{cost:.4f}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.caption("花费按 deepseek-chat 输入 ¥2/百万、输出 ¥8/百万 粗略估算，以官网为准。")


def _render_trace(out: dict):
    for entry in out["trace"]:
        if entry["type"] == "thought":
            thought = html.escape(str(entry.get("content", ""))[:800])
            st.markdown(
                f'<div class="step thought">'
                f'<div class="gutter">{entry["step"]:02d}</div>'
                f'<div class="body"><div class="prompt">💭 思考</div>'
                f'<div class="detail">{thought}</div></div></div>',
                unsafe_allow_html=True,
            )
        elif entry["type"] == "tool":
            name = entry["name"]
            args = html.escape(str(entry["arguments"])[:160])
            result = html.escape(str(entry["result"])[:900])
            if name in ("run_test", "run_snippet"):
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


def _render_before_after(before: str, after: str):
    """并排显示修复前 vs 修复后。"""
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**❌ 修复前**")
        st.code(before, language="python")
    with c2:
        st.markdown("**✅ 修复后**")
        st.code(after, language="python")


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
tab_paste, tab_demo, tab_eval = st.tabs(["📝 粘贴修复", "🔧 仓库修复演示", "📊 批量演示"])

# ---------- 粘贴修复 ----------
with tab_paste:
    st.markdown("**粘贴你报错的代码，让 agent 真调试并修复。**")
    st.markdown("agent 会实际运行你的代码、看到报错、反复修改直到跑通——下面是它的完整决策日志。")
    code_in = st.text_area(
        "你的代码", height=200,
        placeholder="def divide(a, b):\n    return a / b",
    )
    err_in = st.text_area(
        "报错信息 / 期望行为", height=100,
        placeholder="ZeroDivisionError: division by zero\n（或：除数为 0 时应该返回 None）",
    )
    if st.button("🔍 找出 bug 并修复", type="primary"):
        if not code_in.strip():
            st.warning("请先粘贴你的代码。")
        else:
            llm = _get_llm()
            if llm is None:
                st.warning("请先在左侧侧边栏填写 DeepSeek API Key。")
            else:
                try:
                    with st.spinner("agent 正在运行并调试你的代码..."):
                        res = run_snippet_agent(llm, code_in, err_in or "（未提供报错信息，请根据代码语义判断）")
                    st.markdown("**agent 的调试过程**")
                    _render_trace(res)
                    if res["fixed_code"]:
                        _render_before_after(code_in, res["fixed_code"])
                    else:
                        st.warning("agent 没能得到可运行的修复（可能因依赖缺失或步数用尽）。")
                    _render_tokens(res["tokens"])
                except Exception as e:
                    st.error(f"运行出错：{e}")

# ---------- 单个修复演示 ----------
with tab_demo:
    st.markdown("**下面是 agent 要修复的仓库，代码可直接修改——改完就是你的 bug。**")
    st.caption("点「运行修复」后，agent 会读这个文件、改代码、跑测试，下面的决策日志会一步步展示它做了什么。")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**`calc.py`**")
        calc_val = st.text_area("calc.py", value=_read_text("benchmark/demo/calc.py"), height=160, label_visibility="collapsed")
    with c2:
        st.markdown("**`test_calc.py`**")
        test_val = st.text_area("test_calc.py", value=_read_text("benchmark/demo/test_calc.py"), height=160, label_visibility="collapsed")

    col_reset, col_run = st.columns([1, 2])
    with col_reset:
        if st.button("🔄 重置为初始 bug"):
            _reset("benchmark/demo")
            st.rerun()
    with col_run:
        if st.button("🚀 运行修复", type="primary"):
            llm = _get_llm()
            if llm is None:
                st.warning("请先在左侧侧边栏填写 DeepSeek API Key。")
            else:
                _write_text("benchmark/demo/calc.py", calc_val)
                _write_text("benchmark/demo/test_calc.py", test_val)
                try:
                    with st.spinner("agent 正在读代码、改 bug、跑测试..."):
                        out = _run(llm, "benchmark/demo", "pytest test_calc.py -q", reset=False)
                    _render_trace(out)
                    _render_before_after(calc_val, _read_text("benchmark/demo/calc.py"))
                    _render_tokens(out["tokens"])
                except Exception as e:
                    st.error(f"运行出错：{e}")

# ---------- 一键评测 ----------
with tab_eval:
    st.markdown("**下面是几个小 bug，代码可直接修改，也能在底部添加你自己的 bug。**")
    st.caption("这只是**快速演示**（手写小 bug），不是严谨评测。真正的评测用 `scripts/mine_bugs.py` + `scripts/evaluate.py`。")

    base_bugs = [
        {"id": "字符串反转", "repo": "benchmark/demo-benchmark/reverse"},
        {"id": "空列表求平均", "repo": "benchmark/demo-benchmark/average"},
        {"id": "大写元音计数", "repo": "benchmark/demo-benchmark/vowels"},
    ]
    extra_bugs = st.session_state.get("extra_bugs", [])
    bugs = base_bugs + extra_bugs

    edits = {}
    for b in bugs:
        with st.expander(f"🐛 {b['id']}", expanded=False):
            cc1, cc2 = st.columns(2)
            with cc1:
                st.markdown("**`mylib.py`**")
                code = st.text_area("代码", value=_read_text(f"{b['repo']}/mylib.py"), key=f"{b['repo']}_code", height=110, label_visibility="collapsed")
            with cc2:
                st.markdown("**`test_mylib.py`**")
                test = st.text_area("测试", value=_read_text(f"{b['repo']}/test_mylib.py"), key=f"{b['repo']}_test", height=110, label_visibility="collapsed")
            edits[b["repo"]] = (code, test)

    if st.button("📊 开始演示", type="primary"):
        llm = _get_llm()
        if llm is None:
            st.warning("请先在左侧侧边栏填写 DeepSeek API Key。")
        else:
            results = []
            total_tokens = {"prompt": 0, "completion": 0, "total": 0}
            progress = st.progress(0, text="运行中...")
            for i, b in enumerate(bugs):
                code, test = edits[b["repo"]]
                _write_text(f"{b['repo']}/mylib.py", code)
                _write_text(f"{b['repo']}/test_mylib.py", test)
                try:
                    out = _run(llm, b["repo"], "pytest test_mylib.py -q", reset=False)
                    results.append({"任务": b["id"], "结果": "✅ 修复" if out["success"] else "❌ 未修复", "步数": out["steps"]})
                    for k in total_tokens:
                        total_tokens[k] += out["tokens"].get(k, 0)
                    # 展示该 bug 的完整 ReAct 过程（思考→行动→观察）
                    label = f"🐛 {b['id']} — {'✅ 修复' if out['success'] else '❌ 未修复'}（{out['steps']} 步）"
                    with st.expander(label, expanded=(i == 0)):
                        _render_trace(out)
                except Exception as e:
                    results.append({"任务": b["id"], "结果": "❌ 异常", "步数": "-"})
                    st.error(f"{b['id']} 运行出错：{e}")
                progress.progress((i + 1) / len(bugs), text=f"已完成 {i + 1}/{len(bugs)}")

            st.table(results)
            resolved = sum(1 for r in results if "✅" in r["结果"])
            st.metric("修复成功率", f"{resolved}/{len(bugs)} = {resolved / len(bugs) * 100:.0f}%")
            _render_tokens(total_tokens)

    with st.expander("➕ 添加你自己的 bug"):
        new_name = st.text_input("bug 名称", placeholder="例如：列表去重")
        new_code = st.text_area("代码 `mylib.py`", height=110, placeholder="def dedup(xs):\n    return xs")
        new_test = st.text_area("测试 `test_mylib.py`", height=90, placeholder="from mylib import dedup\n\n\ndef test_dedup():\n    assert dedup([1, 1, 2]) == [1, 2]")
        if st.button("➕ 添加"):
            if not (new_name.strip() and new_code.strip() and new_test.strip()):
                st.warning("名称、代码、测试都要填。")
            else:
                repo = f"benchmark/demo-benchmark/{new_name.strip()}"
                (ROOT / repo).mkdir(parents=True, exist_ok=True)
                _write_text(f"{repo}/mylib.py", new_code)
                _write_text(f"{repo}/test_mylib.py", new_test)
                st.session_state.setdefault("extra_bugs", []).append({"id": new_name.strip(), "repo": repo})
                st.success(f"已添加 bug：{new_name.strip()}")
                st.rerun()
