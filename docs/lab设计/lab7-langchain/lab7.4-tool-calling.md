# Lab 7.4 — Tool Calling 进阶

> 给工具加 Pydantic 结构化参数，对比粗粒度和细粒度两套工具——同一个任务，Agent 调用行为完全不同。

---

## 🎯 实验目标

1. 用 Pydantic `BaseModel` 定义工具的结构化参数，告别 `query: str` 一刀切
2. 实现粗粒度和细粒度两套工具，对比 Agent 的行为差异
3. 理解工具异常处理的分层策略（工具内部 → Agent 感知 → 用户无感知）
4. 学会根据任务复杂度选择合适的工具粒度

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | LLM 调用需要 |
| 3 | 完成 Lab 7.1 | 了解 `@tool` 和 `create_react_agent` 的基本用法 |
| 4 | 安装依赖 | `pip install langchain langchain-openai langgraph pydantic` |

---

## 📦 实验数据

### 数据文件

| 文件路径 | 用途 | 说明 |
|----------|------|------|
| `demo/equipment_data.json` | 设备数据 | 12 台电力设备（lab7.1 已创建） |
| `demo/knowledge_base.json` | 知识库 | 12 篇技术文档（lab7.2 已创建） |
| `demo/tool_calling_skeleton.py` | 骨架代码 | 两套工具框架 + Pydantic 模型 + 对比框架 |

### 背景信息

#### 为什么需要结构化参数

lab7.1 中 `search_equipment` 的参数是 `keyword: str`。这在工作——但如果 Agent 想查"天河区的异常变压器"，这个 `keyword` 字符串就很尴尬：

```python
# 当前方式：所有筛选条件挤在一个字符串里
search_equipment("天河区 异常 变压器")

# 工具内部需要自己做字符串解析：
# "天河区" 是 region？"异常" 是 status？"变压器" 是 type？
# → 解析逻辑容易出错
```

用 Pydantic 定义结构化参数后：

```python
class EquipmentSearchFilter(BaseModel):
    device_type: Optional[str] = Field(description="设备类型")
    status: Optional[str] = Field(description="设备状态")  
    region: Optional[str] = Field(description="所属区域")

@tool(args_schema=EquipmentSearchFilter)
def search_equipment(device_type=None, status=None, region=None):
    # 参数已经按字段分好了，不需要再解析
```

Agent 会直接传结构化参数：`{"device_type": "变压器", "status": "异常", "region": "天河区"}`——不需要工具内部再做文本解析。

#### 粗粒度 vs 细粒度

| | 粗粒度 | 细粒度 |
|---|---|---|
| 工具数 | 1-2 个大工具 | 多个小工具，各司其职 |
| 每个工具的功能 | 大而全（搜设备+查知识库+巡检一站搞定） | 单一职责（只搜设备/只查状态/只诊断） |
| Agent 行为 | 调 1 次工具，给 LLM 塞一堆结果 | 调多次工具，每次拿精确结果 |
| 优势 | 简单、调用少 | 灵活、可控、可追踪 |
| 劣势 | Agent 对中间过程不可控 | 调用次数多、Token 消耗可能更高 |

---

## 🔬 实验步骤

### Task 1：理解 Pydantic 参数模型

**目标**：读懂骨架代码中的 Pydantic 模型，理解 Field 的 `description` 参数的作用。

**步骤**：

1. 打开 `demo/tool_calling_skeleton.py`，找到 `InspectionFilter` 和 `FaultDiagnosisInput` 两个 Pydantic 模型
2. 重点关注 `Field(description=...)` 的值——这个 description 就是给 AI 看的"参数说明书"
3. 理解 `Optional[str]` 的含义：这个参数是可选的，Agent 可以不传

```python
# Field description 的值直接决定了 AI 能否正确使用这个参数
class FaultDiagnosisInput(BaseModel):
    device_id: str = Field(
        description="设备编号，如 EP-B-001"  # ← AI 读到这行就知道要传设备编号
    )
    symptom: str = Field(
        description="故障现象描述，如 油温过高、断路器拒分、SF6压力低"
    )
    severity: str = Field(
        default="warning",
        description="严重程度：info（一般询问）、warning（需关注）、critical（紧急故障）"
    )
```

4. 思考：如果 `description` 写得很模糊（如"设备信息"），AI 会传什么？

**预期结果**：能说清楚每个 Field 的 description 对 AI 行为的直接影响。

---

### Task 2：实现粗粒度工具组

**目标**：完成 `search_all_equipment` 和 `inspect_device` 两个大而全的工具。

**步骤**：

1. 找到 `search_all_equipment` 函数
2. 完成实现：

```python
@tool
def search_all_equipment(query: str) -> str:
    """万能搜索工具：输入任意关键词，搜索设备、知识库、巡检记录等所有数据。"""
    equipments = load_equipment_data()
    kb = load_knowledge_base()
    
    results = {"equipment": [], "knowledge": [], "total": 0}
    
    # 在设备中搜索
    query_lower = query.lower()
    for eq in equipments:
        for field in ["name", "id", "type", "region", "status"]:
            if query_lower in str(eq.get(field, "")).lower():
                results["equipment"].append(eq)
                break
    
    # 在知识库中搜索
    for doc in kb:
        if query_lower in doc["content"].lower() or query_lower in doc["title"].lower():
            results["knowledge"].append({
                "title": doc["title"],
                "category": doc["category"],
                "snippet": doc["content"][:150],
            })
    
    results["total"] = len(results["equipment"]) + len(results["knowledge"])
    
    if results["total"] == 0:
        return f"未找到与 '{query}' 相关的任何信息。"
    
    return json.dumps(results, ensure_ascii=False, indent=2)
```

3. 同样完成 `inspect_device`。
4. 用粗粒度工具创建 Agent，测试几个查询：

```
"天河区有哪些异常设备？"
"变压器油温高怎么处理？"
```

5. 观察问题：
   - Agent 调用了几次工具？
   - 工具返回的结果里是否混了无关信息？
   - Agent 需要自己从一大堆结果中筛选？

**预期结果**：Agent 只调用 1 次工具，但返回结果可能混杂了设备信息和知识库文档，Agent 需要自己筛选。

---

### Task 3：实现细粒度工具组

**目标**：完成 5 个单一职责的工具，每个工具只做一件事。

**步骤**：

1. 分别完成 5 个细粒度工具：
   - `search_equipment_by_type` — 只按类型筛选
   - `search_equipment_by_status` — 只按状态筛选
   - `search_equipment_by_region` — 只按区域筛选
   - `diagnose_device_fault` — 故障诊断（使用 `FaultDiagnosisInput` 结构化参数）
   - `get_inspection_records` — 多维度巡检记录查询

2. 每个工具的返回结果要精准——不要返回无关数据

3. 以 `diagnose_device_fault` 为例，注意它使用了 `args_schema=FaultDiagnosisInput`：

```python
@tool(args_schema=FaultDiagnosisInput)
def diagnose_device_fault(device_id, symptom, severity="warning"):
    # 1. 查设备信息
    equipments = load_equipment_data()
    device = next((e for e in equipments if e["id"] == device_id), None)
    if not device:
        return f"❌ 未找到设备 {device_id}"
    
    # 2. 查知识库中相关的处置规程
    kb = load_knowledge_base()
    related = [d for d in kb if symptom in d["content"] or symptom in d["title"]]
    
    # 3. 按严重程度调整建议
    urgency = {
        "info": "可以安排下次巡检时关注",
        "warning": "建议在 24 小时内安排检查",
        "critical": "⚠️ 需要立即停机检查",
    }
    
    return json.dumps({
        "device": f"{device['name']} ({device_id})",
        "current_status": device["status"],
        "symptom": symptom,
        "severity": severity,
        "urgency": urgency.get(severity, ""),
        "related_procedures": [d["title"] for d in related[:3]],
        "recommendation": f"针对 {symptom} 问题，{urgency.get(severity, '请安排检查')}",
    }, ensure_ascii=False, indent=2)
```

4. 用细粒度工具创建 Agent，测试同样的查询：

```
"天河区有哪些异常设备？"
```

5. 观察：
   - Agent 可能先调 `search_equipment_by_region("天河区")` → 拿到天河区设备列表
   - 再调 `search_equipment_by_status("异常")` → 拿到异常设备列表
   - 或者直接多次调用组合筛选

**预期结果**：Agent 可能调用 2-3 次工具，每次拿到精确结果，最终回答更有条理。

---

### Task 4：粗粒度 vs 细粒度对比实验

**目标**：完成 `compare_granularity` 函数，量化两种策略的差异。

**步骤**：

1. 完成对比函数：

```python
def compare_granularity():
    llm = ChatOpenAI(model=MODEL, base_url=DASHSCOPE_BASE_URL, api_key=DASHSCOPE_API_KEY, temperature=0)
    
    coarse_agent = create_react_agent(llm, [search_all_equipment, inspect_device])
    fine_agent = create_react_agent(llm, [
        search_equipment_by_type, search_equipment_by_status, search_equipment_by_region,
        diagnose_device_fault, get_inspection_records,
    ])
    
    tasks = [
        "天河区有哪些设备状态异常？帮我看看可能的原因。",
        "我需要找所有变压器的巡检记录，特别是维护中的。",
    ]
    
    for task in tasks:
        print(f"\n{'='*60}")
        print(f"任务：{task}")
        
        # 粗粒度
        result = coarse_agent.invoke({"messages": [{"role": "user", "content": task}]})
        coarse_tool_calls = [m for m in result["messages"] if hasattr(m, "tool_calls") and m.tool_calls]
        print(f"\n粗粒度 Agent：")
        print(f"  工具调用次数：{len(coarse_tool_calls)}")
        print(f"  最终回答：{result['messages'][-1].content[:200]}...")
        
        # 细粒度
        result = fine_agent.invoke({"messages": [{"role": "user", "content": task}]})
        fine_tool_calls = [m for m in result["messages"] if hasattr(m, "tool_calls") and m.tool_calls]
        print(f"\n细粒度 Agent：")
        print(f"  工具调用次数：{len(fine_tool_calls)}")
        for tc in fine_tool_calls:
            for call in tc.tool_calls:
                print(f"    → {call['name']}({json.dumps(call.get('args', {}), ensure_ascii=False)})")
        print(f"  最终回答：{result['messages'][-1].content[:200]}...")
```

2. 填写对比表格：

| 维度 | 粗粒度 | 细粒度 |
|------|:---:|:---:|
| 工具调用次数（任务1） | ? | ? |
| 工具调用次数（任务2） | ? | ? |
| 调用参数是否精确 | ? | ? |
| 返回结果是否混杂无关信息 | ? | ? |
| 回答是否完整有条理 | ? | ? |

3. 写结论：什么场景用粗粒度合适？什么场景用细粒度？

**预期结果**：表格填写完整，有基于实验数据的结论。

---

### Task 5：工具异常处理

**目标**：给工具增加异常处理，让 Agent 在工具失败时能自动调整策略。

**步骤**：

1. 给 `diagnose_device_fault` 增加异常处理：

```python
@tool(args_schema=FaultDiagnosisInput)
def diagnose_device_fault(device_id, symptom, severity="warning"):
    try:
        # ... 正常逻辑
        device = next((e for e in equipments if e["id"] == device_id), None)
        if not device:
            return json.dumps({
                "error": "device_not_found",
                "message": f"未找到编号为 {device_id} 的设备。请检查编号是否正确，或尝试用搜索功能确认设备编号。",
                "suggestion": "可以先用 search_equipment_by_type 查找同类型设备的编号",
            }, ensure_ascii=False)
        # ... 其余逻辑
    except Exception as e:
        return json.dumps({
            "error": "internal_error",
            "message": f"诊断过程出错：{str(e)}",
            "suggestion": "请重试或联系管理员",
        }, ensure_ascii=False)
```

2. 测试异常场景：
   - 传入一个不存在的设备编号（如 `EP-X-999`）
   - 观察 Agent 收到错误后的反应——它会尝试其他工具吗？还是直接报告给用户？

3. 关键设计点：
   - 错误信息要给出**明确的下一步建议**——不是"出错了"，而是"出错了，你可以尝试 XXX"
   - Agent 会读到错误信息并自行判断下一步

**预期结果**：Agent 能识别工具返回的错误信息，并尝试用其他方式完成任务。

---

## 📊 结果产出

| 产出 | 格式 | 位置 | 说明 |
|------|------|------|------|
| 两套完整工具代码 | `.py` | `demo/tool_calling_skeleton.py` | 粗粒度 2 个 + 细粒度 5 个工具 |
| 对比表格 | 文本 | Task 4 表格 | 两种粒度的多维度对比 |
| 异常处理验证 | 终端输出 | 终端 | Agent 在工具返回错误后的行为 |

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 | 检查 |
|------|--------|----------|------|
| 1 | **Pydantic 参数模型截图** | `FaultDiagnosisInput` 或 `InspectionFilter` 的定义 | ☐ |
| 2 | **粗粒度工具运行截图** | Agent 调用了粗粒度工具并回答问题 | ☐ |
| 3 | **细粒度工具调用链截图** | 一次查询触发了 ≥2 个细粒度工具的调用，参数可见 | ☐ |
| 4 | **对比表格** | Task 4 的表格填写完整 | ☐ |
| 5 | **异常处理截图** | 传入不存在的设备编号，Agent 正确处理了错误 | ☐ |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| Agent 不使用结构化参数 | `description` 写得太模糊 | 让 description 更具体，包含示例值 |
| 细粒度工具 Agent 只调了一个工具 | 任务太简单，Agent 判断一个工具就够 | 设计一个更复杂的多维度查询任务 |
| 粗粒度工具返回结果太长 | 工具把设备、知识库、记录全塞一块 | 控制每类结果的最大条数，或增加分页 |
| Agent 收到错误后直接放弃 | 错误信息的 suggestion 不够明确 | 在错误 JSON 中给出具体的备选工具名和参数示例 |
| `args_schema` 不生效 | 参数名不匹配 | schema 的字段名要和函数参数名完全一致 |

---

**🎉 恭喜完成实验！**
