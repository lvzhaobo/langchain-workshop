# Lab 7.6 架构图 — Human in the Loop 人工审批

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    %% ── 入口 ──
    U(["👤 用户<br/>EP-D-002 断路器拒分"])
    U --> R

    %% ── 正常执行：左到右主线 ──
    R["🔍 Router<br/>意图识别"]
    R --> D
    D["🩺 Diagnosis<br/>查设备 + 查知识库 → 诊断结论"]
    D --> PAUSE

    %% ── 暂停点 ──
    PAUSE["⏸️ interrupt_before<br/>Solution 前暂停"]
    PAUSE --> REVIEW

    %% ── 审批决策 ──
    REVIEW{"👤 人工审批<br/>展示诊断结论 + 严重程度"}
    
    %% ── 审批通道（侧边） ──
    TERM["🖥 终端<br/>input a/r"]
    FEISHU["📨 飞书卡片<br/>Webhook"]
    REVIEW -.- TERM
    REVIEW -.- FEISHU

    %% ── 批准路径 ──
    REVIEW -->|"✅ 批准"| S
    S["📋 Solution<br/>生成处置方案"]
    S --> E["✅ Execute<br/>执行记录"]
    E --> DONE(["🎯 完成"])

    %% ── 驳回路径 ──
    REVIEW -->|"↩️ 驳回"| ROLLBACK
    ROLLBACK["🔄 回退<br/>清空诊断结论<br/>记录驳回原因"]
    ROLLBACK --> D

    %% ── Checkpointer（底部） ──
    CKP["💾 Checkpointer<br/>暂停时保存 State<br/>恢复时加载 State"]
    PAUSE -.->|保存| CKP
    ROLLBACK -.->|更新| CKP

    %% ── 样式 ──
    classDef user fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef node fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:1px
    classDef pause fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    classDef review fill:#f5f3ff,color:#5b21b6,stroke:#7c3aed,stroke-width:2px
    classDef approve fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:1px
    classDef reject fill:#fff1f2,color:#9f1239,stroke:#e11d48,stroke-width:1px
    classDef channel fill:#fafafa,color:#78716c,stroke:#d6d3d1,stroke-width:1px
    classDef ckp fill:#f0f9ff,color:#0369a1,stroke:#0ea5e9,stroke-width:1px,stroke-dasharray: 5 5
    classDef done fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px

    class U user
    class R,D node
    class PAUSE pause
    class REVIEW review
    class S,E approve
    class ROLLBACK reject
    class TERM,FEISHU channel
    class CKP ckp
    class DONE done
```

## 图例

| 颜色 | 含义 |
|------|------|
| 🔵 浅蓝 | 工作流节点（Router / Diagnosis） |
| 🟡 浅黄 | 暂停点（interrupt_before） |
| 🟣 浅紫 | 人工审批 |
| 🟢 浅绿 | 批准路径（Solution / Execute） |
| 🔴 浅红 | 驳回路径（回退重诊） |
| ⬜ 浅灰 | 审批通道（终端 / 飞书） |
| 🔷 浅天蓝 | Checkpointer |

## 批准 vs 驳回

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph LR
    subgraph APPROVE["✅ 批准"]
        direction LR
        A1["暂停"] --> A2["人审"] --> A3["批准"] --> A4["Solution"] --> A5["Execute"] --> A6["完成"]
    end

    subgraph REJECT["↩️ 驳回"]
        direction LR
        R1["暂停"] --> R2["人审"] --> R3["驳回"] --> R4["清空诊断"] --> R5["重新诊断"] --> R6["再次暂停"]
    end

    classDef approve fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef reject fill:#fff1f2,color:#9f1239,stroke:#e11d48,stroke-width:2px

    class APPROVE approve
    class REJECT reject
```

| 路径 | 操作 | State 变化 | 下一步 |
|------|------|-----------|--------|
| **批准** | `Command(resume=True)` | 不变 | Solution 继续 |
| **驳回** | `update_state` 清空诊断字段 → `Command(resume=True)` | `diagnosis_result`、`severity` → None | 重新 Diagnosis |

## 无 HITL vs 有 HITL

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph LR
    subgraph WITHOUT["lab7.5 无 HITL"]
        direction LR
        W1["Router"] --> W2["Diagnosis"] --> W3["Solution"] --> W4["Execute"]
    end

    subgraph WITH["lab7.6 有 HITL"]
        direction LR
        H1["Router"] --> H2["Diagnosis"] --> H3["⏸️ 暂停"]
        H3 --> H4["👤 审批"]
        H4 -->|批| H5["Solution"]
        H4 -->|驳| H2
        H5 --> H6["Execute"]
    end

    classDef without fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef with fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px

    class WITHOUT without
    class WITH with
```

| 维度 | 无 HITL | 有 HITL |
|------|:---:|:---:|
| 执行方式 | 全自动 | 中间暂停等人审批 |
| 人能介入吗 | ❌ | ✅ 批准 / 驳回 / 修改 |
| 出错处理 | 跑完再改 | 驳回后立即重新诊断 |
| 适合场景 | 自动巡检、批量处理 | 关键设备诊断、停机决策 |
