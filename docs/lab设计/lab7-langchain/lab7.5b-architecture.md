# Lab 7.5b 架构图 — Supervisor 多 Agent 协作模式

```mermaid
graph TB
    %% ── 入口 ──
    U(["👤 用户<br/><i>EP-D-002 断路器拒分</i>"])
    U --> S

    %% ── Supervisor 调度中心 ──
    S["🧠 Supervisor<br/>调度中心 LLM"]
    S -->|"1️⃣ 无诊断结论<br/>→ 调诊断专家"| DA
    S -->|"2️⃣ 有诊断无方案<br/>→ 调方案专家"| SA
    S -->|"3️⃣ 有方案未执行<br/>→ 调执行专家"| EA
    S -->|"✅ 全部完成<br/>→ 汇总输出"| SUM

    %% ── Diagnosis Agent ──
    subgraph DA_BOX["🔍 Diagnosis Agent · 诊断专家"]
        DA_SYS["System: 你是电力设备<br/>故障诊断专家"]
        DA_T1["🛠 search_equipment_by_id<br/><i>查设备详细信息</i>"]
        DA_T2["🛠 search_knowledge_base<br/><i>查故障处理规程</i>"]
        DA_OUT["📤 产出<br/>· diagnosis_result<br/>· severity<br/>· related_procedures"]
        DA_SYS --> DA_T1
        DA_SYS --> DA_T2
        DA_T1 --> DA_OUT
        DA_T2 --> DA_OUT
    end
    DA --> DA_SYS

    %% ── Solution Agent ──
    subgraph SA_BOX["📋 Solution Agent · 方案专家"]
        SA_SYS["System: 你是设备维修<br/>方案制定专家"]
        SA_READ["📥 读取<br/>· diagnosis_result<br/>· severity"]
        SA_T1["🛠 generate_repair_plan<br/><i>生成处置方案</i>"]
        SA_T2["🛠 send_alert<br/><i>发送告警通知</i>"]
        SA_OUT["📤 产出<br/>· solution_plan<br/>· alert_sent"]
        SA_SYS --> SA_READ
        SA_READ --> SA_T1
        SA_READ --> SA_T2
        SA_T1 --> SA_OUT
        SA_T2 --> SA_OUT
    end
    SA --> SA_SYS

    %% ── Execute Agent ──
    subgraph EA_BOX["✅ Execute Agent · 执行专家"]
        EA_SYS["System: 你是巡检记录<br/>与通知执行专员"]
        EA_READ["📥 读取<br/>· diagnosis_result<br/>· solution_plan"]
        EA_T1["🛠 create_inspection_record<br/><i>生成巡检记录</i>"]
        EA_T2["🛠 push_notification<br/><i>推送通知</i>"]
        EA_OUT["📤 产出<br/>· execution_record<br/>· notification_sent"]
        EA_SYS --> EA_READ
        EA_READ --> EA_T1
        EA_READ --> EA_T2
        EA_T1 --> EA_OUT
        EA_T2 --> EA_OUT
    end
    EA --> EA_SYS

    %% ── 汇总 ──
    SUM["📊 汇总节点<br/>聚合所有 Agent 产出<br/>→ 最终答案"]
    SUM --> OUT(["✅ 输出<br/>诊断报告 + 处置方案<br/>+ 执行记录"])

    %% ── 每个 Agent 回到 Supervisor ──
    DA_OUT -.->|"↩ 回到 Supervisor"| S
    SA_OUT -.->|"↩ 回到 Supervisor"| S
    EA_OUT -.->|"↩ 回到 Supervisor"| S

    %% ── 共享状态 ──
    subgraph STATE["📦 共享状态 MultiAgentState"]
        direction LR
        F1["diagnosis_result"]
        F2["severity"]
        F3["solution_plan"]
        F4["execution_record"]
        F5["task_history"]
    end
    DA_OUT -.->|写入| STATE
    SA_OUT -.->|写入| STATE
    SA_READ -.-|读取| STATE
    EA_READ -.-|读取| STATE
    EA_OUT -.->|写入| STATE

    %% ── 样式 ──
    classDef user fill:#455a64,color:#fff,stroke:#263238,stroke-width:2px
    classDef supervisor fill:#7b1fa2,color:#fff,stroke:#4a148c,stroke-width:2px
    classDef agent fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:1px
    classDef tool fill:#f5f5f5,color:#333,stroke:#bdbdbd,stroke-width:1px
    classDef output fill:#e8f5e9,color:#2e7d32,stroke:#a5d6a7,stroke-width:1px
    classDef state fill:#fff3e0,color:#e65100,stroke:#ffcc80,stroke-width:2px
    classDef summary fill:#00695c,color:#fff,stroke:#004d40,stroke-width:2px
    classDef read fill:#e3f2fd,color:#1565c0,stroke:#90caf9,stroke-width:1px

    class U,OUT user
    class S supervisor
    class DA,SA,EA agent
    class DA_SYS,SA_SYS,EA_SYS agent
    class DA_T1,DA_T2,SA_T1,SA_T2,EA_T1,EA_T2 tool
    class DA_OUT,SA_OUT,EA_OUT output
    class SA_READ,EA_READ read
    class SUM summary
    class STATE,F1,F2,F3,F4,F5 state
```

## 图例说明

| 颜色 | 含义 |
|------|------|
| 🟣 紫色 | Supervisor 调度中心 |
| 🔵 蓝色 | 各专业 Agent |
| ⬜ 灰色 | Agent 专属工具 |
| 🟢 绿色 | Agent 产出写入 State |
| 🟠 橙色 | 共享状态 / 其他 Agent 读取 |
| 🟦 青色 | 汇总输出节点 |

## 三种模式对比

```mermaid
graph LR
    subgraph S1["lab7.1 ReAct Agent"]
        direction TB
        A1["LLM"] -->|思考| A2["调工具?"]
        A2 -->|是| A3["Tool A/B/C"]
        A3 -->|观察| A1
        A2 -->|否| A4["回答"]
    end

    subgraph S2["lab7.5 StateGraph"]
        direction LR
        B1["Router"] --> B2["Diag"] --> B3["Sol"] --> B4["Exec"]
    end

    subgraph S3["lab7.5b Supervisor"]
        direction TB
        C1["Supervisor"] --> C2["Agent A"]
        C2 --> C1
        C1 --> C3["Agent B"]
        C3 --> C1
        C1 --> C4["Agent C"]
        C4 --> C1
    end

    classDef mode1 fill:#e3f2fd,stroke:#1565c0
    classDef mode2 fill:#e8f5e9,stroke:#2e7d32
    classDef mode3 fill:#f3e5f5,stroke:#7b1fa2

    class S1 mode1
    class S2 mode2
    class S3 mode3
```

| 模式 | 决策者 | 路径 | 适用场景 |
|------|:---:|------|------|
| **ReAct Agent** | AI 自主 | 动态 | 开放式探索任务 |
| **StateGraph** | 你（编译时） | 固定 | 有确定流程的任务 |
| **Supervisor** | Supervisor LLM | 半动态 | 需要灵活调度多专家的复杂任务 |
