# Lab 7.2 架构图 — RAG 检索增强生成

```mermaid
%%{init: {'theme':'base', 'flowchart':{'curve':'basis','htmlLabels':true,'nodeSpacing':40,'rankSpacing':60}}}%%
graph LR
    U(["👤 用户<br/>SF6气体泄漏怎么处理？"])

    U --> EMB["📐 Embedding<br/>问题 → 向量"]

    EMB --> VS["📦 ChromaDB<br/>向量相似度搜索<br/><br/>12篇电力文档<br/>分块→Embedding→存储"]

    VS --> TOP["📋 Top-3 相关文档"]

    TOP --> AUG["📝 增强 Prompt<br/>文档作为上下文"]

    AUG --> LLM["🤖 LLM 生成<br/>qwen-plus"]

    LLM --> ANS(["✅ 回答<br/>SF6年泄漏率≤0.5%<br/>用检漏仪沿密封面检测"])

    style U fill:#f1f5f9,stroke:#64748b,stroke-width:2px
    style EMB fill:#eff6ff,stroke:#3b82f6,stroke-width:2px
    style VS fill:#eff6ff,stroke:#3b82f6,stroke-width:2px
    style TOP fill:#eff6ff,stroke:#3b82f6,stroke-width:2px
    style AUG fill:#ecfdf5,stroke:#10b981,stroke-width:2px
    style LLM fill:#ecfdf5,stroke:#10b981,stroke-width:2px
    style ANS fill:#f0f9ff,stroke:#0ea5e9,stroke-width:2px
```

## 步骤说明

| 步骤 | 阶段 | 做什么 |
|:---:|------|------|
| 1 | 索引构建 | 12 篇文档分块 → Embedding 转向量 → 存入 ChromaDB |
| 2 | 用户提问 | "SF6 气体泄漏怎么处理？" |
| 3 | 检索 | 问题转向量 → ChromaDB 相似度搜索 → Top-3 文档 |
| 4 | 增强 Prompt | 把 3 篇文档拼到 Prompt 里作为上下文 |
| 5 | LLM 生成 | LLM 基于上下文回答（不编造） |

## 有 RAG vs 无 RAG

```mermaid
%%{init: {'theme':'base', 'flowchart':{'curve':'basis','htmlLabels':true,'nodeSpacing':60,'rankSpacing':80}}}%%
graph LR
    subgraph NO["❌ 无 RAG"]
        direction LR
        N1["问题"] --> N2["LLM"] --> N3["编造或不知道"]
    end

    subgraph YES["✅ 有 RAG"]
        direction LR
        Y1["问题"] --> Y2["检索文档"] --> Y3["LLM 生成"] --> Y4["基于文档回答"]
    end

    NO -.->|"对比"| YES

    style NO fill:#fff1f2,stroke:#e11d48,stroke-width:2px
    style YES fill:#ecfdf5,stroke:#10b981,stroke-width:2px
    style N1 fill:#fff,stroke:#fda4af
    style N2 fill:#fff,stroke:#fda4af
    style N3 fill:#fff,stroke:#fda4af
    style Y1 fill:#fff,stroke:#6ee7b7
    style Y2 fill:#fff,stroke:#6ee7b7
    style Y3 fill:#fff,stroke:#6ee7b7
    style Y4 fill:#fff,stroke:#6ee7b7
```
