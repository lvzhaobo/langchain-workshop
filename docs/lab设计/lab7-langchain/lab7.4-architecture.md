# Lab 7.4 架构图 — Tool Calling 粗粒度 vs 细粒度

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    U(["👤 用户<br/><i>天河区有哪些设备状态异常？</i>"])

    U --> SPLIT

    SPLIT{"两套工具对比"}

    SPLIT -->|粗粒度| COARSE
    SPLIT -->|细粒度| FINE

    subgraph COARSE["🔨 粗粒度工具"]
        direction TB
        C1["search_all_equipment<br/>一个 query 字符串<br/>搜设备+知识库+巡检"]
        C2["调用 1 次"]
        C3["返回一堆混杂结果"]
        C4["Agent 自己筛选"]
        C1 --> C2 --> C3 --> C4
    end

    subgraph FINE["🔧 细粒度工具"]
        direction TB
        F1["search_by_region<br/>只按区域查"]
        F2["search_by_status<br/>只按状态查"]
        F3["diagnose_device<br/>用 Pydantic 参数"]
        F4["调用 3 次<br/>每次拿精确结果"]
        F5["回答有条理"]
        F1 --> F4
        F2 --> F4
        F3 --> F4
        F4 --> F5
    end

    classDef user fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef coarse fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    classDef fine fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px
    classDef split fill:#f5f3ff,color:#5b21b6,stroke:#7c3aed,stroke-width:2px

    class U user
    class SPLIT split
    class COARSE coarse
    class FINE fine
    class C1,C2,C3,C4,F1,F2,F3,F4,F5 node
```

## 步骤说明

| 步骤 | 做什么 |
|:---:|------|
| 1 | 实现粗粒度工具组：`search_all_equipment` + `inspect_device` |
| 2 | 实现细粒度工具组：`search_by_type/status/region` + `diagnose_device`（Pydantic 参数） |
| 3 | 同一个任务分别用两套工具跑 |
| 4 | 对比：调用次数、参数准确性、回答完整性 |

## 粗粒度 vs 细粒度 对比

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph LR
    subgraph PYDANTIC["✅ Pydantic 结构化参数"]
        direction LR
        P1["Agent"] -->|"{type:'变压器',status:'异常'}"| P2["Tool"]
    end
    subgraph STRING["❌ 字符串参数"]
        direction LR
        S1["Agent"] -->|"'天河区 异常 变压器'"| S2["Tool 内部还要解析"]
    end
    classDef ok fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef nok fill:#fff1f2,color:#9f1239,stroke:#e11d48,stroke-width:2px
    class PYDANTIC ok
    class STRING nok
```
