# Lab 7.5 — LangGraph 多 Agent 编排

> 用 StateGraph 把故障诊断流程拆成 4 个节点，用条件边控制路由——同样的任务，StateGraph 的执行路径是确定的，ReAct Agent 是随机的。

---

## 🎯 实验目标

1. 理解 StateGraph 的四要素：**State（状态）→ Node（节点）→ Edge（边）→ Workflow（图）**
2. 实现一个 4 节点故障诊断工作流：Router → Diagnosis → Solution → Execute
3. 用条件边（`add_conditional_edges`）根据严重程度选择不同路径
4. 用 `stream` 观察每个节点的输入输出，理解状态的传递过程

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | LLM 调用需要 |
| 3 | 完成 Lab 7.1 | 了解 Agent 的基本概念 |
| 4 | 安装依赖 | `pip install langchain langchain-openai langgraph` |

---

## 📦 实验数据

### 数据文件

| 文件路径 | 用途 | 说明 |
|----------|------|------|
| `demo/equipment_data.json` | 设备数据 | 12 台电力设备 |
| `demo/knowledge_base.json` | 知识库 | 12 篇技术文档 |
| `demo/langgraph_skeleton.py` | 骨架代码 | 图结构 + 节点函数 + 条件函数框架 |

### 背景信息

#### LangGraph vs ReAct Agent：区别是什么？

lab7.1 的 ReAct Agent 让 AI **自主决定**调用哪个工具、调几次、什么顺序——这是一种"自由探索"模式。

LangGraph 的 StateGraph 是**显式编排**——你定义好节点和边，AI 按你设计的流程图执行。这更接近传统软件开发中的"工作流引擎"思想。

```
ReAct Agent（自由探索）：
  适合：开放式任务，AI 需要灵活应变

StateGraph（显式编排）：
  适合：有确定流程的任务，需要审批、审计、合规
  如：故障诊断 → 方案生成 → 审批 → 执行
```

#### StateGraph 四要素

```
┌─────────────────────────────────────────────────┐
│              StateGraph 工作流                    │
│                                                 │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐    │
│  │ Router  │ →  │Diagnosis │ →  │Solution │    │
│  │ 意图识别 │    │ 故障诊断  │    │ 方案生成 │    │
│  └─────────┘    └──────────┘    └─────────┘    │
│       │                               │         │
│       │           条件边               │         │
│       │       severity=normal         │         │
│       │           直接跳过方案生成      │         │
│       │                               │         │
│       └───────────→ Execute ←─────────┘         │
│                    执行/记录                     │
└─────────────────────────────────────────────────┘
```

**State（状态）**：节点间传递的数据结构。每个节点读 state → 处理 → 写 state。

**Node（节点）**：一个 Python 函数，接收 state，返回更新后的 state。

**Edge（边）**：节点之间的连接。固定边（`add_edge`）确定性的 → 条件边（`add_conditional_edges`）分支的。

**Workflow（图）**：所有节点和边的集合，`compile()` 后变成一个可运行的 graph。

#### 条件边的本质

```python
# 条件边 = 代码里的 if-else，但可视化在图中
def route_by_severity(state):
    if state["severity"] == "critical":
        return "solution"     # 严重 → 生成紧急方案
    elif state["severity"] == "normal":
        return "execute"      # 正常 → 跳过方案，直接记录
    else:
        return "solution"     # 默认 → 生成方案
```

---

## 🔬 实验步骤

### Task 1：读懂图结构

**目标**：理解骨架代码中 StateGraph 的设计意图，画出完整的流程分支。

**步骤**：

1. 打开 `demo/langgraph_skeleton.py`，找到 `build_graph` 中的图结构注释
2. 理解以下路径的含义：

```
路径 A（故障诊断）：
  Router → Diagnosis → Solution → Execute → END
  
路径 B（信息查询）：
  Router → Solution → Execute → END（跳过诊断）

路径 C（巡检）：
  Router → Execute → END（跳过诊断和方案）

路径 D（正常设备）：
  Router → Diagnosis → Execute → END（跳过方案）

路径 E（意图不明）：
  Router → Fallback → END
```

3. 在纸上画出完整的流程图，标注每个条件边的判断逻辑
4. 理解 `AgentState` 中每个字段在不同节点间的生命周期：
   - `user_query` → Router 消费
   - `intent`、`device_id`、`symptom` → Router 产出，Diagnosis 消费
   - `diagnosis_result`、`severity` → Diagnosis 产出，Solution/Execute 消费
   - `solution` → Solution 产出，Execute 消费

**预期结果**：能画出完整的流程图，并说明状态字段在各个节点间的流转。

---

### Task 2：实现 Router 和 Diagnosis 节点

**目标**：完成前两个节点函数，跑通图的前半段。

**步骤**：

1. 实现 `router_node`：

```python
def router_node(state: AgentState) -> AgentState:
    state["messages"].append(f"[Router] 收到用户输入: {state['user_query'][:80]}...")
    
    # 用 LLM 分析意图
    llm = ChatOpenAI(model=MODEL, base_url=DASHSCOPE_BASE_URL, api_key=DASHSCOPE_API_KEY, temperature=0)
    
    prompt = f"""分析以下用户输入的意图，提取设备编号和故障现象。

用户输入：{state['user_query']}

返回 JSON 格式：
{{"intent": "diagnosis|inquiry|inspection|unknown", "device_id": "设备编号（如 EP-B-001，没有则 null）", "symptom": "故障现象描述（没有则 null）"}}
"""
    response = llm.invoke(prompt)
    result = json.loads(response.content)
    
    state["intent"] = result.get("intent", "unknown")
    state["device_id"] = result.get("device_id")
    state["symptom"] = result.get("symptom")
    state["messages"].append(f"[Router] 意图={state['intent']}, 设备={state['device_id']}, 现象={state['symptom']}")
    
    return state
```

2. 实现 `diagnosis_node`：

```python
def diagnosis_node(state: AgentState) -> AgentState:
    # 查设备
    equipments = load_equipment_data()
    device = next((e for e in equipments if e["id"] == state.get("device_id")), None)
    
    if device:
        state["device_info"] = json.dumps(device, ensure_ascii=False)
        state["messages"].append(f"[Diagnosis] 找到设备: {device['name']}")
    else:
        state["device_info"] = None
        state["messages"].append(f"[Diagnosis] 未找到设备 {state.get('device_id')}")
    
    # 查知识库 + LLM 诊断
    kb = load_knowledge_base()
    symptom = state.get("symptom", "")
    related = [d for d in kb if symptom and any(kw in d["content"] for kw in symptom.split())]
    
    llm = ChatOpenAI(model=MODEL, base_url=DASHSCOPE_BASE_URL, api_key=DASHSCOPE_API_KEY, temperature=0)
    context = json.dumps([{"title": d["title"], "content": d["content"][:300]} for d in related[:3]], ensure_ascii=False)
    
    prompt = f"""根据以下信息给出诊断结论。

设备信息：{state.get('device_info', '未知')}
故障现象：{symptom}
相关知识库：{context}

返回 JSON：
{{"diagnosis": "诊断结论（1-2句）", "severity": "normal|warning|critical"}}
"""
    response = llm.invoke(prompt)
    result = json.loads(response.content)
    
    state["diagnosis_result"] = result.get("diagnosis", "")
    state["severity"] = result.get("severity", "warning")
    state["messages"].append(f"[Diagnosis] 结论={state['diagnosis_result'][:60]}..., 严重程度={state['severity']}")
    
    return state
```

3. 临时建一个简单图来测试前两个节点：

```python
workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("diagnosis", diagnosis_node)
workflow.set_entry_point("router")
workflow.add_edge("router", "diagnosis")  # 临时用固定边
workflow.add_edge("diagnosis", END)

graph = workflow.compile()
result = graph.invoke({"user_query": "EP-D-002 断路器拒分了", "messages": []})
print(result["messages"])
```

**预期结果**：Router 正确识别意图和设备编号，Diagnosis 能找到设备并给出诊断结论。

---

### Task 3：实现 Solution 和 Execute 节点 + 条件路由

**目标**：完成后两个节点和条件函数，跑通完整图。

**步骤**：

1. 实现 `solution_node` 和 `execute_node`（与 Diagnosis 类似，根据 state 中的信息生成方案和执行记录）

2. 实现 `route_by_intent` 和 `route_by_severity`：

```python
def route_by_intent(state: AgentState) -> str:
    mapping = {
        "diagnosis": "diagnosis",
        "inquiry": "solution",
        "inspection": "execute",
    }
    return mapping.get(state["intent"], "fallback")

def route_by_severity(state: AgentState) -> str:
    if state.get("severity") == "normal":
        return "execute"
    return "solution"
```

3. 完成 `build_graph`：

```python
def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("router", router_node)
    workflow.add_node("diagnosis", diagnosis_node)
    workflow.add_node("solution", solution_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("fallback", fallback_node)
    
    workflow.set_entry_point("router")
    
    workflow.add_conditional_edges("router", route_by_intent, {
        "diagnosis": "diagnosis",
        "inquiry": "solution", 
        "inspection": "execute",
        "fallback": "fallback",
    })
    
    workflow.add_conditional_edges("diagnosis", route_by_severity, {
        "solution": "solution",
        "execute": "execute",
    })
    
    workflow.add_edge("solution", "execute")
    workflow.add_edge("execute", END)
    workflow.add_edge("fallback", END)
    
    return workflow.compile()
```

**预期结果**：完整图可以编译并运行，不同任务走不同的路径。

---

### Task 4：用 stream 观察执行过程

**目标**：完成 `stream_graph` 函数，逐节点观察状态变化。

**步骤**：

1. 实现 stream：

```python
def stream_graph(graph, user_query):
    print(f"\n{'='*50}")
    print(f"用户输入: {user_query}")
    
    for event in graph.stream({"user_query": user_query, "messages": []}):
        for node_name, node_output in event.items():
            print(f"\n📍 节点 [{node_name}] 执行完成")
            
            # 打印该节点的关键产出
            if node_name == "router":
                print(f"   意图: {node_output.get('intent', 'N/A')}")
                print(f"   设备: {node_output.get('device_id', 'N/A')}")
            elif node_name == "diagnosis":
                print(f"   诊断: {node_output.get('diagnosis_result', 'N/A')[:80]}")
                print(f"   严重程度: {node_output.get('severity', 'N/A')}")
            elif node_name == "solution":
                print(f"   方案: {node_output.get('solution', 'N/A')[:80]}")
            elif node_name == "execute":
                print(f"   执行结果: {node_output.get('execution_result', 'N/A')[:80]}")
            
            # 打印该节点新增的消息
            node_msgs = node_output.get("messages", [])
            print(f"   消息数: {len(node_msgs)}")
    
    print(f"\n{'='*50}")
    print("完整执行日志:")
    # 从最后一个节点的 messages 获取完整日志
    for msg in node_output.get("messages", []):
        print(f"  {msg}")
```

2. 测试两条不同的路径：

```
# 路径 A：完整诊断
stream_graph(graph, "EP-D-002 的断路器拒分了，需要紧急处理")

# 路径 B：信息查询
stream_graph(graph, "天河区有哪些变压器？")
```

3. 对比两次执行遍历了哪些节点。

**预期结果**：stream 输出显示了每个节点的执行顺序和状态变化，两条路径遍历的节点不同。

---

### Task 5（选做）：对比 StateGraph vs ReAct Agent

**目标**：用同一个任务对比两种编排方式的差异。

**步骤**：

1. 创建一个 ReAct Agent（lab7.1 的方式），给它同样的工具
2. 用 StateGraph 和 ReAct Agent 分别执行同一个任务
3. 对比：

| 维度 | StateGraph | ReAct Agent |
|------|:---:|:---:|
| 执行路径是否确定 | ✅ 确定 | ❌ 不确定 |
| 能否跳过不必要的步骤 | ✅ 条件边控制 | ⚠️ AI 自己判断 |
| 执行过程可审计 | ✅ stream 逐节点 | ⚠️ 黑盒 |
| 适合什么场景 | 合规流程、需审批 | 开放式探索 |

**预期结果**：理解两种方式的适用场景差异。

---

## 📊 结果产出

| 产出 | 格式 | 位置 | 说明 |
|------|------|------|------|
| 完整 StateGraph | `.py` | `demo/langgraph_skeleton.py` | 4 节点 + 条件路由均已实现 |
| Stream 输出 | 终端文本 | 终端 | 两条路径的执行日志 |
| 流程图（选做） | 手绘/截图 | 任意 | 标注了所有节点和条件分支 |

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 | 检查 |
|------|--------|----------|------|
| 1 | **Router + Diagnosis 截图** | 两个节点正确分析了意图和设备信息 | ☐ |
| 2 | **完整图 stream 截图** | 两条不同路径的执行日志，遍历的节点不同 | ☐ |
| 3 | **条件路由验证** | severity=normal 时跳过了 solution 节点 | ☐ |
| 4 | **图结构代码截图** | `build_graph` 函数完整代码 | ☐ |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| `stream` 输出乱序 | 每个节点的输出是独立的 dict | 用 `node_output.get("messages", [])` 获取日志 |
| LLM 返回的 JSON 解析失败 | LLM 可能返回带 markdown 代码块的内容 | 用 `response.content.strip().strip('```json').strip('```')` |
| 条件边走错路径 | route 函数返回的字符串和 `add_conditional_edges` 的 mapping 不匹配 | 检查返回值是否和 mapping 的 key 完全一致 |
| 状态在节点间丢失 | TypedDict 需要显式复制和更新 | 每个节点返回的 dict 要包含所有要保留的字段 |
| `compile()` 报错 | 有节点没有边指向它或从它出发 | 检查所有非 START/END 节点都有入边和出边 |

---

**🎉 恭喜完成实验！**
