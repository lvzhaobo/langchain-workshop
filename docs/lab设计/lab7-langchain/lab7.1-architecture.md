# Lab 7.1 架构图 — ReAct Agent 循环

```mermaid
%%{init: {'flowchart': {'curve': 'basis', 'nodeSpacing': 25, 'rankSpacing': 40}}}%%
graph LR
    U(["👤 用户<br/>#1变压器巡检人？"])

    U --> THINK["💭 Think"] --> ACT["🔧 Act"] --> OBSERVE["📥 Observe"]
    OBSERVE --> DECIDE{"够了？"}
    DECIDE -->|不够| THINK
    DECIDE -->|够了| ANSWER(["💬 张工 · 2026-07-10"])

    ACT -.->|调用| T1["search_equipment"]
    ACT -.->|调用| T2["get_detail"]
    OBSERVE -.-|读取| D1["📦 equipment_data.json"]

    classDef user fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef think fill:#f5f3ff,color:#5b21b6,stroke:#7c3aed,stroke-width:1px
    classDef observe fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:1px
    classDef output fill:#f0f9ff,color:#0369a1,stroke:#0ea5e9,stroke-width:2px
    classDef side fill:#fafafa,color:#94a3b8,stroke:#d6d3d1,stroke-width:1px,stroke-dasharray: 3 3

    class U user
    class THINK,ACT,DECIDE think
    class OBSERVE observe
    class ANSWER output
    class T1,T2,D1 side
```

## 步骤说明

| 步骤 | 节点 | 做什么 |
|:---:|------|------|
| 1 | Think | AI 分析问题，判断需要调哪个工具 |
| 2 | Act | 调用工具，传入搜索关键词 |
| 3 | Observe | 工具返回数据，AI 解读 |
| 4 | 判断 | 够了→回答；不够→回到 Think |
| 5 | 输出 | 自然语言组织答案 |

## 单次 LLM vs Agent

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph LR
    N1["❌ 单次LLM"] --> N2["编造"]
    W1["✅ Agent"] --> W2["调工具"] --> W3["真实数据"]
    classDef nok fill:#fff1f2,color:#9f1239,stroke:#e11d48,stroke-width:2px
    classDef ok fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    class N1,N2 nok
    class W1,W2,W3 ok
```

> **排版要点** 工具层和数据层不再各自包 subgraph，而是用虚线从主流程侧边连出——主流程保持横向一条线，工具和数据作为"侧边资源"不抢占纵向空间。
