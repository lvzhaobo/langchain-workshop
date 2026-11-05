# Samples

> **完整项目，学员读代码、讲师演示全景。** labs 你改代码，samples 你读代码。
>
> 每个项目都能单独阅读；需要运行的，见各目录 README。

## 索引（8 个）

| 编号 | 项目 | 内容 | py | 体积 |
|:--:|---|---|--:|--:|
| `01-LangChain实验集` | agent-basic / rag-faiss / hitl / callbacks / lcel | 带 `_offline_utils.py` + 5 个 skeleton | 14 | 392K |
| **`02-BATWork渐进教程`** | **step1 骨架 → step10 技能市场，10 步** | **唯一 100% 自包含** | **87** | 1.2M |
| `03-四天课程包` | day1–day4 | 课程打包 | 17 | 508K |
| `04-基于图的Agent` | 线性链 / 条件分支 / 并行扇出 / 循环重试 / Supervisor / HITL / 子图 | 图模式 7 种 | 10 | 248K |
| `05-Agent记忆分层` | 记忆分层 + 用户画像 | 记忆体系 | 5 | 168K |
| `06-RAG智能客服` | FastAPI + ChromaDB + H5 前端 | 完整 RAG 项目 | 4 | 128K |
| `07-5G设备平台` | app.py + agents + templates + data | LangGraph + Flask | 3 | 56K |
| `08-LangGraph演示集` | MCP / deepagents / memory-demo | 小演示集合 | 8 | 84K |

合计 **8 个 / 2.8M**。

## 三个重点

**`02-BATWork渐进教程` 最干净** —— 10 个 step 全部自包含，9 个有 `requirements.txt`，
是唯一"拆开就能跑"的。

**`01-LangChain实验集` 和 labs 重叠最多** —— 自带 `_offline_utils.py` 和 5 个 `*_skeleton.py`，
是给 `labs/04–26` 做离线化的现成模板。

**`06-RAG智能客服` 最完整的单项目** —— backend + frontend + `start.sh` + README。
但 `requirements.txt` 锁 `langchain==0.1.20`（2024 年），和现在的 1.3.11 差两代，**必须重写**。

## 运行前提

| 缺什么 | 涉及 |
|---|---|
| 没有 `requirements.txt` | 除 `02` 外全部 |
| 没有「怎么跑」说明 | 多数只有项目说明 |
| 依赖外部服务 | LLM API / Dify / 向量库 |
| 版本是老的 | `06` 锁 `langchain==0.1.20`；`02` 用 `langgraph>=0.2.0` |
