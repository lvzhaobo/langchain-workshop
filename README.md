# LangChain Workshop

> **LangChain / LangGraph / LangSmith / LangServe —— 代码栈全覆盖，不含低代码平台。**
>
> 在 macOS 上，`./setup.sh` + `./run.sh 01` 就能跑通 **labs 01–03**。
> **离线、不需要 API Key、不联网跑推理。**
>
> 其余 13 个实验需要先配好 `.env` 里的 Key —— 见下方状态表。

## 为什么叫 langchain 而不是 langgraph

`LangGraph`、`LangSmith`、`LangServe` 全属于 **`langchain-ai`** 这个 GitHub 组织，
`langgraph` 还依赖 `langchain-core`。**LangChain 是家族，LangGraph 只是其中一个包。**

用 `langgraph` 命名等于用包名装全家。详见 [docs/langchain-vs-langgraph.md](docs/langchain-vs-langgraph.md)。

**和 Dify / 扣子的区别**不是"能不能做 Agent"，而是**谁来写逻辑**：

| | 你写的产物 | 代表 |
|---|---|---|
| **代码栈**（本仓库） | `.py` 文件 | LangChain / LangGraph / LangSmith / LangServe |
| 低代码平台 | DSL / 应用配置 JSON | Dify / 扣子 / n8n |

## 这是什么

一套 **Hands-on Lab** 式的培训材料：

- **`labs/`** —— 15–30 分钟的动手实验。**你来写代码**，每个 lab 有 `solution.py` 兜底。
- **`samples/`** —— 完整项目，**你来读代码、看全景**，讲师现场演示。
- **`docs/`** —— 原理文档 26 篇、CheatSheet、环境准备、lab 设计文档。

两者的关系：**上午看 sample 的全景，下午用它的一部分做 lab。**

**依赖分层**：`labs/` 只依赖 `langchain-core`，所以**完全离线可跑**；`samples/` 才需要
`langchain-openai` 等外部集成。这个分层是故意的——现场一半人会卡在 Key 和额度上。

## 3 条命令开始（macOS）

```bash
cd langchain-workshop
./setup.sh          # 建 .venv（Python 3.11）并装依赖，首次 1–3 分钟
./run.sh 01     # 跑 Lab 01
```

**不需要手动 `activate` venv**，所有脚本都会自己找到 `.venv/bin/python`。

想先确认环境对不对：

```bash
./doctor.sh
```

```
venv python : .venv/bin/python
Python 3.11.15
langgraph      : 1.2.7
langchain-core : 1.5.1
uv             : ~/.local/bin/uv
```

装依赖卡住了看 [docs/01-环境准备.md](docs/01-环境准备.md)。

## 换成别的模型（不需要改代码）

所有 lab 都走 **OpenAI 兼容协议**，换 provider 只改两个环境变量：

```bash
cp .env.example .env
# 然后把 AGENT_API_BASE / AGENT_MODEL 换成你要用的
```

| 想用 | AGENT_API_BASE | AGENT_MODEL |
|---|---|---|
| DeepSeek（默认） | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 本地 Ollama（零成本） | `http://localhost:11434/v1` | `qwen2.5:7b` |
| 本地 vLLM | `http://localhost:8000/v1` | `Qwen/Qwen2.5-7B-Instruct` |

完整配置（含 Embedding、常见报错、换模型后要重建索引）见
[docs/模型配置.md](docs/模型配置.md)。

## 现在有哪些 lab

**26 个并列编号，`labs/01`–`labs/26`。**

| Lab | 主题 | 状态 |
|---|---|---|
| [**01**](./labs/01-hello-graph/) | 最小 StateGraph：State / Node / 条件边 | ✅ 离线可跑 |
| [**02**](./labs/02-tools/) | 工具调用循环：assistant → tools | ✅ 离线可跑 |
| [**03**](./labs/03-memory/) | Checkpointer 与 thread_id 记忆隔离 | ✅ 离线可跑 |
| **12 14 16 17 19-23** | RAG / 多 Agent / 生产化 | ⬜ 需配 Key |

**现在零 Key 就能跑的是 5 个：`01 02 03 05 10`。** 其余 21 个需要配 `.env` 里的 Key。
`./run.sh 06` 会报"缺 Key"——这是事实，不是 bug。

05 和 10 是靠 [`_mock_llm.py`](docs/零Key模式.md) 跑通的：没配 Key 时回放预设回复，
配了 Key 就走真模型，**代码不用改**。

两个低代码对照：`04-DifyAgent`、`15-Dify-RAG-Agent` 用的是 **Dify**，不在 LangChain 代码栈里，
验收物是导出的 DSL 而不是 `.py`。

完整的能力分布见 [labs/README.md](labs/README.md)。

## 每个 lab 怎么用

在**仓库根目录**执行，不用 cd 进 lab 目录：

```bash
./run.sh 01         # 跑你的代码（有 TODO）
./check.sh 01       # 验收你的代码
./check.sh 01 -s    # 验收参考答案
./run.sh 01             # 短别名，等价于 lab-01
```

每个 lab 的 `README.md` 才是操作指引（目标 / 步骤 / 验收 / 卡住了怎么办）。
想进去手动跑也行：

```bash
source .venv/bin/activate
cd labs/01-hello-graph && python check.py
```

**卡住超过 3 分钟就看 `solution.py`**，不要硬扛——培训时间是固定的。

## 仓库级自检

```bash
./verify.sh        # 跑全部 lab 的参考答案，应全绿
```

## 目录

```
langchain-workshop/
├── README.md
├── setup.sh               ← 建 venv + 装依赖（跑一次）
├── run.sh                 ← ./run.sh 01
├── check.sh               ← ./check.sh 01 [-s]
├── verify.sh              ← 验收全部已适配的 lab
├── doctor.sh              ← 环境自检
├── clean.sh               ← 删 .venv 与缓存
├── requirements.txt       ← uv compile 出来的锁定版本（81 个包）
├── requirements.in        ← 手工维护的直接依赖
├── .env.example           ← 模型配置模板（支持换 provider）
├── docs/
│   ├── 00-全景图.md
│   ├── 01-环境准备.md
│   ├── 模型配置.md         ← 换 DeepSeek / OpenAI / 通义 / 本地
│   ├── 零Key模式.md        ← 不配 Key 也能跑通的做法
│   ├── langchain-vs-langgraph.md
│   ├── 原理/              9 篇：Pregel/Checkpoint、Stream/HITL/Subgraph、三层上下文、Memory 体系…
│   ├── cheatsheet/        LangChain 全家桶 CheatSheet（md + html）
│   └── lab设计/lab7-langchain/   11 个 lab 设计文档 + 7 个 skeleton
│                                 （含 labs 里缺的 LangServe / LangSmith / evals / Web UI / Ops）
├── labs/                  26 个并列编号
│   ├── _template/
│   ├── 01-hello-graph … 03-memory    已适配，离线可跑
│   └── 04-DifyAgent … 26-LLM裁判工程  需配 Key
└── samples/               8 个完整项目
    ├── 01-LangChain实验集
    ├── 02-BATWork渐进教程    10 步，100% 自包含
    └── …
```

## 三条约定

1. **lab 里的代码必须能离线跑**。要用模型的地方一律先用假模型，讲清机制后再换成真模型。
2. **每个 lab 单一可验证产出**。做不完就该拆成两个。
3. **`labs/NN-xxx` 的编号永不重排**。外部 PPT、文章、视频会引用这些路径。
