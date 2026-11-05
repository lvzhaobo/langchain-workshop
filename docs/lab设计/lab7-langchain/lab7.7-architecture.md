# Lab 7.7 架构图 — Evals 评测体系

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    subgraph PREP["📝 准备阶段"]
        direction LR
        DS["评测数据集<br/>10 条手工标注<br/>问题 + 期望答案 + 来源"]
    end

    PREP --> RUN

    subgraph RUN["🔄 评测循环"]
        direction TB
        FOR["逐条跑评测用例"]
        RAG["RAG 管道执行"]
        METRICS["计算三个指标"]
        FOR --> RAG --> METRICS
    end

    subgraph METRICS_DETAIL["📊 三个指标"]
        direction LR
        M1["意图准确率<br/>分类对不对"]
        M2["检索召回率<br/>找没找到来源文档"]
        M3["答案质量<br/>LLM 裁判打分"]
    end

    METRICS --> METRICS_DETAIL
    METRICS_DETAIL --> REPORT

    REPORT["📋 评测报告<br/>通过率 + 失败用例分析"]

    REPORT --> FIX{"有失败用例？"}
    FIX -->|有| IMPROVE["🔧 调整配置<br/>Prompt / k值 / 分块策略"]
    FIX -->|无| DONE(["✅ 通过"])
    IMPROVE --> RUN

    classDef prep fill:#f5f3ff,color:#5b21b6,stroke:#7c3aed,stroke-width:2px
    classDef run fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef metrics fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef report fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    classDef done fill:#f0f9ff,color:#0369a1,stroke:#0ea5e9,stroke-width:2px
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px

    class PREP prep
    class RUN run
    class METRICS_DETAIL metrics
    class REPORT report
    class DONE done
    class DS,FOR,RAG,METRICS,M1,M2,M3,FIX,IMPROVE node
```

## 步骤说明

| 步骤 | 做什么 |
|:---:|------|
| 1 | 基于 12 篇知识库文档，手工标注 10 条评测用例 |
| 2 | 实现意图准确率、检索召回率、答案质量三个指标 |
| 3 | 跑评测循环，每条用例记录分数 |
| 4 | 分析失败用例，定位根因（检索没召回？LLM 编造？） |
| 5 | 调整配置（Prompt、k 值、分块策略等），重新评测 |
| 6 | 对比调整前后的分数变化 |
