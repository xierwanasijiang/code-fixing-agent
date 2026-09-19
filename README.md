# 代码修复 Agent

从零手写的 ReAct 代码 bug 修复 Agent，不用 LangChain/LangGraph，只用 DeepSeek 的 function calling。

## 架构

四层结构，各司其职：

```
┌─────────────────────────────────────────────┐
│ 1. Agent 循环（大脑）  手写 ReAct 循环         │
│    LLM 决策 → 调用工具 → 观察结果 → 再决策    │
├─────────────────────────────────────────────┤
│ 2. 工具集（手）                                │
│    读文件 / 搜索代码 / 改文件 / 跑测试 / 列文件 │
├─────────────────────────────────────────────┤
│ 3. 执行环境（沙盒）                            │
│    被修的 Python 仓库 + 它的测试，隔离运行     │
├─────────────────────────────────────────────┤
│ 4. 评测层（裁判）                              │
│    benchmark 里的 bug + 修复成功率 + 消融     │
└─────────────────────────────────────────────┘
```

- **Agent 循环**：手写 ReAct 循环（`src/code_agent/loop.py`），核心是一个 `while` + prompt 拼装 + 一次 API 调用，约 300 行。LLM 决策 → 调用工具 → 观察结果 → 再决策，直到测试通过 / 超出步数上限 / 模型宣布放弃。
- **工具集**（5 个，`src/code_agent/tools.py`）：`list_files` / `read_file` / `search_code` / `edit_file` / `run_test`。
- **沙盒**（`src/code_agent/sandbox.py`）：在独立 git checkout 里改代码，跑测试用 `subprocess` + 超时，跑完 `git checkout -- .` 重置，保证 bug 之间互不污染。
- **评测层**：自建真实 bug benchmark + 修复成功率 + 消融实验。

完整的架构、设计决策与非目标，见设计文档 [docs/superpowers/specs/2026-09-19-code-agent-design.md](docs/superpowers/specs/2026-09-19-code-agent-design.md)。

## 快速开始

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 配置 DeepSeek API key
export DEEPSEEK_API_KEY=你的key      # Windows: set DEEPSEEK_API_KEY=你的key

# 3. 阶段 0：体会 function calling 闭环（模型调用 get_weather 工具）
python scripts/demo_weather.py

# 4. 阶段 1：端到端修好 benchmark/demo 里的 bug
python scripts/demo_fix.py

# 5. 阶段 2：从目标库 git 历史挖真实 bug（<repo_url> <repo_name> <max_bugs>）
python scripts/mine_bugs.py https://github.com/Textualize/rich.git rich 30

# 6. 阶段 3：在 benchmark 上全量评测，统计修复成功率
python scripts/evaluate.py

# 7. 阶段 3：消融实验（变量名可选 no_search / model / max_steps）
python scripts/ablate.py no_search ""
python scripts/ablate.py model deepseek-reasoner
python scripts/ablate.py max_steps 5
```

> 运行 `demo_weather.py` / `demo_fix.py` / `mine_bugs.py` / `evaluate.py` / `ablate.py` 都需要先配置 `DEEPSEEK_API_KEY`。

## 结果

> ⚠️ 以下数字尚未填写：真实评测依赖 `DEEPSEEK_API_KEY`，**待配置 key 并运行 `python scripts/evaluate.py` 与 `python scripts/ablate.py` 后，将真实数字回填到本节**。

- 修复成功率：`X/30 = Y%`
- 消融：
  - 去掉 `search_code` 工具后成功率下降 `Z%`
  - 换 `deepseek-reasoner` 后成功率变化 `±W%`
  - `max_steps=5` 时成功率变化 `±V%`

## 亮点

- 约 300 行手写 ReAct 循环，不套 LangChain/LangGraph
- 自建真实 bug benchmark（从 git 历史挖掘 fix 提交 + 失败测试）
- 可复现评测 + 消融实验，能量化每个设计决策的价值

## 测试

```bash
python -m pytest -q
```

`pytest.ini` 中 `testpaths = tests`，只收集 `tests/` 下的单元测试（`benchmark/demo` 里故意留 bug 的 `test_calc.py` 不会被当作失败用例收集）。
