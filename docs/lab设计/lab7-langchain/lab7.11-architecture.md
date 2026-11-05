# Lab 7.11 架构图 — Ops 监控 Dashboard

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    GW["⚡ AI Gateway<br/>每次 Agent 调用"]

    subgraph LOG["📝 日志层"]
        direction LR
        USAGE["logs/usage.jsonl<br/>· timestamp<br/>· agent_id · model<br/>· tokens · cost · latency"]
        ALERT_LOG["logs/alerts.jsonl<br/>· cost_spike<br/>· high_latency<br/>· error_rate"]
    end

    GW --> LOG

    subgraph API["📊 /api/metrics"]
        direction LR
        SUMMARY["当日摘要<br/>total_tokens · total_cost<br/>total_calls · avg_latency<br/>by_agent 拆分"]
    end

    LOG --> API

    subgraph DASH["📈 ops_dashboard.html · 16:9 宽屏"]
        direction LR
        CARDS["概览卡片<br/>Token · 费用 · 调用 · 延迟 · 错误"]
        CHARTS["Chart.js 图表<br/>柱状图: Agent用量<br/>折线图: 延迟分布"]
        TABLE["调用记录表格<br/>最近 20 条"]
    end

    API --> DASH

    subgraph ALERT["🚨 告警引擎"]
        direction LR
        A1["💸 单日费用 > ¥5"]
        A2["🐌 P95 延迟 > 3s"]
        A3["❌ 错误率 > 5%"]
    end

    API --> ALERT
    ALERT --> ALERT_LOG

    classDef gw fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef log fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef api fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    classDef dash fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef alert fill:#fff1f2,color:#9f1239,stroke:#e11d48,stroke-width:2px
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px

    class GW gw
    class LOG log
    class API api
    class DASH dash
    class ALERT alert
    class USAGE,ALERT_LOG,SUMMARY,CARDS,CHARTS,TABLE,A1,A2,A3 node
```

## 监控三层次

| 层次 | 能力 | 本实验 |
|:--:|------|:--:|
| Level 1 | 看得到（Metrics Dashboard） | ✅ Task 1-2 |
| Level 2 | 告得了（Alerting） | ✅ Task 3 |
| Level 3 | 自愈（Auto-Remediation） | 🔲 后续扩展 |
