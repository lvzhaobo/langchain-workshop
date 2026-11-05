# Lab 7.1 — 基础 LangChain Agent 搭建

> 用 @tool 定义工具，用 create_react_agent 创建 Agent，让它自主决定何时查数据、何时回答。

---

## 🎯 实验目标

1. 理解 LangChain Agent 的核心三要素：**LLM（大脑）+ Tool（手脚）+ Agent（决策循环）**
2. 用 `@tool` 装饰器把普通 Python 函数变成 Agent 可调用的工具
3. 用 `create_react_agent` 创建 Agent，观察 ReAct 循环（思考→调工具→观察→回答）
4. 对比"单次 LLM 调用"和"Agent 自主调工具"的行为差异

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | 设置环境变量 `DASHSCOPE_API_KEY` |
| 3 | 安装 LangChain | `pip install langchain langchain-openai langgraph` |
| 4 | 了解 Python 函数和 docstring | 能读写基本的 Python 函数 |

---

## 📦 实验数据

### 数据文件

| 文件路径 | 用途 | 说明 |
|----------|------|------|
| `demo/equipment_data.json` | 设备数据集 | 12 台电力设备，含变压器、断路器、输电线路等 6 种类型 |
| `demo/agent_skeleton.py` | 骨架代码 | 结构已写好，关键方法留空，需要你完成 |

### 背景信息

#### Agent 的"思考→行动→观察→再思考"循环

普通的 LLM 调用是**一问一答**——给它一个问题，它直接回答。但如果问题涉及外部数据（比如"1 号变压器最后一次巡检是谁做的？"），LLM 不知道答案，因为训练数据里没有。

LangChain Agent 的解决方式：给 LLM 配工具。当 LLM 遇到它不知道的信息时，它**自己决定调哪个工具**，拿到数据后再回答。

```
用户："1 号变压器最后一次巡检是谁做的？"

单次 LLM 调用：
  LLM → "抱歉，我没有这些数据。" ❌

Agent：
  LLM → 💭"我需要查设备数据" → 调 search_equipment("#1 主变压器")
      → 📥 拿到设备 JSON → LLM → "最后一次巡检是张工，在 2026-07-10" ✅
```

这个"思考→行动→观察→再思考"的循环就是 **ReAct 循环**，它是 LangChain Agent 的核心机制。

#### ReAct 循环的四个步骤

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ 思考     │ →   │ 行动     │ →   │ 观察     │ →   │ 再思考   │
│ (Think)  │     │ (Act)    │     │ (Observe)│     │ (Think)  │
│          │     │          │     │          │     │          │
│ AI判断： │     │ 调用工具  │     │ 收到结果  │     │ 信息够了？│
│ 我需要   │     │          │     │          │     │ 够了→回答│
│ 什么信息？│     │          │     │          │     │ 不够→再调│
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

#### 骨架代码结构

```
agent_skeleton.py
├── 配置区：百炼 API Key、模型名
├── load_equipment_data()               ← 数据层（已完成）
├── @tool search_equipment(keyword)     ← 工具定义（TODO）
├── build_agent()                       ← Agent 创建（TODO）
├── compare_llm_vs_agent()              ← 对比实验（TODO）
└── __main__                            ← 测试入口（按需取消注释）
```

#### 百炼 API 配置说明

百炼提供 OpenAI 兼容接口，LangChain 可以直接对接：

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="qwen-plus",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key="你的百炼 API Key",  # 或从环境变量读取
)
```

> 不需要额外安装 SDK。百炼的兼容接口支持 `/chat/completions` 端点，LangChain 的 `ChatOpenAI` 原生支持。

---

## 🔬 实验步骤

### Task 1：读懂骨架

**目标**：理解骨架代码的每个部分在 Agent 体系中的角色。

**步骤**：

1. 打开 `demo/agent_skeleton.py`，通读全部代码
2. 关注以下模块的职责：

```python
# 模块 1：数据层（已完成，不需要改）
def load_equipment_data():
    """从 JSON 文件加载 12 台电力设备数据"""
    
# 模块 2：工具定义（需要你写搜索逻辑）
@tool
def search_equipment(keyword: str) -> str:
    """搜索电力设备..."""

# 模块 3：Agent 创建（需要你写 LLM + Agent 组装）
def build_agent():
    """创建 LLM 实例 + 用 create_react_agent 组装"""

# 模块 4：对比实验（需要你写对比逻辑）
def compare_llm_vs_agent():
    """同一问题，LLM 直接回答 vs Agent 调工具后回答"""
```

3. 看 `equipment_data.json`，理解设备数据的结构：

```json
{
  "id": "EP-B-001",
  "name": "#1 主变压器",
  "type": "变压器",
  "region": "天河区",
  "voltage": "220kV",
  "status": "正常运行",
  "lastCheck": "2026-07-10",
  "checker": "张工"
}
```

4. 重点理解 `@tool` 装饰器的作用——它的 docstring 就是给 AI 看的"工具说明书"

**预期结果**：能用自己的话说明骨架代码的四个模块分别负责什么。

---

### Task 2：实现 `search_equipment` 工具

**目标**：完成第一个工具函数，让 Agent 能搜索设备。

**步骤**：

1. 在 `agent_skeleton.py` 中找到 `search_equipment` 函数
2. 将 `pass` 替换为搜索逻辑：

```python
@tool
def search_equipment(keyword: str) -> str:
    """搜索电力设备..."""
    # 1. 加载数据
    equipments = load_equipment_data()
    
    # 2. 模糊搜索（比对 name、id、type、region 四个字段）
    keyword_lower = keyword.lower()
    results = []
    for eq in equipments:
        if (keyword_lower in eq["name"].lower()
            or keyword_lower in eq["id"].lower()
            or keyword_lower in eq["type"].lower()
            or keyword_lower in eq["region"].lower()):
            results.append(eq)
    
    # 3. 格式化返回
    if not results:
        return f"未找到匹配 '{keyword}' 的设备"
    
    return json.dumps(results, ensure_ascii=False, indent=2)
```

3. **关键设计点**：
   - 工具函数的 docstring 决定了 AI 会不会用它——描述要准确说明功能
   - 返回类型建议用字符串（JSON 格式），不要返回 Python 字典——LLM 处理字符串最稳定
   - 搜索逻辑越简单越好——这个实验的重点是 Agent 框架，不是搜索算法

4. 取消 `__main__` 中对应注释，测试工具：

```bash
cd demo
python agent_skeleton.py
```

**预期结果**：`search_equipment.invoke("变压器")` 返回 4 条变压器数据，JSON 格式化清晰。

**验证通过标准**：
- `search_equipment.invoke("不存在的设备")` 返回 "未找到匹配..."
- `search_equipment.invoke("天河区")` 返回多条数据

---

### Task 3：创建 Agent 并观察 ReAct 循环

**目标**：用 `create_react_agent` 组装 Agent，观察它如何自主决策调用工具。

**步骤**：

1. 完成 `build_agent` 函数：

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

def build_agent():
    # 1. 创建 LLM 实例
    llm = ChatOpenAI(
        model=MODEL,
        base_url=BASE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0,  # 确定性输出，方便观察
    )
    
    # 2. 创建 Agent
    tools = [search_equipment]
    agent = create_react_agent(llm, tools)
    
    return agent
```

2. 写一段测试脚本（直接写在 `__main__` 中或另写测试）：

```python
agent = build_agent()

# 给 Agent 一个需要查数据的问题
question = "天河区有哪些设备？把它们的名称和状态列出来。"

result = agent.invoke({
    "messages": [{"role": "user", "content": question}]
})

# 打印 Agent 的完整回答
for msg in result["messages"]:
    if hasattr(msg, "content") and msg.content:
        print(f"[{msg.type}] {msg.content[:300]}")
```

3. 观察输出。你应该能看到 Agent 的执行过程：
   - `[tool]` — Agent 调用了 `search_equipment`
   - `[ai]` — Agent 拿到了搜索结果，开始组织回答

4. 试试不同类型的提问，观察 Agent 的行为：
   - "EP-D-002 的巡检人是谁？"
   - "有哪些设备状态异常？"
   - "今天天气怎么样？"（与设备无关——Agent 会不会也去调工具？）

**预期结果**：Agent 能自主判断是否需要调工具。设备问题 → 调 `search_equipment`；无关问题 → 直接回答（不调工具）。

**关键观察点**：
- Agent **不一定每问必调工具**——它自己判断
- 同一个问题，Agent 可能调一次工具，也可能调多次（比如搜索结果不够精确，再搜一次）

---

### Task 4：增加第二个工具

**目标**：给 Agent 增加一个 `get_equipment_detail` 工具，观察多工具场景下 Agent 的选择。

**步骤**：

1. 在 `agent_skeleton.py` 中新增第二个工具：

```python
@tool
def get_equipment_detail(device_id: str) -> str:
    """根据设备编号获取一台设备的完整信息，包括安装日期、制造商、容量、冷却方式。
    设备编号格式如 'EP-B-001'。

    参数:
        device_id: 设备编号
    """
    equipments = load_equipment_data()
    for eq in equipments:
        if eq["id"].upper() == device_id.upper():
            return json.dumps(eq, ensure_ascii=False, indent=2)
    return f"未找到编号为 '{device_id}' 的设备"
```

2. 把新工具加入 Agent 的工具列表：

```python
tools = [search_equipment, get_equipment_detail]  # 两个工具
```

3. 测试"需要两步才能回答"的问题：

```
"#1 主变压器的制造商是谁？"
```

这类问题 Agent 可能需要：先调 `search_equipment` 找到设备编号 → 拿到编号 → 调 `get_equipment_detail` 获取详细信息。

4. 观察 Agent 的调用链条。在终端记录：
   - Agent 调用了哪些工具？
   - 调用顺序是什么？
   - 总共调了几次工具？

**预期结果**：Agent 能根据问题选择不同的工具，甚至按顺序调用多个工具。

---

### Task 5：对比实验 — 单次 LLM vs Agent

**目标**：完成 `compare_llm_vs_agent` 函数，直观感受差异。

**步骤**：

1. 完成对比函数：

```python
def compare_llm_vs_agent():
    llm = ChatOpenAI(
        model=MODEL,
        base_url=BASE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0,
    )
    agent = build_agent()
    
    questions = [
        "天河区有哪些设备？",
        "EP-D-002 的当前状态和巡检人是谁？",
        "列出所有状态为'异常'的设备。",
    ]
    
    for q in questions:
        print(f"\n{'─'*50}")
        print(f"问题：{q}")
        
        # 方式 A：单次 LLM
        llm_result = llm.invoke(q)
        print(f"\n📝 单次 LLM：")
        print(f"   {llm_result.content[:200]}")
        
        # 方式 B：Agent
        agent_result = agent.invoke({
            "messages": [{"role": "user", "content": q}]
        })
        final_msg = agent_result["messages"][-1]
        print(f"\n🤖 Agent：")
        print(f"   {final_msg.content[:200]}")
```

2. 对比三个问题的两种回答方式：
   - 哪个给出了具体数据？
   - 哪个在编造或猜测？
   - Agent 多做了什么？

**预期结果**：单次 LLM 没有设备数据，只能编造或拒绝回答；Agent 通过调工具拿到了真实数据，回答准确。

---

## 📊 结果产出

| 产出 | 格式 | 位置 | 说明 |
|------|------|------|------|
| 完整 Agent 代码 | `.py` | `demo/agent_skeleton.py` | 两个工具 + Agent 均已实现 |
| 对比测试输出 | 终端文本 | 终端 | LLM vs Agent 三个问题的对比结果 |
| 多工具调用链记录 | 终端文本 | 终端 | Agent 在复杂问题上调用工具的顺序 |

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 | 检查 |
|------|--------|----------|------|
| 1 | **search_equipment 实现截图** | 源码 + `invoke("变压器")` 的搜索结果 | ☐ |
| 2 | **Agent 运行截图** | Agent 调用 `search_equipment` 并回答了设备相关问题 | ☐ |
| 3 | **多工具调用链截图** | 一个问题触发 ≥2 个工具调用，可以看到调用顺序 | ☐ |
| 4 | **LLM vs Agent 对比截图** | 同一个数据相关问题，LLM 编造 vs Agent 给出真实数据 | ☐ |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| `DASHSCOPE_API_KEY` 未设置 | 环境变量缺失 | `export DASHSCOPE_API_KEY=你的Key` 或写在 `.env` 文件中 |
| Agent 不调工具，直接回答 | 问题太简单（如"你好"），Agent 判断不需要工具 | 换一个涉及具体设备数据的问题 |
| Agent 调了工具但回答不准确 | 搜索结果为空或工具返回的 JSON 格式不易读 | 优化 `search_equipment` 的搜索逻辑，确保返回格式清晰的字符串 |
| `create_react_agent` 报错 | 版本不兼容 | `pip install langgraph --upgrade`，确保 langgraph >= 0.2.0 |
| 百炼 API 返回 401 | API Key 错误 | 检查 Key 是否正确，确认百炼控制台 Key 状态 |
| `json` 模块未导入 | skeleton 顶部缺少 `import json` | 在文件顶部添加 `import json` |

---

**🎉 恭喜完成实验！**
