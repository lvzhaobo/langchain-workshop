# 知识点：Agent Memory 体系

> 跨会话持久记忆 · 多 Agent 共享记忆 · 知识图谱

---

## 架构总览

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    subgraph SHORT["🔵 短期记忆 — 单次对话"]
        direction LR
        MSG["消息列表<br/>messages[]"]
        CTX["上下文窗口<br/>最近 N 轮对话"]
        MSG --> CTX
    end

    subgraph LONG["🟢 长期记忆 — 跨会话持久化"]
        direction LR
        FILE["📄 文件存储<br/>MEMORY.md"]
        VEC["🔢 向量数据库<br/>Chroma / FAISS"]
        KV["🗄 KV 存储<br/>Redis / JSON"]
    end

    subgraph SHARED["🟣 共享记忆 — 多 Agent 协作"]
        direction LR
        STATE["📊 共享 State<br/>LangGraph"]
        BUS["📨 消息总线<br/>Pub/Sub"]
        BRIDGE["📁 文件桥接<br/>OpenClaw"]
    end

    SHORT --> LONG
    LONG --> SHARED

    classDef short fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef long fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef shared fill:#f5f3ff,color:#5b21b6,stroke:#7c3aed,stroke-width:2px
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px

    class SHORT short
    class LONG long
    class SHARED shared
    class MSG,CTX,FILE,VEC,KV,STATE,BUS,BRIDGE node
```

---

## 一、跨会话持久记忆

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph LR
    USER["👤 用户<br/>会话 1"] --> AGENT["🤖 Agent"]

    subgraph MEM_PROCESS["💾 记忆管理"]
        direction TB
        JUDGE{"值得记？"}
        STORE["📄 写入<br/>MEMORY.md"]
        JUDGE -->|身份/决策/偏好| STORE
        JUDGE -->|闲聊/临时| SKIP["跳过"]
    end

    AGENT --> JUDGE

    subgraph RECALL["📋 会话 2 启动"]
        direction TB
        LOAD["📄 加载 MEMORY.md"]
        INJECT["注入 System Prompt"]
        LOAD --> INJECT
    end

    STORE -.->|下次对话| LOAD
    INJECT --> AGENT2["🤖 Agent<br/>🏷 已知用户身份和偏好"]

    classDef user fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef agent fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:1px
    classDef mem fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    classDef recall fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px

    class USER user
    class AGENT,AGENT2 agent
    class MEM_PROCESS mem
    class RECALL recall
    class JUDGE,STORE,SKIP,LOAD,INJECT node
```

---

## 二、多 Agent 共享记忆

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    subgraph AGENTS["🤖 三个 Agent"]
        direction LR
        A1["🩺 诊断 Agent<br/>输出诊断结论"]
        A2["📋 方案 Agent<br/>需要诊断结果"]
        A3["📄 报告 Agent<br/>需要诊断+方案"]
    end

    subgraph MODES["🔄 三种共享方式"]
        direction LR

        subgraph M1["📊 共享 State"]
            direction TB
            ST["{'diagnosis':'...',<br/>'solution':'...',<br/>'report':'...'}" ]
            ST_DESC["所有 Agent 读写同一份 State<br/>LangGraph · 紧耦合"]
        end

        subgraph M2["📁 文件桥接"]
            direction TB
            F1["workspace/<br/>diagnosis.md"]
            F2["workspace/<br/>solution.md"]
            F1 -.->|复制| F2
            F2_DESC["Agent 间不共享内存<br/>OpenClaw · 松耦合"]
        end

        subgraph M3["📨 消息总线"]
            direction TB
            PUB["发布 diagnosis.complete"]
            SUB["订阅 diagnosis.complete"]
            PUB --> SUB
            M3_DESC["事件驱动<br/>动态加入/退出"]
        end
    end

    AGENTS --> MODES

    classDef agents fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef modes fill:#f5f3ff,color:#5b21b6,stroke:#7c3aed,stroke-width:2px
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px

    class AGENTS agents
    class MODES modes
    class A1,A2,A3,ST,ST_DESC,F1,F2,F2_DESC,PUB,SUB,M3_DESC node
    class M1,M2,M3 modes
```

---

## 三、多智能体知识图谱

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    subgraph QUERY["🔍 查询方式"]
        direction LR
        Q1["直接查询<br/>'2号断路器在哪'"]
        Q2["关系查询<br/>'梅花站有哪些设备'"]
        Q3["推理查询<br/>'线圈烧毁→影响哪些设备'"]
    end

    subgraph GRAPH["🕸 知识图谱"]
        direction LR
        N1["(梅花变电站)"]
        N2["(2号断路器)"]
        N3["(分闸线圈)"]
        N4["(烧毁)"]
        N1 --"包含"--> N2
        N2 --"包含"--> N3
        N3 --"故障模式"--> N4
    end

    subgraph TOOLS["🔧 Agent Tools"]
        direction LR
        T1["query_node(id)<br/>查一个实体"]
        T2["query_neighbors(id)<br/>查一跳邻居"]
        T3["query_path(from,to)<br/>最短路径"]
    end

    QUERY --> GRAPH
    GRAPH --> TOOLS
    TOOLS --> ANSWER["✅ 回答<br/>'线圈烧毁→影响2号断路器<br/>→影响梅花变电站220kV供电'"]

    classDef query fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef graph fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef tools fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    classDef answer fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px

    class QUERY query
    class GRAPH graph
    class TOOLS tools
    class ANSWER answer
    class Q1,Q2,Q3,N1,N2,N3,N4,T1,T2,T3 node
```

---

## 四、模型路由

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    USER["👤 用户输入"] --> CLASSIFY["🔍 复杂度分类器<br/>小模型快速判断<br/><200ms"]

    CLASSIFY -->|simple<br/>查询/统计/闲聊| SMALL["🟢 小模型<br/>Ollama 7B / qwen-turbo<br/>免费 · <500ms"]
    CLASSIFY -->|complex<br/>诊断/分析/报告| LARGE["🔵 大模型<br/>qwen-plus / qwen-max<br/>付费 · ~1s"]

    SMALL --> LOG["📊 路由日志<br/>agent_id · complexity · model · cost"]
    LARGE --> LOG

    LOG --> DASH["📈 Dashboard<br/>路由命中率 · 成本节省"]

    classDef user fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef classify fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    classDef small fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef large fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef log fill:#f5f3ff,color:#5b21b6,stroke:#7c3aed,stroke-width:1px
    classDef dash fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:1px

    class USER user
    class CLASSIFY classify
    class SMALL small
    class LARGE large
    class LOG log
    class DASH dash
```

---

## 五、Ops 监控

```mermaid
%%{init: {'flowchart': {'curve': 'basis'}}}%%
graph TB
    GW["⚡ AI Gateway"] --> LOG_JSON["📝 logs/usage.jsonl<br/>每次调用一条日志"]

    subgraph METRICS["📊 监控三指标"]
        direction LR
        TOKEN["🔢 Token 用量<br/>按 Agent/天拆分"]
        COST["💰 API 费用<br/>Token×单价=实时成本"]
        LATENCY["⏱ 延迟分布<br/>P50 · P95 · P99"]
    end

    LOG_JSON --> METRICS

    METRICS --> DASHBOARD["📈 Ops Dashboard<br/>· 概览卡片（Token/费用/延迟/错误率）<br/>· Chart.js 柱状图+折线图<br/>· 最近 20 条调用记录表格"]

    METRICS --> ALERTS["🚨 告警引擎"]
    ALERTS --> A1["💸 单日费用 > ¥5"]
    ALERTS --> A2["🐌 P95 延迟 > 3s"]
    ALERTS --> A3["❌ 错误率 > 5%"]

    A1 & A2 & A3 --> NOTIFY["📨 告警日志<br/>logs/alerts.jsonl<br/>（可扩展飞书通知）"]

    classDef gw fill:#f1f5f9,color:#334155,stroke:#64748b,stroke-width:2px
    classDef log fill:#eff6ff,color:#1e40af,stroke:#3b82f6,stroke-width:1px
    classDef metrics fill:#fffbeb,color:#92400e,stroke:#d97706,stroke-width:2px
    classDef dash fill:#ecfdf5,color:#065f46,stroke:#059669,stroke-width:2px
    classDef alert fill:#fff1f2,color:#9f1239,stroke:#e11d48,stroke-width:2px
    classDef node fill:#fafafa,color:#44403c,stroke:#d6d3d1,stroke-width:1px

    class GW gw
    class LOG_JSON log
    class METRICS metrics
    class DASHBOARD dash
    class ALERTS alert
    class TOKEN,COST,LATENCY,A1,A2,A3,NOTIFY node
```

---

## 六、三种记忆方案对比

| 维度 | 短期记忆 | 长期记忆 | 共享记忆 |
|------|:--:|:--:|:--:|
| 存储位置 | 内存（messages list） | 文件/向量库/KV | State / 文件 / 消息总线 |
| 生命周期 | 单次对话 | 跨会话持久化 | 跨 Agent、跨会话 |
| 检索方式 | 顺序读取 | 语义检索 / Key 查询 | 读写 State / Pub-Sub |
| 代表实现 | LangChain Memory | MEMORY.md / Chroma | LangGraph State / OpenClaw Bridge |

## 七、快速上手建议

| 阶段 | 做什么 | 技术选型 |
|------|------|------|
| **Level 1** | 跨会话记忆 | JSON 文件 + LLM 自主判断写入 |
| **Level 2** | 多 Agent 共享上下文 | LangGraph State 共享 |
| **Level 3** | 语义相似记忆检索 | 向量数据库（Chroma / FAISS） |
| **Level 4** | 设备关系推理 | JSON 知识图谱 + 图查询 Tool |
| **Level 5** | 全企业知识图谱 | Neo4j / 图数据库（生产级） |
