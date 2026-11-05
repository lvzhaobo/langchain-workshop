# LangChain 全家桶 CheatSheet（详细版）

> 来源：官方文档、社区整理、知乎/CSDN/掘金 · 2025-2026

---

## 一、生态全景：三层架构

```
┌─────────────────────────────────────────────┐
│ LangChain Core    "零件层"                    │
│ ChatModel · Prompt · Tool · Message · Output │
├─────────────────────────────────────────────┤
│ LangGraph         "编排层"                    │
│ StateGraph · Node · Edge · Checkpoint · HITL │
├─────────────────────────────────────────────┤
│ LangSmith         "观测层"                    │
│ Tracing · Evaluation · Monitoring · Studio   │
├─────────────────────────────────────────────┤
│ LangServe         "部署层"                    │
│ REST API · Playground · 一行部署              │
├─────────────────────────────────────────────┤
│ LangFlow          可视化拖拽（社区项目）        │
└─────────────────────────────────────────────┘
```

---

## 二、LangChain Core — 完整 API

### 2.1 ChatModel

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4.1", temperature=0, streaming=True, max_tokens=2000)

# 调用
response = llm.invoke("Hello")              # 单条
responses = llm.batch(["q1", "q2", "q3"])  # 批量
for chunk in llm.stream("Hello"): ...       # 流式

# 容错降级
model = ChatOpenAI(model="gpt-4.1").with_fallbacks([ChatOpenAI(model="gpt-4o-mini")])
```

### 2.2 Prompt Template

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{role}，专攻{domain}。"),
    MessagesPlaceholder("history"),    # 对话历史占位
    ("human", "{question}"),
])

# Few-shot
prompt = ChatPromptTemplate.from_messages([
    ("system", "只返回 JSON。"),
    ("user", "示例:\n{examples}\n\n问题: {question}")
])
```

### 2.3 LCEL — 管道语法 `|`

```python
# 基础管道
chain = prompt | llm | StrOutputParser()

# 并行
chain = RunnableParallel(
    summary=summary_prompt | llm | StrOutputParser(),
    keywords=keywords_prompt | llm | StrOutputParser(),
)

# 透传 + 动态赋值
chain = (RunnablePassthrough.assign(extra=lambda x: "value") | prompt | llm | parser)

# 分支路由
chain = RunnableBranch(
    (lambda x: "math" in x["topic"], math_chain),
    (lambda x: "code" in x["topic"], code_chain),
    general_chain  # 默认
)
```

**`|` 规则：左边输出类型必须匹配右边输入类型。**

### 2.4 @tool 工具

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# 简单工具
@tool
def query_device(device_id: str) -> str:
    """查询 5G 基站设备详情"""
    return f"{device_id}: 华为 AAU5613, 在线"

# 结构化参数
class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=5)

@tool(args_schema=SearchInput)
def search_kb(query: str, max_results: int = 5) -> str:
    """搜索知识库"""
    return f"找到 {max_results} 条结果"

# 绑定工具
llm_with_tools = llm.bind_tools([query_device, search_kb])
```

### 2.5 Structured Output

```python
from pydantic import BaseModel, Field

class Diagnosis(BaseModel):
    device_id: str
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_action: str

structured_llm = llm.with_structured_output(Diagnosis)
result: Diagnosis = structured_llm.invoke("DEV-0001 光模块告警")
```

### 2.6 Messages

```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

# HumanMessage   — 用户输入
# AIMessage      — LLM 输出（可能含 tool_calls）
# SystemMessage  — 系统提示词
# ToolMessage    — 工具返回结果
```

### 2.7 Memory（LangChain 经典版）

```python
from langchain.memory import ConversationBufferMemory, ConversationBufferWindowMemory

# Buffer: 全记
memory = ConversationBufferMemory(return_messages=True)

# Window: 只记最近 K 轮
memory = ConversationBufferWindowMemory(k=4, return_messages=True)

# Summary: LLM 自动压缩
memory = ConversationSummaryMemory(llm=llm, return_messages=True)

# SummaryBuffer: Token 预算内保留原始+超出自动摘要
memory = ConversationSummaryBufferMemory(llm=llm, max_token_limit=2000)
```

### 2.8 废弃 → 现代替代

| 旧 API | 现代替代 |
|--------|---------|
| `LLMChain` | `prompt \| llm \| parser` |
| `SequentialChain` | `step1 \| step2 \| step3` |
| `initialize_agent()` | `create_react_agent()` from langgraph |
| `chain.run()` | `chain.invoke()` |
| `AgentExecutor` | LangGraph StateGraph |

---

## 三、LangChain RAG — 完整技术栈

### 3.1 标准 RAG Pipeline

```python
# 1. 加载
from langchain_community.document_loaders import TextLoader
docs = TextLoader("knowledge.txt").load()

# 2. 切割
from langchain_text_splitters import RecursiveCharacterTextSplitter
chunks = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100).split_documents(docs)

# 3. 向量化
from langchain_openai import OpenAIEmbeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 4. 存入 FAISS
from langchain_community.vectorstores import FAISS
vectorstore = FAISS.from_documents(chunks, embeddings)

# 5. 检索器
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 6. RAG Chain
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

def format_docs(docs): return "\n\n".join(d.page_content for d in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt | llm | StrOutputParser()
)
```

### 3.2 RAG 优化四象限

| 方向 | 技术 |
|------|------|
| 查询优化 | Query Rewrite · HyDE · Multi-Query |
| 检索优化 | MMR 去重 · Cross-Encoder 重排序 · 混合检索（向量+BM25） |
| 生成优化 | 引用来源 · 拒答机制 · 上下文压缩 |
| 评估 | RAGAS（忠实度+相关性+精确度+召回率） |

---

## 四、LangGraph — 完整 API 参考

### 4.1 StateGraph 三要素

```python
from typing import Annotated, TypedDict
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]          # 消息追加
    results: Annotated[list, operator.add]           # 列表追加
    counter: Annotated[int, operator.add]            # 累加
    max_score: Annotated[int, max]                   # 取最大值
    flags: Annotated[bool, operator.or_]             # 逻辑或

builder = StateGraph(State)
graph = builder.compile()
```

### 4.2 State Reducer 全集

| Reducer | 行为 | State 写法 |
|---------|------|-----------|
| 默认（无） | 后者覆盖前者 | `name: str` |
| `operator.add` | 累加 / 列表拼接 | `Annotated[int, operator.add]` |
| `operator.or_` | 任一 True 则 True | `Annotated[bool, operator.or_]` |
| `add_messages` | 消息追加 + 去重 | `Annotated[list, add_messages]` |
| 自定义 | 任意合并逻辑 | `Annotated[T, custom_func]` |

### 4.3 Nodes — 三种签名

```python
# 签 1: 只读 state
def node(state: State): return {"key": val}

# 签 2: state + config（拿 thread_id）
def node(state: State, config: RunnableConfig):
    tid = config["configurable"]["thread_id"]
    return {"key": val}

# 签 3: state + runtime（读写 store）
def node(state: State, runtime: Runtime):
    runtime.store.put(["namespace"], "key", {"data": "val"})
    return {"key": val}
```

### 4.4 Edges 全集

```python
# 固定边
builder.add_edge(START, "node_a")
builder.add_edge("node_a", END)

# 条件边
def router(state) -> Literal["path_a", "path_b"]:
    return "path_a" if state["flag"] else "path_b"

builder.add_conditional_edges("node", router, ["path_a", "path_b"])

# Command — 节点内决定下一步
from langgraph.types import Command
def node(state) -> Command[Literal["a", "b"]]:
    return Command(update={"key": val}, goto="a")

# Send — 并行 Fan-out
from langgraph.types import Send
def dispatcher(state):
    return [Send("worker", {"task": t}) for t in state["tasks"]]
```

### 4.5 Checkpoint

```python
from langgraph.checkpoint.memory import MemorySaver

graph = builder.compile(checkpointer=MemorySaver())

# 调用时带 thread_id
config = {"configurable": {"thread_id": "session-1"}}
graph.invoke(input, config)

# 读状态
state = graph.get_state(config)

# 历史快照
for snap in graph.getStateHistory(config):
    print(snap.values)

# 时间旅行
fork_config = graph.updateState(old_config, {"key": "new_value"})
graph.invoke(None, fork_config)
```

| Checkpointer | 存储 | 适用 |
|-------------|------|------|
| MemorySaver | 内存 dict | 测试/Demo |
| SqliteSaver | SQLite 文件 | 本地开发 |
| PostgresSaver | PostgreSQL | 生产 |

### 4.6 Stream — 7 种模式

`invoke()` 一口气跑完才出结果，`stream()` 逐步暴露执行过程。7 种模式对应 7 种视角——开发调试看 `updates`，用户端看 `messages`（打字机效果），排查问题看 `debug`。可以组合多个模式，同时看到节点更新和 LLM 输出。

```python
# stream_mode 可选值
graph.stream(input, stream_mode="values")       # 每步完整 State
graph.stream(input, stream_mode="updates")      # 每步节点更新 diff
graph.stream(input, stream_mode="messages")     # 逐 token 打字机（需 streaming=True）
graph.stream(input, stream_mode="custom")       # get_stream_writer() 自定义事件
graph.stream(input, stream_mode="checkpoints")  # checkpoint 元数据
graph.stream(input, stream_mode="tasks")        # 任务调度信息
graph.stream(input, stream_mode="debug")        # 所有信息汇总

# 组合多个模式
graph.stream(input, stream_mode=["updates", "messages"])
```

### 4.7 HITL — interrupt + Command(resume)

Agent 不能自己决定重启核心设备。在高风险操作前插一个人工审批点：`interrupt()` 让图暂停，当前 State 自动存档到 Checkpoint；人做决定后，`Command(resume=...)` 从暂停点接着跑。整个过程对开发透明——节点函数从 `interrupt` 那一行继续执行。

```python
from langgraph.types import interrupt, Command

def approval_node(state):
    decision = interrupt(f"是否批准: {state['action']}?")
    return {"approved": decision}  # 这行在 resume 之后才执行

# 暂停后恢复
graph.invoke(input, config)                    # 跑到 interrupt → 暂停
graph.invoke(Command(resume=True), config)     # 人批准 → 继续
```

### 4.8 Subgraph — 图嵌套图

把编译好的图当成父图的一个节点。父图把子图当作黑盒——只关心输入输出，不关心里面怎么跑。子图可以有自己独立的 State（也可以和父图共享）。这是多 Agent 的基础：每个 Worker 可以是一个独立编译的子图，挂到 Supervisor 的编排图中。

```python
child_graph = child_builder.compile()
parent_builder.add_node("child_agent", child_graph)  # 子图作为节点
```

### 4.9 Long-Term Memory — Store API

Checkpoint 存的是"这次对话跑到哪了"，Store 存的是"跨对话学到的知识"。Store 按命名空间（namespace）组织记忆，支持语义检索——节点内通过 `runtime.store` 读写，新会话启动时检索相关记忆注入 System Prompt。可以配合 Embeddings 做向量检索。

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
graph = builder.compile(store=store)

# 节点内读写
def my_node(state, runtime: Runtime):
    # 写入记忆（命名空间隔离不同用户/项目）
    runtime.store.put(["user_123"], "mem_1", {"data": "..."})
    # 语义检索相关记忆
    results = runtime.store.search(["user_123"], query="relevant", limit=3)
```

---

## 五、Agent 模式全集

六种模式按复杂度递增，从一条直线到循环调度到人机协同。Supervisor 是 Day3 核心，HITL 是企业级刚需。

| 模式 | 核心思路 | 怎么跑 | 示例 |
|------|---------|--------|------|
| ReAct | LLM 思考→调工具→看结果→再思考 | LLM 和 Tool 之间反复跳，直到 LLM 觉得够了 | sample-6 |
| Supervisor | 一个中央调度者 + N 个专业 Worker | Supervisor 看 State → 决定派谁 → Worker 干完回来 → 再看 → 直到 FINISH | sample-12 |
| Map-Reduce | 把任务拆成 N 份并行处理，最后汇总 | Send API 扇出 N 条分支 → 各跑各的 → collector 收结果 | sample-3 |
| Plan-Execute | 先列步骤清单，再逐条执行，最后对照检查 | Plan→Step1→Step2→...→Check→Done | — |
| Reflection | 生成→自我批评→改进→再生成 | Write→Critique→Rewrite，直到满意 | — |
| HITL | 高风险操作前暂停，等人批了再继续 | interrupt() 中断 → 人操作 → Command(resume) 继续 | sample-8 |

---

## 六、快速参考速查表

| 概念 | Python 写法 |
|------|-----------|
| 图 | `StateGraph(State)` |
| 编译 | `.compile(checkpointer=MemorySaver())` |
| 运行 | `.invoke(input, config)` |
| 流式 | `.stream(input, stream_mode="messages")` |
| 固定边 | `.add_edge(START, "node")` |
| 条件边 | `.add_conditional_edges("node", router, ["a","b"])` |
| 路由+更新 | `Command(update={}, goto="x")` |
| 并行派发 | `Send("worker", {"arg": val})` |
| 暂停 | `interrupt("提示信息")` |
| 恢复 | `Command(resume=value)` |
| 读状态 | `.get_state(config)` |
| 消息追加 | `Annotated[list, add_messages]` |
| 工具 | `@tool` + `.bind_tools()` |
| RAG | `retriever \| prompt \| llm \| parser` |

---

## 七、框架对比

| | LangGraph | CrewAI | AutoGen | AgentScope |
|---|:--:|:--:|:--:|:--:|
| 核心抽象 | 状态机(Graph) | 角色(Role) | 对话 | Actor 模型 |
| 状态管理 | Checkpoint | 内存字典 | 平台托管 | 独立管理 |
| 流程控制 | 显式 Node/Edge | 预定义 Flow | 内置循环 | 消息路由 |
| HITL | Interrupt 原语 | 手动 | 内置 | 实时介入 |
| 持久化 | 一等公民 | 无 | 云端 | 插件 |
| 生产度 | ★★★★★ | ★★★ | ★★★★ | ★★★★ |

---

## 八、9 Phase 学习路线

```
Phase 1: LangChain 核心（Runnable / LCEL / ChatModel / Prompt）
Phase 2: RAG 全流程（Loader → Split → Embed → FAISS → Retrieve → Generate）
Phase 3: Agent + Tools（@tool / bind_tools / ReAct / 结构化输出）
Phase 4: LangGraph 基础（StateGraph / Node / Edge / 条件路由）
Phase 5: 复杂工作流（循环迭代 / 错误恢复 / Supervisor / MCP）
Phase 6: 进阶特性（Checkpoint / HITL / Streaming / Subgraph）
Phase 7: 可观测性（LangSmith / OpenTelemetry）
Phase 8: 评估体系（RAGAS / 自定义 Eval Pipeline）
Phase 9: 生产部署（langgraph.json / Docker / LangGraph Cloud）
```

---

## 参考文献

| 来源 | 链接 |
|------|------|
| 知乎：LangChain全家桶一文读懂 | https://zhuanlan.zhihu.com/p/1977684118427956316 |
| 阿里云：10个LangChain核心概念 | https://developer.aliyun.com/article/1741841 |
| 微信：一图看懂LangChain全家桶 | https://mp.weixin.qq.com/s?__biz=MzAwNjU0NjA3Ng==&mid=2247518128&idx=1&sn=8525c43593cb5c6e44307cbf307e6df5 |
| GitHub：Agent Platform学习路线 | https://github.com/kevinten-ai/ai-agent-langgraph |
| CSDN：Agent框架选型指南 | https://blog.csdn.net/Python_cocola/article/details/158933430 |
| 掘金：AgentScope vs LangGraph对比 | https://juejin.cn/post/7549553534321623086 |
| 语雀：LangChain+LangGraph笔记 | https://www.yuque.com/wwk-ai/ai/nozls2dw2iztma0b |
