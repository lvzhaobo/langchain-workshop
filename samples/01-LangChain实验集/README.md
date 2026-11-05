# Sample 7 — LangChain 实验集

> 七个递进式实验，从基础 Agent 到多 Agent 协作，覆盖 LangChain + LangGraph 核心能力

## 两种运行模式

所有实验都支持两种运行模式：

```bash
# 在线模式（需要百炼 API Key）
export DASHSCOPE_API_KEY=你的Key
python 01-agent-basic/agent_basic.py

# 离线模式（无需任何外部 API，纯本地运行）
python 01-agent-basic/agent_basic.py --offline
```

**离线模式工作原理**：用纯 Python 模拟 LLM 响应，但数据流和工具调用（查 JSON 文件）100% 真实执行。代码结构不变，方便在没有外网的教室里演示完整流程。

## 实验地图

```
sample7/
├── README.md                          # 本文件
├── _offline_utils.py                  # 离线模式共享工具
├── equipment_data.json                # 共享数据：12 台电力设备
├── knowledge_base.json                # 共享数据：12 篇电力技术文档
│
├── 01-agent-basic/                    # 实验一：ReAct Agent 基础 ⭐
│   └── agent_basic.py                 #   @tool → create_react_agent → ReAct 循环
│
├── 02-rag-faiss/                      # 实验二：FAISS + RAG ⭐⭐
│   └── rag_faiss.py                   #   Embedding → FAISS 索引 → 检索增强生成
│
├── 03-hitl/                           # 实验三：Human-in-the-Loop ⭐⭐⭐
│   └── hitl_workflow.py               #   StateGraph + interrupt_before → 人工审批
│
├── 04-callbacks/                      # 实验四：回调监控 ⭐⭐
│   └── callbacks_demo.py              #   生命周期事件 → Token 用量 → 延迟统计
│
├── 05-multi-agent/                    # 实验五：多 Agent 协作 ⭐⭐⭐
│   └── multi_agent.py                 #   Supervisor 调度 → 3 个专家 Agent
│
├── 06-memory/                         # 实验六：Memory 机制对比 ⭐⭐
│   └── memory_compare.py              #   Buffer / Window / Summary → Token vs 信息保留
│
├── 07-lcel-struct/                    # 实验七：LCEL + 结构化输出 ⭐⭐
│   └── lcel_demo.py                   #   pipeline | passthrough | with_structured_output()
│
├── lab7.*.md                          # 参考讲义（11 篇）
└── *_skeleton.py                      # 骨架代码（供动手实验使用）
```

## 实验能力矩阵

| 实验 | 核心概念 | 难度 | 离线可跑 |
|:---:|----------|:----:|:---:|
| **01-agent-basic** | `@tool`、`create_react_agent`、ReAct 循环、LLM vs Agent 对比 | ⭐ | ✅ |
| **02-rag-faiss** | Embedding、FAISS 索引、语义检索、RAG、有/无 RAG 对比 | ⭐⭐ | ✅ |
| **03-hitl** | `StateGraph`、`interrupt_before`、`Command`、Checkpointer | ⭐⭐⭐ | ✅ |
| **04-callbacks** | 回调事件链、Token 统计、延迟监控、成本核算 | ⭐⭐ | ✅ |
| **05-multi-agent** | Supervisor 模式、三专家 Agent、共享 State、循环调度 | ⭐⭐⭐ | ✅ |
| **06-memory** | Buffer/Window/Summary 三种策略、跨轮记忆验证 | ⭐⭐ | ✅ |
| **07-lcel-struct** | LCEL 管道、RunnablePassthrough、`with_structured_output()` | ⭐⭐ | ✅ |

## 快速开始

### 环境准备

```bash
# 离线模式 — 无需任何依赖即可运行
python 01-agent-basic/agent_basic.py --offline

# 在线模式 — 需要安装依赖
pip install langchain langchain-openai langgraph langchain-community faiss-cpu pydantic
export DASHSCOPE_API_KEY=你的Key

# 在线模式运行
python 01-agent-basic/agent_basic.py
```

### 推荐学习路径

```
实验一（Agent 基础）→ 理解 ReAct 循环和工具调用
    ↓
实验二（RAG）→ 理解向量检索和检索增强生成
    ↓
实验七（LCEL）→ 理解 LangChain 的核心语法和结构化输出
    ↓
实验六（Memory）→ 理解多轮对话的记忆策略
    ↓
实验四（Callbacks）→ 理解监控和可观测性
    ↓
实验三（HITL）→ 理解工作流中断和人工审批
    ↓
实验五（Multi-Agent）→ 理解多 Agent 协作和 Supervisor 调度
```

## 实验数据

两个 JSON 文件在 sample7 根目录，所有实验共享：

- `equipment_data.json` — 12 台电力设备（变压器、断路器、输电线路、配电柜、开关柜）
- `knowledge_base.json` — 12 篇电力技术文档（故障诊断、巡检规程、技术规范、试验标准等）
