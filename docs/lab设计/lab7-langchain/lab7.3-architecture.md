# Lab 7.3 架构图 — Memory 三种策略对比

```mermaid
%%{init: {'flowchart': {'curve': 'basis', 'nodeSpacing': 15, 'rankSpacing': 30}}}%%
graph LR
    U(["👤 7轮排障对话"])

    U --> BUF
    U --> WIN  
    U --> SUM

    BUF["Buffer<br/>全量历史"] --> B1["第1轮"] --> B2["第2轮"] --> B3["..."] --> B7["第7轮"]
    B7 --> BN["✅ 全记住<br/>Token持续增长"]

    WIN["Window<br/>K=3轮"] --> W1["第1轮"] --> W2["第2轮"] --> W3["..."] --> W7["第7轮"]
    W7 --> WN["❌ 忘早期信息<br/>Token固定上限"]

    SUM["Summary<br/>LLM摘要"] --> S1["第1轮"] --> S2["第2轮"] --> S3["..."] --> S7["第7轮"]
    S7 --> SN["⚠️ 细节可能丢<br/>Token中等"]

    classDef user fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef buf fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef win fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    classDef sum fill:#f5f3ff,color:#5b21b6,stroke:#7c3aed,stroke-width:2px
    classDef note fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px
    classDef node fill:#eff6ff,color:#1e40af,stroke:#90caf9,stroke-width:1px

    class U user
    class BUF buf
    class WIN win
    class SUM sum
    class BN,WN,SN note
    class B1,B2,B3,B7,W1,W2,W3,W7,S1,S2,S3,S7 node
```

## 步骤说明

| 步骤 | 做什么 |
|:---:|------|
| 1 | 准备同一段 7 轮排障对话 |
| 2 | 分别用三种 Memory 运行 |
| 3 | 最后一轮问验证问题 |
| 4 | 对比回答正确率和 Token 消耗 |

## 三种策略对比

| 策略 | 原理 | Token | 丢信息？ |
|------|------|:---:|:---:|
| **BufferMemory** | 全量历史 | 持续增长 | 不丢 |
| **WindowMemory** | 最近 K 轮 | 固定上限 | 早期丢失 |
| **SummaryMemory** | LLM 摘要 | 中等 | 细节可能丢 |

> **排版要点** 去除 subgraph 嵌套：三种策略不再各自包一层盒子，而是直接三列并排。`direction LR` 让每列内部从左到右。
