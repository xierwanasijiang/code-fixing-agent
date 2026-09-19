# 代码修复 Agent（Code Bug-Fixing Agent）

> 一个**从零手写**的 ReAct 代码修复智能体：你给它一段报错的代码或一个仓库，它会自己思考、动手、验证，一步步把 bug 修好。**不使用 LangChain / LangGraph 等任何 Agent 框架**，只用大模型（DeepSeek/OpenAI）的 function calling。

---

## 它能做什么

给你一个报错的场景，agent 会按「思考 → 行动 → 观察」的循环反复迭代，直到修复：

```
💭 思考：观察到测试在 test_divide_by_zero 失败，说明 divide 没处理除 0；决定先读 calc.py 确认
🔧 行动：read_file(calc.py)
👁 观察：读到了 `return a / b`，没有除 0 判断
💭 思考：决定加 if b == 0 的判断
🔧 行动：edit_file(...)
🧪 验证：run_test → returncode=0，1 passed
✅ 修复成功
```

界面（Streamlit）会把上面**每一步的思考、行动、观察都可视化出来**，让你看清 agent 到底在干什么。

## 三个功能

| 页签 | 用途 | 用的工具 |
|------|------|---------|
| 📝 **粘贴修复** | 贴一段报错代码 + 报错信息，agent 真运行、真调试、修好它 | `run_snippet`（执行验证） |
| 🔧 **仓库修复** | agent 在真实仓库里修 bug（代码可编辑、可重置） | `read_file`/`edit_file`/`run_test`/`search_code`/`list_files` |
| 📊 **批量演示** | 一批 bug 上跑修复成功率（每个 bug 的 ReAct 过程可展开看） | 仓库那套工具 |

## 为什么要看这个项目（价值所在）

1. **从零手写 ReAct 循环**——不是 `import langchain` 调库，而是自己实现了 Thought-Action-Observation 的完整循环，真正理解 agent 内部发生了什么。
2. **工具执行安全**——agent 能调工具，就意味着模型输出能触达你的机器。本项目做了**命令白名单**（只允许跑 pytest）和**路径穿越校验**（read/edit 越界直接拒绝），这是绝大多数教程项目没有的。
3. **有基线对比实验**——没有对比的"我的 agent 很牛"是耍流氓。本项目写了 `scripts/compare.py`，在同一批 bug 上对比「agent」和「直接问一次 LLM」。
4. **token 花费追踪**——每次运行都统计输入/输出 token 和估算成本。
5. **工程规范**——TDD、单元测试、完整 git 提交历史、清晰的模块划分。

## 涉及的核心知识点

| 知识点 | 在项目里对应什么 |
|--------|-----------------|
| **ReAct 范式** | `loop.py` 里的思考-行动-观察循环 |
| **Function Calling（工具调用）** | `tools.py` 里 6 个工具的 JSON schema + 执行分发 |
| **OpenAI 兼容协议** | `llm.py` 用 `openai` SDK 指向 DeepSeek，消息按 `assistant.tool_calls` + `role:"tool"` 回传 |
| **上下文管理** | `context.py` 管理多轮消息，超长观察结果截断 |
| **工具安全** | 命令白名单 + 路径穿越校验 + 执行超时 |
| **评测方法** | `mine_bugs.py`（挖真实 bug）、`evaluate.py`（成功率）、`compare.py`（基线对比）、`ablate.py`（消融） |
| **Prompt 工程** | `prompts.py` 的系统提示词 + 引导思考的提问 |

## 快速开始（一键运行）

**前置**：安装 Python 3.10+（[python.org](https://www.python.org) 下载，安装时勾选 "Add to PATH"）。

然后**双击 `启动界面.bat`**，它会自动：

1. 检查依赖（streamlit / openai / pytest）是否装好；
2. 没装就问你「是否现在安装」，选 Y 自动安装；
3. 装好后就启动界面，浏览器自动打开 `http://localhost:8501`。

**接着在界面左侧侧边栏填入你自己的 API Key**（去 [platform.deepseek.com](https://platform.deepseek.com) 免费申请一个；key 只存在当前会话，不会保存、不会上传），就能开始用了。

> 手动运行也可以：
> ```bash
> pip install -r requirements.txt
> python -m streamlit run app.py
> ```

## 评测与基线对比（诚实结论）

在 `scripts/make_real_bugs.py` 手写的 8 个真实 bug 模式（可变默认参数、保序去重、大小写、off-by-one、递归缺基准、递归 flatten、返回哨兵值错误、过滤负数等）上：

- **基线（直接把代码+测试塞给 LLM 问一次）：8/8 = 100%**
- **agent（完整 ReAct 循环）：8/8 = 100%**

结论很诚实：**在"单函数、单个清晰 bug"这种简单场景，一次问 LLM 和完整 agent 持平**——因为强模型看一遍就能修对，agent 的多步循环是冗余。

**agent 的价值在"一次问不出来"的场景**：多文件、需要探索搜索、第一次修复会错的 bug。这需要更难的真实 benchmark（本项目的 `mine_bugs.py` + `evaluate.py` 已为此写好，从真实仓库 git 历史挖 bug），这是进一步工作的方向。

> 这个"诚实承认 agent 在简单场景无优势"的结论，本身就是一个有说服力的点：它说明你会做对照实验、会质疑自己的东西。

## 项目结构

```
├── 启动界面.bat            # 一键启动（检查/安装依赖 + 打开界面）
├── app.py                  # Streamlit 界面
├── requirements.txt        # 依赖
├── src/code_agent/         # 核心代码
│   ├── llm.py              #   LLM 客户端 + 响应解析 + token 用量
│   ├── prompts.py          #   系统提示词 + 思考引导
│   ├── context.py          #   上下文（消息列表）管理
│   ├── tools.py            #   5 个仓库工具 + 安全校验 + 执行分发
│   ├── sandbox.py          #   沙盒：跑 pytest、reset 仓库、subprocess 环境
│   ├── loop.py             #   ReAct 主循环（思考→行动→观察）
│   └── snippet.py          #   粘贴修复模式（run_snippet 工具 + 循环）
├── scripts/                # 命令行脚本
│   ├── demo_weather.py     #   最小 function calling 演示
│   ├── demo_fix.py         #   端到端修一个 bug
│   ├── mine_bugs.py        #   从真实仓库 git 历史挖 bug
│   ├── evaluate.py         #   批量评测
│   ├── compare.py          #   基线 vs agent 对比
│   ├── ablate.py           #   消融实验
│   └── make_real_bugs.py   #   生成真实 bug 模式评测集
├── benchmark/              # 评测用的 bug（demo / 手写真实 bug / 挖出的实例）
└── tests/                  # 单元测试（28 个）
```

## 运行测试

```bash
python -m pytest
```

## 技术栈

- **语言**：Python 3.10+
- **模型**：DeepSeek `deepseek-chat`（OpenAI 兼容，`openai` SDK，换 OpenAI/GPT 只需改 base_url 和模型名）
- **界面**：Streamlit
- **测试**：pytest
- **显式不用**：LangChain / LangGraph / AutoGPT 等 Agent 框架

## License

MIT
