# Lab 7.5 — LangGraph 工作流编排

> 用 StateGraph 把故障诊断流程拆成 4 个节点，用条件边控制路由——同样的任务，StateGraph 的执行路径是确定的，ReAct Agent 是随机的。

---

## 🎯 实验目标

1. 理解 StateGraph 四要素：**State（状态）→ Node（节点）→ Edge（边）→ Workflow（图）**
2. 实现一个 4 节点故障诊断工作流：Router → Diagnosis → Solution → Execute
3. 用条件边根据严重程度选择不同路径
4. 用 `stream` 观察每个节点的输入输出

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | LLM 调用需要 |
| 3 | 完成 Lab 7.1 | 了解 `create_react_agent` 的基本用法 |
| 4 | 安装依赖 | `pip install langchain langchain-openai langgraph` |

---

## 📦 实验数据

| 文件路径 | 用途 | 说明 |
|----------|------|------|
| `demo/equipment_data.json` | 设备数据 | 12 台电力设备 |
| `demo/knowledge_base.json` | 知识库 | 12 篇技术文档 |
| `demo/langgraph_skeleton.py` | 骨架代码 | 图结构 + 节点函数框架 |

### 背景信息

#### ReAct Agent vs StateGraph：区别是什么？

lab7.1 的 ReAct Agent 让 AI **自主决定**调用哪个工具、调几次、什么顺序——这是"自由探索"模式。

StateGraph 是**显式编排**——你定义好节点和边，AI 按你设计的流程图执行。

```
ReAct Agent（自由探索）：
  AI 自己决定下一步 → 适合开放式任务

StateGraph（显式编排）：
  你定义的流程图 → 适合有确定流程的任务（如故障诊断 → 方案生成 → 执行）
```

#### StateGraph 四要素

```
┌──────────────────────────────────────────────┐
│              StateGraph 工作流                │
│                                              │
│  ┌─────────┐   ┌──────────┐   ┌─────────┐   │
│  │ Router  │ → │Diagnosis │ → │Solution │   │
│  │ 意图识别 │   │ 故障诊断  │   │ 方案生成 │   │
│  └─────────┘   └──────────┘   └─────────┘   │
│       │                            │         │
│       │      条件边                 │         │
│       │   severity=normal          │         │
│       │   直接跳过方案生成           │         │
│       │                            │         │
│       └────────→ Execute ←─────────┘         │
│                  执行/记录                    │
└──────────────────────────────────────────────┘
```

- **State（TypedDict）**：节点间传递的数据。每个节点读 state → 处理 → 写 state
- **Node（函数）**：Python 函数，输入 state，输出更新后的 state
- **Edge**：节点之间的连接。固定边（`add_edge`）→ 确定性；条件边（`add_conditional_edges`）→ 分支
- **Workflow**：所有节点和边的集合，`compile()` 后变成可运行的 graph

---

## 🔬 实验步骤

### Task 1：读懂图结构和状态定义

**目标**：理解骨架代码中的 `AgentState` 和图的 5 条执行路径。

**步骤**：

1. 打开 `demo/langgraph_skeleton.py`，找到 `AgentState` 和 `build_graph` 中的图结构注释
2. 理解以下 5 条路径分别适用于什么场景：

```
路径 A（故障诊断）：Router → Diagnosis → Solution → Execute → END
路径 B（信息查询）：Router → Solution → Execute → END（跳过诊断）
路径 C（直接巡检）：Router → Execute → END（跳过诊断和方案）
路径 D（正常设备）：Router → Diagnosis → Execute → END（跳过方案）
路径 E（意图不明）：Router → Fallback → END
```

3. 画出 `AgentState` 中字段在节点间的流转图：
   - `user_query` → Router 消费
   - `intent`、`device_id`、`symptom` → Router 产出，Diagnosis 消费
   - `diagnosis_result`、`severity` → Diagnosis 产出，Solution/Execute 消费
   - `solution` → Solution 产出，Execute 消费

**预期结果**：能用纸笔画出完整流程图，并说出状态字段在各节点间的生命周期。

---

### Task 2：实现 Router 和 Diagnosis 节点

**目标**：完成前两个节点，跑通图的前半段。

**步骤**：

1. 实现 `router_node`：用 LLM 分析 `user_query`，提取 `intent`、`device_id`、`symptom`

```python
def router_node(state: AgentState) -> AgentState:
    state["messages"].append(f"[Router] 收到: {state['user_query'][:80]}...")
    
    llm = ChatOpenAI(model=MODEL, base_url=DASHSCOPE_BASE_URL, api_key=DASHSCOPE_API_KEY, temperature=0)
    
    prompt = f"""分析以下用户输入的意图，提取设备编号和故障现象。
用户输入：{state['user_query']}
返回 JSON：{{"intent": "diagnosis|inquiry|inspection|unknown", "device_id": "设备编号或null", "symptom": "故障现象描述或null"}}"""
    
    result = json.loads(llm.invoke(prompt).content)
    state["intent"] = result.get("intent", "unknown")
    state["device_id"] = result.get("device_id")
    state["symptom"] = result.get("symptom")
    state["messages"].append(f"[Router] 意图={state['intent']}, 设备={state['device_id']}")
    return state
```

2. 实现 `diagnosis_node`：查设备数据 + 查知识库 + LLM 给出诊断结论和严重程度

3. 临时建一个直线图测试前两个节点：

```python
workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("diagnosis", diagnosis_node)
workflow.set_entry_point("router")
workflow.add_edge("router", "diagnosis")
workflow.add_edge("diagnosis", END)

graph = workflow.compile()
result = graph.invoke({"user_query": "EP-D-002 断路器拒分", "messages": []})
```

**预期结果**：Router 正确提取设备编号，Diagnosis 找到设备信息并给出诊断结论。

---

### Task 3：实现完整图 + 条件路由

**目标**：完成 `solution_node`、`execute_node`、`fallback_node` 和两个条件函数，编译完整图。

**步骤**：

1. 实现 `route_by_intent`（Router → 各分支）和 `route_by_severity`（Diagnosis → Solution 或 Execute）
2. 实现 `solution_node`（根据诊断结论生成处置方案）和 `execute_node`（生成巡检记录）
3. 完成 `build_graph`，用 `add_conditional_edges` 组装完整图
4. 测试两条不同路径，验证条件路由生效

**预期结果**：同一个 query 走"诊断"路径；另一个 query 走"查询"路径时跳过 Diagnosis。

---

### Task 4：用 stream 观察执行过程

**目标**：逐节点观察状态变化和执行路径选择。

**步骤**：

```python
for event in graph.stream({"user_query": "EP-D-002 断路器拒分，需要紧急处理", "messages": []}):
    for node_name, node_output in event.items():
        print(f"\n📍 节点 [{node_name}] 完成")
        print(f"   意图: {node_output.get('intent', 'N/A')}")
        print(f"   严重程度: {node_output.get('severity', 'N/A')}")
```

对比两条不同任务的 stream 输出，观察遍历的节点顺序是否不同。

**预期结果**：stream 清晰展示每个节点的执行顺序，不同意图走不同路径。

---

## 📊 结果产出

| 产出 | 格式 | 说明 |
|------|------|------|
| 完整 StateGraph | `.py` | 4 节点 + 条件路由均可运行 |
| Stream 输出 | 终端文本 | 两条不同路径的执行日志对比 |

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 |
|------|--------|----------|
| 1 | **Router + Diagnosis 截图** | 正确提取了意图和设备信息 |
| 2 | **完整图 stream 截图** | 两条不同路径的执行日志 |
| 3 | **条件路由验证** | severity=normal 时跳过了 solution 节点 |
| 4 | **图结构代码截图** | `build_graph` 函数完整代码 |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| LLM 返回的 JSON 解析失败 | LLM 可能包裹了 markdown 代码块 | `response.content.strip().strip('```json').strip('```')` |
| 条件边走错路径 | 返回字符串和 mapping 的 key 不匹配 | 检查 `route_*` 函数的返回值和 `add_conditional_edges` 的 mapping 是否一致 |
| 状态在节点间丢失 | TypedDict 需要显式更新字段 | 每个节点中 `state["field"] = value` |
| `compile()` 报错 | 有节点缺少入边或出边 | 检查非 START/END 节点都有入边和出边 |

---

**🎉 恭喜完成实验！**

---

> 完成本实验后，进入 [Lab 7.5b](lab7.5b-multi-agent.md) — 在一个工作流中编排多个各司其职的 Agent。
