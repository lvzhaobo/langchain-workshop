# Lab 7.9 架构图 — Web UI Flask 封装

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    subgraph BROWSER["🖥 浏览器"]
        direction TB
        HTML["index.html<br/>聊天界面"]
        INPUT["输入框<br/><i>EP-D-002 断路器拒分</i>"]
        MSG["逐节点展示<br/>Router → Diagnosis → ..."]
        HTML --> INPUT --> MSG
    end

    INPUT -->|"POST /chat/stream"| FLASK

    subgraph BACKEND["⚙️ Flask 后端"]
        direction TB
        FLASK["app.py"]
        ROUTE["/chat/stream<br/>SSE 端点"]
        GRAPH["LangGraph 工作流<br/>graph.stream()"]
        FLASK --> ROUTE --> GRAPH
    end

    GRAPH -->|"data: {node: 'router'}"| MSG
    GRAPH -->|"data: {node: 'diagnosis'}"| MSG
    GRAPH -->|"data: {node: 'solution'}"| MSG
    GRAPH -->|"data: {node: 'done'}"| MSG

    classDef browser fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef backend fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef sse fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px,stroke-dasharray: 5 5
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px

    class BROWSER browser
    class BACKEND backend
    class HTML,INPUT,MSG,FLASK,ROUTE,GRAPH node
```

## 步骤说明

| 步骤 | 做什么 |
|:---:|------|
| 1 | 创建 Flask 应用，定义 `/chat/stream` SSE 端点 |
| 2 | 在 `generate()` 函数中调用 `graph.stream()`，每个节点完成 → `yield` 一条 SSE 消息 |
| 3 | 写 `index.html`：输入框 + 聊天区域 + EventSource 接收 SSE |
| 4 | 浏览器逐节点展示执行过程：Router → Diagnosis → Solution → Execute |
| 5 | （选做）根据 severity 用不同颜色展示诊断结果卡片 |

## SSE 数据流

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
sequenceDiagram
    participant B as 浏览器
    participant F as Flask
    participant G as LangGraph

    B->>F: POST /chat/stream {query}
    F->>G: graph.stream()
    G-->>F: Router 完成
    F-->>B: data: {"node":"router"}
    G-->>F: Diagnosis 完成
    F-->>B: data: {"node":"diagnosis"}
    G-->>F: Solution 完成
    F-->>B: data: {"node":"solution"}
    G-->>F: Execute 完成
    F-->>B: data: {"node":"done"}
```
