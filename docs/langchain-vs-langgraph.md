# LangChain 与 LangGraph：为什么这个 workshop 叫 langgraph

> 学员最常问的两个问题：这两个是什么关系？我该学哪个？

## 一句话

| | 定位 | 类比 |
|---|---|---|
| **LangChain** | **零件库 + 生态**：模型、Prompt、解析器、检索器、向量库、工具、社区集成 | 乐高积木 |
| **LangGraph** | **编排层**：把零件连成一张有状态、可循环、可暂停恢复的图 | 拼装说明书 + 底板 |

**LangGraph 不替代 LangChain，它建立在 LangChain 之上**——`langgraph` 依赖 `langchain-core`，节点里调用的模型、工具、检索器都还是 LangChain 的对象。

## 为什么 workshop 叫 langgraph

因为本课的**教学主线是「图」**，不是「API 大全」：

- lab-01：State / Node / 条件边 —— 纯 langgraph
- lab-02：工具循环 —— `ToolNode` + `@tool`（`@tool` 来自 langchain-core）
- lab-03：Checkpointer / thread_id —— 纯 langgraph

如果叫 `langchain-workshop`，学员会以为是"把 40 个 Chain 的 API 背一遍"，那是两天也讲不完的目录，而且**背完还是不会做 Agent**。

**LangChain 的内容放在 `docs/cheatsheet/` 和 `samples/` 里**——用到什么查什么，不做穷举。

## 本 workshop 实际用到的 LangChain 组件

| 组件 | 来自 | 用在哪 |
|---|---|---|
| `ChatOpenAI` / `init_chat_model` | `langchain-openai` | samples（labs 用假模型替代） |
| `@tool` 装饰器 | `langchain-core` | lab-02 |
| `AIMessage` / `ToolMessage` / `HumanMessage` | `langchain-core` | lab-02 |
| `RecursiveCharacterTextSplitter` | `langchain-text-splitters` | samples（RAG） |
| `Chroma` 向量库 | `langchain-community` | samples（RAG） |
| Prompt 模板 | `langchain-core` | samples |

labs 只依赖 `langchain-core`，所以**离线可跑**；samples 才需要 `langchain-openai` 等外部集成。

## 什么时候不需要 LangGraph

不是所有场景都要上图。判定很简单：

| 你的需求 | 该用什么 |
|---|---|
| 一次调用就能出结果（翻译、摘要、分类） | **直接调模型**，连 LangChain 都不用 |
| 固定顺序的几步（取数据 → 拼 prompt → 调模型 → 解析） | **LCEL 管道**（LangChain Expression Language）就够了 |
| 需要**循环**（调工具、重试、多轮反思） | **LangGraph** |
| 需要**人工介入**（HITL，暂停等审批） | **LangGraph**（interrupt） |
| 需要**记住历史、多会话隔离、断点续跑** | **LangGraph**（checkpointer） |
| 需要**多个 Agent 协作** | **LangGraph**（子图 / supervisor） |

**判断口诀：有环、有状态、要暂停 —— 就上 LangGraph。全是直线就用 LCEL。**

## 版本提醒（很重要）

LangChain 1.x 与 0.x **不兼容**，LangGraph 1.x 与 0.2.x 也有 breaking change。

- 本 workshop 锁定：`langgraph==1.2.7` / `langchain-core==1.5.1`
- 网上大量 2024–2025 年的教程是 0.1.x / 0.2.x 写的，**直接抄会跑不起来**
- 遇到报错先看版本，别怀疑自己的代码

```bash
pip list | grep -E "langchain|langgraph"
```
