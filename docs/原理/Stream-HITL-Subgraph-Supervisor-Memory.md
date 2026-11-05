# Stream · HITL · Subgraph · Supervisor · Memory 体系

> 覆盖 sample-8 至 sample-13

---

## 一、Stream 流式输出（sample-9）

### 1.1 三种模式

| 模式 | 输出内容 | 适合 |
|------|---------|------|
| `values` | 每步完整 State | 调试 |
| `updates` | 每步只输出更新 | 看 diff |
| `messages` | 逐 token 打字机 | 用户端实时显示 |

### 1.2 用法

```python
graph.stream(input, stream_mode="values")
graph.stream(input, stream_mode="updates")
graph.stream(input, stream_mode="messages")
```

---

## 二、HITL 人工审批（sample-8）

### 2.1 核心 API

```python
from langgraph.types import interrupt, Command

def review_node(state):
    decision = interrupt("是否批准？")  # 暂停在这里
    if decision:
        return {"approved": True}

# 人做决定后
graph.invoke(Command(resume=True), config)   # 批准
graph.invoke(Command(resume=False), config)  # 拒绝
```

### 2.2 暂停方式

| 方式 | 位置 | 用法 |
|------|------|------|
| `interrupt()` | 节点内 | 灵活，可带提示信息 |
| `interrupt_before=["node"]` | compile 参数 | 在指定节点前停 |
| `interrupt_after=["node"]` | compile 参数 | 在指定节点后停 |

### 2.3 依赖 Checkpoint

interrupt 暂停时 State 自动存档，resume 从存档点恢复继续执行。

---

## 三、Command 动态路由（sample-10）

### 3.1 用法

```python
from langgraph.types import Command

def diagnose(state):
    if state["rx_power"] < -30:
        return Command(goto="escalate", update={"severity": "critical"})
    return Command(goto="auto_fix")
```

### 3.2 和条件边的区别

- add_conditional_edges：路由逻辑在节点外
- Command：路由逻辑在节点内，更内聚

---

## 四、子图 Subgraph（sample-11）

### 4.1 用法

```python
child_builder = StateGraph(State)
# ... 子图自己的节点和边
child_graph = child_builder.compile()

parent_builder = StateGraph(State)
parent_builder.add_node("child", child_graph)  # 子图作为节点
```

---

## 五、Supervisor 模式（sample-12）

### 5.1 架构

```
Supervisor（中央调度）
  ├→ Worker A（检测）
  ├→ Worker B（诊断）
  └→ Worker C（处置）
       │
   Worker 干完 → 回到 Supervisor 再决策
```

### 5.2 图结构

```python
builder.add_edge(START, "supervisor")
builder.add_conditional_edges("supervisor", route_fn, {
    "worker_a": "worker_a",
    "worker_b": "worker_b",
    "worker_c": "worker_c",
    FINISH: END,
})
# Worker 干完 → 回到 Supervisor
builder.add_edge("worker_a", "supervisor")
builder.add_edge("worker_b", "supervisor")
builder.add_edge("worker_c", "supervisor")
```

---

## 六、记忆体系（sample-13）

### 6.1 三层架构

| 层级 | 概念 | 实现 |
|------|------|------|
| 短期记忆 | 当前对话消息 | MessagesState + add_messages |
| 工作记忆 | 当前任务进度 | State 字段 + Checkpoint |
| 长期记忆 | 跨会话知识 | MEMORY.md 文件存储 + 检索注入 |

### 6.2 OpenClaw 四层对比

| OpenClaw | LangGraph 对应 |
|----------|---------------|
| Layer 1: Session Context | messages in State |
| Layer 2: Daily Log | ❌ 不直接对应 |
| Layer 3: Long-term Memory | MEMORY.md + 检索 |
| Layer 4: Vector Search | FAISS / 向量库 |

### 6.3 记忆写入机制

LLM 自主判断 + write_memory 工具 + MEMORY.md 文件持久化

---

## 七、RAG 裸链（sample-14）

### 7.1 完整链条

```
文档 → TextLoader → RecursiveCharacterTextSplitter → OpenAIEmbeddings → FAISS → retriever → LLM 生成
```

### 7.2 关键代码

```python
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

---

## 八、Prompt 模板 + 缓存 + LangSmith（sample-15）

### 8.1 Prompt 模板

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{role}，专攻{domain}"),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])
```

### 8.2 LLM 缓存

```python
from langchain_core.caches import InMemoryCache
from langchain_core.globals import set_llm_cache
set_llm_cache(InMemoryCache())  # 相同输入秒回
```

### 8.3 LangSmith Trace

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls__your_key
export LANGCHAIN_PROJECT=agent-training
```
