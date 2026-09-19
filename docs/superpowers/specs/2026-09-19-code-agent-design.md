# 代码修复 Agent（Code Bug-Fixing Agent）设计文档

- 日期：2026-09-19
- 状态：待用户评审
- 作者：用户 + Claude Code

## 1. 目标与背景

做一个能放在简历上的 AI Agent 项目，用于投递 **LLM 应用/算法岗**。核心定位不是"又一个 LangChain 教程 Demo"，而是同时满足三个面试官最看重的能力：

1. **理解 Agent 循环是怎么运作的**（从零手写，不套框架）
2. **有能力量化它好不好**（自建真实 benchmark + 修复成功率）
3. **能做消融实验证明每个设计都有用**（去掉某工具/换模型会怎样）

### 关键约束

| 维度 | 决策 |
|------|------|
| 目标岗位 | LLM 应用 / 算法岗 |
| 技能基础 | Python 熟练，LLM 新手 |
| 项目场景 | 代码 Agent（修 bug） |
| 时间预算 | 1-2 个月（快速出 MVP） |
| 模型 | DeepSeek（`deepseek-chat`，OpenAI 兼容，支持 function calling） |
| 项目根目录 | `D:\AIagent项目` |

## 2. 总体架构

四层结构：

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

## 3. 核心 Agent 循环（ReAct，手写）

```
1. 给 LLM 输入：任务描述（"让这条失败测试通过"）
   + 当前上下文（已看过的文件/报错/历史动作）
2. LLM 返回一个动作：调用某个工具，或宣布"我修好了"
3. 循环代码执行该工具，拿到结果（文件内容/报错/测试结果）
4. 把结果塞回上下文，回到第 2 步
5. 直到：测试通过（成功）/ 超出步数上限（失败）/ 模型宣布放弃
```

伪代码：

```python
context = [system_prompt, user_task]
for step in range(MAX_STEPS):
    response = call_llm(context)            # 带 tools 的 API 调用
    if response.is_final_answer():
        break
    tool_name, args = response.tool_call()
    result = execute_tool(tool_name, args)  # 在沙盒里执行
    context.append(observation(result))     # 把结果塞回上下文
```

### 为什么手写、不用 LangChain/LangGraph

- 循环本质是 `while` + prompt 拼装 + 一次 API 调用，核心 200-400 行。
- 手写才能真正理解上下文里装了什么、token 怎么涨、模型为什么跑偏——这正是算法岗面试追问的点。
- 简历上"用 300 行从零实现 ReAct 循环"远胜"我会调 LangGraph"。

## 4. 工具集（5 个）

| 工具 | 作用 | 实现 |
|------|------|------|
| `list_files` | 列出目录结构 | `os.listdir` / `pathlib` |
| `read_file` | 读某个文件（可带行号范围） | `open().read()`，超长截断 |
| `search_code` | 按关键词/正则搜代码 | `grep` / `ripgrep` |
| `edit_file` | 修改文件（定位 + 替换） | 读-改-写，或 `apply_patch` |
| `run_test` | 跑指定测试 | `subprocess.run(["pytest", ...], timeout=...)` |

## 5. 执行环境（沙盒隔离）

- Agent 在一个**独立的 git worktree / 干净 checkout** 里改代码，避免弄脏主目录。
- 跑测试用 `subprocess.run(["pytest", test_path], timeout=..., capture_output=True)`，跑飞就超时杀掉。
- 每次评测结束后重置环境（`git checkout -- .`），保证 bug 之间互不污染。

## 6. 评测体系（项目灵魂）

### 6.1 benchmark 来源

- 从一个**真实的纯 Python 库**（推荐起步：`rich` 或 `click`）的 git 历史里挖 20-30 个真实 bug。
- 挖法：找 commit message 含 `fix`/`bug` 且同时改了测试的提交；"修之前"= bug，"修之后"= 标准答案，"新增的失败测试"= 验证器。
- 用脚本自动产出 `benchmark/` 目录，每个 bug 一个文件夹，含：
  - 仓库的 bug 版本（checkout 到修之前的 commit）
  - 标准答案 diff（供对照，评测时不给模型）
  - 验证测试（FAIL_TO_PASS：修之前失败、修之后应通过）
- 不用 SWE-bench 全集：手写小 agent 在上面成功率接近 0，简历数字难看。

### 6.2 主指标

- **`resolved`（修复成功率）**：验证测试在 agent 改完后是否全部通过。
  `成功率 = 通过的 bug 数 / 总 bug 数`
- 辅助指标：平均步数、平均 token 消耗、超时/超步数比例。

### 6.3 消融实验（2-3 个，证明设计有用）

1. 去掉 `search_code` 工具 → 成功率降多少？（证明搜索工具的价值）
2. 换成 `deepseek-reasoner` 或更强模型 → 成功率变多少？（证明模型选择的影响）
3. 限制最大步数 → 成功率与成本的关系曲线。

## 7. 技术栈

- 语言：Python 3.10+
- LLM：DeepSeek `deepseek-chat`，通过 `openai` SDK（`base_url="https://api.deepseek.com"`）
- 测试：`pytest`
- 其他：`git`、`subprocess`、`pathlib`
- 显式不用：LangChain / LangGraph / AutoGPT 等框架

## 8. 里程碑（4 阶段，约 6 周）

| 阶段 | 时间 | 内容 | 交付物 |
|------|------|------|--------|
| 0. 跑通工具调用 | 第 1 周 | 学会 DeepSeek function calling（`get_weather` 例子，多轮回传） | `tool_loop.py`（能跑） |
| 1. 最小 Agent + 2 工具 | 第 1-2 周 | 手写 ReAct 循环，工具仅 `read_file` + `run_test`，修好一个单文件 demo bug | `agent.py` + demo |
| 2. 补全工具 + 建 benchmark | 第 2-4 周 | 工具补到 5 个，挖 bug 脚本产出 20-30 个真实 bug | `benchmark/` + 评测脚本 |
| 3. 评测 + 消融 + 打磨 | 第 4-6 周 | 跑全量评测、做 2-3 个消融、写 README 画图 | 完整 repo + 结果 |

**先决顺序不可跳**：阶段 0 是地基，LLM 新手跳过工具调用直接写 agent 循环必卡。

## 9. 错误处理与边界

- API 调用失败 / 超时：重试 + 记录，不让单次失败中断整轮评测。
- 模型返回非法工具名 / 参数：记录错误并让模型重试，计入步数。
- token 上限：单轮上下文超限时做摘要/截断最旧观察。
- 评测隔离：每个 bug 独立环境，跑完重置。
- 成本控制：设 MAX_STEPS 与单次评测总预算上限。

## 10. 非目标（YAGNI，明确不做）

- 不做多智能体（multi-agent）协作。
- 不做新增功能 / 重构 / 大范围多文件改动。
- 不做前端界面 / Web 服务（纯 CLI + 脚本）。
- 不做向量数据库 / RAG（与本项目无关）。
