# Lab 7.5b — 多 Agent 协作

> 三个专业 Agent + 一个 Supervisor 调度中心——每个 Agent 有自己的 System Prompt 和专属 Tool，Supervisor 决定"下一步调谁"，所有 Agent 共享同一份 State。

---

## 🎯 实验目标

1. 给每个 Agent 分配专属 System Prompt 和 Tool 集合，让它成为某个领域的"专家"
2. 实现 Supervisor 模式：一个调度节点决定调用哪个 Agent，Agent 执行后回到 Supervisor
3. 理解状态共享：Diagnosis Agent 写入的诊断结论，Solution Agent 如何读到、如何利用
4. 对比单工作流（lab7.5）和多 Agent 协作（本实验）的适用场景差异

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | LLM 调用需要 |
| 3 | 完成 Lab 7.5 | 理解 StateGraph 的基本概念 |
| 4 | 安装依赖 | `pip install langchain langchain-openai langgraph` |

---

## 📦 实验数据

| 文件路径 | 用途 | 说明 |
|----------|------|------|
| `demo/equipment_data.json` | 设备数据 | 共享数据 |
| `demo/knowledge_base.json` | 知识库 | 共享数据 |
| `demo/multi_agent_skeleton.py` | 骨架代码 | 3 个 Agent + Supervisor + 图结构框架 |

### 背景信息

#### 多 Agent 的核心问题

lab7.5 是"一个 LLM 跑完所有节点"——Router、Diagnosis、Solution、Execute 用的都是同一个 LLM 调用。这不叫多 Agent，叫**单 Agent 多步骤**。

真正的多 Agent 是每个 Agent 有自己的"人格"：

```
Diagnosis Agent          Solution Agent           Execute Agent
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ System:      │        │ System:      │        │ System:      │
│ "你是设备    │        │ "你是方案    │        │ "你是执行    │
│  故障诊断    │        │  制定专家"   │        │  记录专员"   │
│  专家"       │        │              │        │              │
│              │        │              │        │              │
│ Tools:       │        │ Tools:       │        │ Tools:       │
│ ·查设备      │        │ ·生成方案    │        │ ·创建记录    │
│ ·查知识库    │        │ ·发告警      │        │ ·推送通知    │
└──────────────┘        └──────────────┘        └──────────────┘
```

三个 Agent 各自有不同的 System Prompt（专业领域不同）和 Tool 集合（能力不同）。Supervisor 负责调度：看当前 State → 决定调谁 → Agent 执行完回到 Supervisor → 再决定。

#### Supervisor 模式 vs 固定流水线

```
lab7.5 的固定流水线：
  Router → Diagnosis → Solution → Execute → END
  路径是编译时确定的

本实验的 Supervisor 模式：
  Supervisor ⇄ Diagnosis Agent
  Supervisor ⇄ Solution Agent
  Supervisor ⇄ Execute Agent
  Supervisor → Summarize → END
  路径是运行时动态决定的
```

Supervisor 可以根据 Agent 的返回结果调整策略——比如 Diagnosis Agent 诊断结果是 normal，Supervisor 可以直接跳到 Execute Agent 而跳过 Solution Agent。

#### 状态共享机制

三个 Agent 通过 `MultiAgentState` 共享数据：

```
MultiAgentState:
  ┌─ diagnosis_result  ← Diagnosis Agent 写入
  │                      Solution Agent 读
  │                      Execute Agent 读
  │
  ├─ solution_plan     ← Solution Agent 写入
  │                      Execute Agent 读
  │
  ├─ execution_record  ← Execute Agent 写入
  │                      Summarize 节点读
  │
  └─ task_history      ← Supervisor 写入
                         所有 Agent 可见
```

不需要"传参数"——Agent A 写完字段后回到 Supervisor，Supervisor 调 Agent B，Agent B 从同一个 state 中读 Agent A 的产出。

---

## 🔬 实验步骤

### Task 1：理解三个 Agent 的职责边界

**目标**：理解每个 Agent 的 System Prompt 和 Tool 设计。

**步骤**：

1. 打开 `demo/multi_agent_skeleton.py`，找到三个 Agent 的函数和各自的工具
2. 画出 Agent-职责-Tool 的对应关系：

| Agent | 职责 | 专属 Tool | 写入 State 的字段 |
|------|------|----------|------------------|
| Diagnosis Agent | 诊断故障原因 + 判断严重程度 | `search_equipment_by_id`、`search_knowledge_base` | `diagnosis_result`、`severity`、`related_procedures` |
| Solution Agent | 根据诊断结论生成处置方案 | `generate_repair_plan`、`send_alert` | `solution_plan`、`alert_sent` |
| Execute Agent | 记录巡检结果、发送通知 | `create_inspection_record`、`push_notification` | `execution_record`、`notification_sent` |

3. 思考：如果让一个 Agent 同时拥有 6 个工具，会发生什么？

**预期结果**：能说清楚每个 Agent 的职责边界，以及为什么 Tool 不能混用。

---

### Task 2：实现各 Agent 的专属工具

**目标**：完成 6 个工具函数，让每个 Agent 有可用的能力。

**步骤**：

1. 依次实现 6 个 `@tool` 函数：

```python
# Diagnosis Agent 工具
@tool
def search_equipment_by_id(device_id: str) -> str:
    equipments = load_equipment_data()
    for eq in equipments:
        if eq["id"].upper() == device_id.upper():
            return json.dumps(eq, ensure_ascii=False, indent=2)
    return f"未找到设备 {device_id}"

@tool
def search_knowledge_base(symptom: str) -> str:
    kb = load_knowledge_base()
    results = []
    for doc in kb:
        if any(kw in doc["content"] + doc["title"] for kw in symptom.split()):
            results.append({"title": doc["title"], "snippet": doc["content"][:200]})
    if not results:
        return f"知识库中未找到与 '{symptom}' 相关的文档"
    return json.dumps(results[:3], ensure_ascii=False, indent=2)
```

2. 每个 Agent 的工具只服务于它的职责——Diagnosis Agent 不需要 `send_alert`

**预期结果**：6 个工具均可独立调用，各自返回合理结果。

---

### Task 3：实现三个 Agent 节点

**目标**：让每个 Agent 能用专属 System Prompt + 专属 Tool 完成任务。

**步骤**：

1. 以 Diagnosis Agent 为例，实现 Agent 节点：

```python
def diagnosis_agent_node(state: MultiAgentState) -> MultiAgentState:
    state["task_history"].append("diagnosis_agent")
    
    llm = ChatOpenAI(model=MODEL, base_url=DASHSCOPE_BASE_URL, api_key=DASHSCOPE_API_KEY, temperature=0)
    
    system_prompt = """你是电力设备故障诊断专家。你有以下工具：
- search_equipment_by_id：根据设备编号查找设备详细信息
- search_knowledge_base：根据故障现象搜索相关技术文档

请按以下步骤工作：
1. 首先确定设备编号。如果用户没提供，请求 Supervisor 帮助明确
2. 查设备信息，了解设备当前状态
3. 查知识库中相关的故障处理规程
4. 综合判断：可能的原因、严重程度（normal/warning/critical）

输出 JSON 格式：
{"diagnosis": "诊断结论", "severity": "normal|warning|critical", "procedures": ["相关规程标题"]}"""

    user_prompt = f"用户问题：{state['user_query']}\n请开始诊断。"
    
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
    
    result = json.loads(response.content)
    state["diagnosis_result"] = result.get("diagnosis", "")
    state["severity"] = result.get("severity", "warning")
    state["related_procedures"] = result.get("procedures", [])
    
    return state
```

2. 同样实现 `solution_agent_node` 和 `execute_agent_node`
3. **关键点**：Solution Agent 从 `state["diagnosis_result"]` 读数据，而不是重新诊断。这就是状态共享的价值。

**预期结果**：三个 Agent 依次执行后，State 中的诊断结论 → 处置方案 → 执行记录形成完整链条。

---

### Task 4：实现 Supervisor 调度逻辑

**目标**：完成 Supervisor 节点 + 路由函数，形成"调度 → 执行 → 回到调度"循环。

**步骤**：

1. 实现 Supervisor（方式 A——硬编码规则）：

```python
def supervisor_node(state: MultiAgentState) -> MultiAgentState:
    # 按顺序调度：诊断 → 方案 → 执行 → 汇总
    history = state.get("task_history", [])
    
    if "diagnosis_agent" not in history:
        state["next_agent"] = "diagnosis_agent"
    elif "solution_agent" not in history:
        state["next_agent"] = "solution_agent"
    elif "execute_agent" not in history:
        state["next_agent"] = "execute_agent"
    else:
        state["next_agent"] = "FINISH"
    
    return state
```

2. 进阶方式（方式 B——LLM 调度）：

```python
def supervisor_node(state: MultiAgentState) -> MultiAgentState:
    llm = ChatOpenAI(model=MODEL, base_url=DASHSCOPE_BASE_URL, api_key=DASHSCOPE_API_KEY, temperature=0)
    
    summary = f"""当前状态：
- 用户问题：{state['user_query']}
- 已执行：{state.get('task_history', [])}
- 诊断结论：{state.get('diagnosis_result', '无')}
- 处置方案：{state.get('solution_plan', '无')}
- 执行记录：{state.get('execution_record', '无')}

可调用的 Agent：
- diagnosis_agent：诊断故障
- solution_agent：生成方案
- execute_agent：执行记录

请决定下一步调用哪个 Agent。如果任务已全部完成，返回 FINISH。
只返回 Agent 名或 FINISH。"""
    
    response = llm.invoke(summary)
    next_agent = response.content.strip().lower()
    
    valid_agents = ["diagnosis_agent", "solution_agent", "execute_agent", "finish"]
    state["next_agent"] = next_agent if next_agent in valid_agents else "FINISH"
    return state
```

3. 组装完整图（关键模式）：

```python
workflow = StateGraph(MultiAgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("diagnosis_agent", diagnosis_agent_node)
workflow.add_node("solution_agent", solution_agent_node)
workflow.add_node("execute_agent", execute_agent_node)
workflow.add_node("summarize", summarize_node)

workflow.set_entry_point("supervisor")

# Supervisor → 各 Agent（条件路由）
workflow.add_conditional_edges("supervisor", route_to_agent, {
    "diagnosis_agent": "diagnosis_agent",
    "solution_agent": "solution_agent",
    "execute_agent": "execute_agent",
    "FINISH": "summarize",
})

# 每个 Agent 执行完 → 回到 Supervisor（核心差异！）
workflow.add_edge("diagnosis_agent", "supervisor")
workflow.add_edge("solution_agent", "supervisor")
workflow.add_edge("execute_agent", "supervisor")

workflow.add_edge("summarize", END)

graph = workflow.compile()
```

**注意**：每个 Agent 执行完不是直线前进，而是回到 Supervisor。这和 lab7.5 的 `Diagnosis → Solution → Execute → END` 完全不同。

**预期结果**：Supervisor 依次调度三个 Agent，task_history 记录调度历史。

---

### Task 5：验证状态共享

**目标**：验证 Agent 间的数据传递是否正确。

**步骤**：

1. 跑完整流程，检查 State 中各字段的值
2. 验证以下数据流是否通畅：

```
Diagnosis Agent 写入:
  state["diagnosis_result"] = "断路器分闸线圈电阻异常"
  state["severity"] = "critical"
           │
           ▼
Supervisor 读 state → 决定调 solution_agent
           │
           ▼
Solution Agent 从 state 读:
  diagnosis = state["diagnosis_result"]  # "断路器分闸线圈电阻异常"
  severity = state["severity"]           # "critical"
  → 生成紧急处置方案
```

3. 如果状态共享失败（Solution Agent 没读到诊断结论），定位原因

**预期结果**：Solution Agent 的 `system_prompt` 中引用了 `state["diagnosis_result"]`，生成的方案是基于诊断结论的，不是自己乱编的。

---

## 📊 结果产出

| 产出 | 格式 | 说明 |
|------|------|------|
| 多 Agent 完整代码 | `.py` | 3 Agent + Supervisor + 图结构 |
| 调度历史 | 终端输出 | 每个 Agent 的执行顺序 |
| 状态共享验证 | 终端输出 | 各 Agent 写入和读取的字段对照 |

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 |
|------|--------|----------|
| 1 | **工具实现截图** | 6 个 `@tool` 函数代码 |
| 2 | **Agent System Prompt 截图** | 三个 Agent 各自不同的 System Prompt |
| 3 | **Supervisor 调度截图** | 运行日志显示 Agent 调度顺序 |
| 4 | **状态共享验证截图** | Solution Agent 的产出引用了 Diagnosis 的诊断结论 |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| Supervisor 无限循环 | Agent 执行完回到 Supervisor，但 task_history 没更新 | 每个 Agent 开头加 `state["task_history"].append(agent_name)` |
| Solution Agent 不读诊断结论 | System Prompt 没指引它读 state 中的字段 | 在 System Prompt 中明确说"你不需要重新诊断，直接使用已有的诊断结论" |
| Agent 用了不该用的 Tool | 把 6 个工具都传给了每个 Agent | 每个 Agent 只传自己的专属 Tool 列表 |
| 三个 Agent 返回结果互相矛盾 | 数据在传递中被 LLM 改写 | 不做自然语言传递，用 JSON 结构化字段：`diagnosis_result` → `solution_plan` → `execution_record` |

---

**🎉 恭喜完成实验！**
