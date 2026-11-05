# LangChain 全家桶 × 实验 × Demo 平台 — 功能对比表

> 统计时间：2026-07-25

---

## 一、LangGraph 16 Samples × Demo 平台覆盖

| # | sample | 核心概念 | 后端接口 | 前端页面 | 状态 |
|---|--------|---------|---------|---------|:--:|
| 1 | 线性串联 | Node→Edge→State | 所有接口底层 | 流水线可视化 | ✅ |
| 2 | 条件分支 | add_conditional_edges | Supervisor/HITL 路由 | 审批分叉展示 | ✅ |
| 3 | 并行执行 | Send + fan-out | — | — | ❌ |
| 4 | State 进阶 | reducer | 后端 State 定义 | — | ⚠️ |
| 4b | 真实 State | 排障 State | app.py HITLState | — | ⚠️ |
| 5 | LLM 节点 | ChatModel | sample-6 内含 | Agent 对话 | ✅ |
| 6 | Agent 循环 | ReAct | /agent/single | Agent 中心→LangChain Tab | ✅ |
| 7 | Checkpoint | 断点续跑 | /sessions | — | ⚠️ |
| 8 | HITL | interrupt+resume | /agent/hitl/start+decide | 审批弹窗交互 | ✅ |
| 9 | Stream | 三种 stream_mode | 所有 Agent 口 SSE | 实时打字机 | ✅ |
| 10 | Command | 节点内路由 | — | — | ❌ |
| 11 | 子图 | Subgraph | — | — | ❌ |
| 12 | Supervisor | 多 Agent 调度 | /agent/supervisor | 一键全流程 | ✅ |
| 13 | 记忆系统 | 三层记忆 | — | — | ❌ |
| 14 | RAG | 检索+生成 | /rag/search | 知识库页检索 | ✅ |
| 15 | Prompt+缓存 | 模板+缓存 | — | — | ❌ |
| 16 | Skills 打包 | 模板化 | — | 独立目录 | ⚠️ |
| **覆盖率** | | | | | **10/16** |

---

## 二、LangChain 全家桶功能 × Demo 覆盖

| 模块 | 功能 | 后端 | 前端 | 状态 |
|------|------|:--:|:--:|:--:|
| **LangChain Core** | ChatModel（多模型调用） | ✅ | — | ✅ |
| | Messages（Human/AI/System/Tool） | ✅ | — | ✅ |
| | @tool 工具定义 + bind_tools | ✅ | — | ✅ |
| | ToolNode 自动执行 | ✅ | — | ✅ |
| | Prompt Template | ✅ | — | ✅ |
| | Structured Output（Pydantic） | — | — | ❌ |
| **LangChain RAG** | Document Loader（TextLoader） | ✅ | — | ✅ |
| | Text Splitter | ✅ | — | ✅ |
| | Embeddings（OpenAIEmbeddings） | ⚠️ | — | ⚠️ |
| | FAISS 向量索引 | ⚠️ | — | ⚠️ |
| | Retriever 检索器 | ✅ | 知识库搜索 | ✅ |
| | LCEL 管道语法（`|`） | ✅ | — | ✅ |
| | RAG 评测（RAGAS） | — | — | ❌ |
| **LangGraph** | StateGraph 构建 | ✅ | 流水线展示 | ✅ |
| | add_edge / add_conditional_edges | ✅ | 审批分叉 | ✅ |
| | Checkpoint（MemorySaver） | ✅ | — | ⚠️ |
| | SqliteSaver 持久化 | — | — | ❌ |
| | interrupt / Command(resume) | ✅ | 弹窗审批 | ✅ |
| | Command(goto) 动态路由 | — | — | ❌ |
| | Subgraph 子图嵌套 | — | — | ❌ |
| | Send API 并行派发 | — | — | ❌ |
| | stream_mode（3 种） | ✅ | SSE 流式 | ✅ |
| | Supervisor 多 Agent | ✅ | 一键全流程 | ✅ |
| **LangSmith** | Trace 调用链 | ✅ | — | ⚠️ |
| | Token/延迟监控 | — | — | ❌ |
| **LangServe** | REST API 发布 | ✅ | Flask 替代 | ✅ |
| **LangFlow** | 可视化拖拽 | — | — | ❌ |
| **全家桶覆盖率** | | | | **19/27** |

---

## 三、labs-new 34 个实验 × Demo 覆盖

| Day | # | 实验 | Demo 对应 | 状态 |
|-----|:--:|------|------|:--:|
| D1 | 1.1 | 平台搭建 | 后端 app.py + Flask | ✅ |
| | 1.2a | 扣子 Agent | Agent 中心→Coze Tab（指引） | ⚠️ |
| | 1.2b | Dify Agent | Agent 中心→Dify Tab（指引） | ⚠️ |
| | 1.3 | 平台接入 Agent | /agent/single 接口 | ✅ |
| | 1.4 | LangChain Agent | LangChain Tab→对话 | ✅ |
| | 1.5 | Output Parser | — | ❌ |
| | 1.6 | Agent 类型对比 | — | ❌ |
| | 1.7 | RunnableBranch | Supervisor 路由 | ✅ |
| D2 | 2.1 | FAISS 向量库 | /rag/search | ✅ |
| | 2.2 | DashVector | — | ❌ |
| | 2.3 | 余弦相似度 | — | ❌ |
| | 2.4 | 图片相似度 | — | ❌ |
| | 2.5 | RAG Agent | 知识库检索+LangChain Tab | ✅ |
| | 2.6 | Dify RAG | — | ❌ |
| | 2.7 | Memory 三种策略 | — | ❌ |
| | 2.8 | Callbacks | LangSmith Trace | ⚠️ |
| | 2.9 | LLM Caching | — | ❌ |
| | 2.10 | RAG 评测 | — | ❌ |
| | 2.11 | Text-to-SQL | — | ❌ |
| D3 | 3.1 | 意图路由 | Supervisor 路由 | ✅ |
| | 3.2 | LangGraph 流水线 | /agent/supervisor | ✅ |
| | 3.3 | 进阶协作 | — | ❌ |
| | 3.4 | HITL 审批 | /agent/hitl + 弹窗 | ✅ |
| | 3.5 | 安全护栏 | — | ❌ |
| | 3.6 | 可观测 Trace | LangSmith | ⚠️ |
| | 3.7 | Streaming | SSE 流式 | ✅ |
| | 3.8 | 应用分发 | — | ❌ |
| D4 | 4.1 | SDD Spec | — | ❌ |
| | 4.2 | 单元测试 | — | ❌ |
| | 4.3 | Prompt 回归 | — | ❌ |
| | 4.4 | 云端部署 | — | ❌ |
| | 4.5 | 压力测试 | — | ❌ |
| | 4.6 | Skills 打包 | sample-16 目录 | ⚠️ |
| | 4.7 | 对接真实系统 | 设备数据 API | ✅ |
| **labs-new 覆盖率** | | | | **16/34** |

---

## 四、汇总

| 维度 | 总数 | 已覆盖 | 覆盖率 |
|------|:--:|:--:|:--:|
| LangGraph Samples | 16 | 10 | 63% |
| LangChain 全家桶能力 | 27 | 19 | 70% |
| labs-new 四天实验 | 34 | 16 | 47% |
| **综合** | **77** | **45** | **58%** |

### 未覆盖的集中在

| 类别 | 未覆盖项 | 原因 |
|------|---------|------|
| 并行/子图（s-3/11） | 无 Send/Subgraph 交互入口 | 高级编排，界面不好展示 |
| Memory 体系（s-13/2.7） | 无三层记忆配置 | 需独立的记忆管理页面 |
| Day4 工程化（4.1~4.6） | SDD/测试/部署 | 属于开发流程，非平台功能 |
| 小众能力（2.2~2.4/2.11） | 余弦/图片/T2SQL | 演示价值低 |

### 核心能力覆盖

| 五条红线 | Demo 状态 |
|---------|:--:|
| ① @tool 工具化 | ✅ Agent 中心可直接体验 |
| ② RAG 全链路 | ✅ 知识库页检索+结果 |
| ③ Agent 循环 | ✅ LangChain Tab 对话+SSE |
| ④ StateGraph 三要素 | ✅ Supervisor 流水线可视化 |
| ⑤ Memory 策略选型 | ⚠️ 后端有，前端无展示 |
