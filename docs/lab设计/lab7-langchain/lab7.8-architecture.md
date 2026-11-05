# Lab 7.8 架构图 — LangServe 部署 + LangSmith 追踪

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    subgraph DEV["💻 开发环境"]
        G["LangGraph 工作流<br/>lab7.5 的 StateGraph"]
    end

    DEV --> DEPLOY

    subgraph DEPLOY["🚀 LangServe 部署"]
        direction TB
        ADD["add_routes(app, graph)<br/>一行代码"]
        ENDPOINTS["自动生成端点"]
        SWAGGER["/docs · Swagger"]
        PLAY["/playground · 在线调试"]
        ADD --> ENDPOINTS
        ENDPOINTS --> SWAGGER
        ENDPOINTS --> PLAY
    end

    CLIENT["🌐 客户端"]
    CLIENT -->|"/invoke 同步"| ENDPOINTS
    CLIENT -->|"/stream SSE"| ENDPOINTS
    CLIENT -->|"/batch 批量"| ENDPOINTS

    subgraph TRACE["🔍 LangSmith 追踪"]
        direction TB
        ENV["LANGCHAIN_TRACING_V2=true"]
        TRACE_DATA["全链路 Trace"]
        DETAIL["每步耗时 · Token 消耗<br/>输入输出 · 错误信息"]
        ENV --> TRACE_DATA --> DETAIL
    end

    ENDPOINTS -.->|自动上报| TRACE_DATA

    classDef dev fill:#f5f3ff,color:#5b21b6,stroke:#7c3aed,stroke-width:2px
    classDef deploy fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef client fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef trace fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px

    class DEV dev
    class DEPLOY deploy
    class CLIENT client
    class TRACE trace
    class G,ADD,ENDPOINTS,SWAGGER,PLAY,ENV,TRACE_DATA,DETAIL node
```

## 步骤说明

| 步骤 | 做什么 |
|:---:|------|
| 1 | 基于 lab7.5 的 `build_graph()` 创建 graph |
| 2 | `add_routes(app, graph, path="/api/diagnosis")` 一行部署 |
| 3 | 访问 `/docs` 查看自动 Swagger，`/playground` 在线调试 |
| 4 | 配置 `LANGCHAIN_TRACING_V2=true` 开启追踪 |
| 5 | 在 LangSmith 控制台查看每条请求的完整调用链 |

## LangServe vs 手写 Flask

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph LR
    subgraph LANGSERVE["LangServe"]
        L1["add_routes(app, graph)"] --> L2["自动生成 /invoke<br/> /stream /batch<br/> /playground /docs"]
    end
    subgraph FLASK["手写 Flask"]
        F1["手写 @app.route"] --> F2["手写请求解析"] --> F3["手写响应格式"] --> F4["手写 Swagger"]
    end
    classDef auto fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef manual fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    class LANGSERVE auto
    class FLASK manual
```
