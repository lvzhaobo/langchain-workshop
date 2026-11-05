# LangChain 核心概念详解

## 一、LangChain 是什么？

LangChain 是一个用于开发大模型应用的框架，它解决了从"大模型API"到"生产级应用"之间的鸿沟。

### 解决的核心痛点
- **如何连接**：如何让大模型与外部数据源、API、工具连接？
- **如何编排**：如何组织复杂的调用流程？
- **如何记忆**：如何让模型"记住"上下文？
- **如何调试**：如何追踪和监控应用的执行过程？

---

## 二、核心概念：Chain 编排

### 什么是 Chain？

Chain 是 LangChain 中最基本的编排单元，它将多个组件串联起来，形成一个完整的处理流程。

```python
# 传统方式：手动调用
response1 = model.invoke("翻译这句话")
response2 = model.invoke(f"总结: {response1}")
response3 = model.invoke(f"润色: {response2}")

# Chain 方式：自动编排
chain = (
    {"text": RunnablePassthrough()} 
    | prompt_template 
    | model 
    | output_parser
)
result = chain.invoke("翻译这句话")
```

### Chain 的核心优势

| 特性 | 传统方式 | Chain 方式 |
|------|---------|-----------|
| 可读性 | 低，逻辑分散 | 高，流水线清晰 |
| 可复用性 | 差 | 好，组件可组合 |
| 可调试性 | 难 | 易，内置追踪 |
| 可扩展性 | 难 | 易，灵活组合 |

### 常见 Chain 类型

#### 1. LLMChain（最基础的链）
```python
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAI

llm = OpenAI(temperature=0.7)
prompt = PromptTemplate(
    input_variables=["product"],
    template="为公司{product}写一句广告语"
)

chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run("智能手表")
```

#### 2. Sequential Chain（顺序链）
```python
from langchain.chains import SequentialChain

# 第一步：翻译
chain1 = LLMChain(llm=llm, prompt=prompt1, output_key="translation")

# 第二步：总结
chain2 = LLMChain(llm=llm, prompt=prompt2, output_key="summary")

# 组合
overall_chain = SequentialChain(
    chains=[chain1, chain2],
    input_variables=["text"],
    output_variables=["translation", "summary"]
)
```

#### 3. Runnable 接口（推荐的新方式）
```python
from langchain.schema.runnable import RunnablePassthrough, RunnableParallel

# 链式组合
chain = {
    "context": retriever,
    "question": RunnablePassthrough()
} | prompt | model | output_parser

# 并行处理
parallel_chain = RunnableParallel(
    summary=summarize_chain,
    keywords=keyword_chain,
    sentiment=sentiment_chain
)
```

---

## 三、核心概念：Agent 调度

### 什么是 Agent？

Agent 是一个能够**自主决策**的系统，它会根据用户的输入，动态选择要使用的工具，并决定下一步行动。

### Agent vs Chain 的区别

```
Chain：固定流程，像流水线
用户输入 → 步骤1 → 步骤2 → 步骤3 → 输出

Agent：动态决策，像智能助手
用户输入 → 思考 → 选择工具 → 执行 → 观察 → 再思考... → 输出
```

### Agent 的核心组件

```
┌─────────────────────────────────────┐
│              Agent                   │
│  ┌───────────────────────────────┐ │
│  │         LLM (大脑)             │ │
│  │   - 理解用户意图               │ │
│  │   - 决策下一步行动             │ │
│  └───────────────────────────────┘ │
│                ↓                    │
│  ┌───────────────────────────────┐ │
│  │      Tools (工具箱)            │ │
│  │   - 搜索工具                   │ │
│  │   - 计算器                     │ │
│  │   - 数据库查询                 │ │
│  │   - API调用                    │ │
│  └───────────────────────────────┘ │
│                ↓                    │
│  ┌───────────────────────────────┐ │
│  │    AgentExecutor (执行器)      │ │
│  │   - 协调执行                   │ │
│  │   - 管理状态                   │ │
│  └───────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Agent 实战示例

```python
from langchain.agents import initialize_agent, Tool
from langchain_openai import OpenAI

# 定义工具
tools = [
    Tool(
        name="搜索",
        func=search_tool,
        description="用于搜索最新信息"
    ),
    Tool(
        name="计算器",
        func=calculator,
        description="用于数学计算"
    )
]

# 创建 Agent
llm = OpenAI(temperature=0)
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="zero-shot-react-description",
    verbose=True  # 显示思考过程
)

# 运行
agent.run("北京今天的天气温度是多少？如果比上海高5度，那么上海多少度？")
```

### Agent 的决策流程

```python
# Agent 的 ReAct 模式
Thought: 用户想知道北京和上海的温差
Action: 搜索
Action Input: 北京今天天气温度
Observation: 北京今天25度
Thought: 现在我知道了北京的温度
Action: 搜索
Action Input: 上海今天天气温度
Observation: 上海今天20度
Thought: 我知道答案了
Final Answer: 北京今天25度，上海今天20度，北京比上海高5度
```

---

## 四、核心概念：Tool 调用

### 什么是 Tool？

Tool 是 Agent 可以调用的外部能力单元，它封装了具体的功能实现。

### Tool 的三要素

1. **名称**：工具的唯一标识
2. **描述**：告诉 LLM 何时使用此工具
3. **执行函数**：实际的执行逻辑

### 创建自定义 Tool

```python
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field

# 方式一：使用装饰器
from langchain.tools import tool

@tool
def get_word_length(word: str) -> int:
    """返回单词的长度"""
    return len(word)

# 方式二：继承 BaseTool
class CalculatorInput(BaseModel):
    a: int = Field(description="第一个数字")
    b: int = Field(description="第二个数字")

class CalculatorTool(BaseTool):
    name = "calculator"
    description = "用于计算两个数的加减乘除"
    args_schema: Type[BaseModel] = CalculatorInput
    
    def _run(self, a: int, b: int):
        return {
            "加": a + b,
            "减": a - b,
            "乘": a * b,
            "除": a / b if b != 0 else "错误：除数不能为0"
        }
```

### 内置常用 Tools

| Tool 类型 | 功能 | 使用场景 |
|----------|------|---------|
| `PythonREPLTool` | 执行 Python 代码 | 数据分析、计算 |
| `SerpAPIWrapper` | 搜索引擎搜索 | 获取最新信息 |
| `WikipediaQueryRun` | 维基百科查询 | 知识问答 |
| `SQLDatabaseChain` | 数据库查询 | 数据分析 |
| `RequestsGetTool` | HTTP 请求 | API 调用 |

### Tool 调用流程

```python
from langchain.tools.render import render_text_description

# 1. 定义工具列表
tools = [search_tool, calculator_tool, weather_tool]

# 2. 生成工具描述（给 LLM 看）
tools_description = render_text_description(tools)

# 3. LLM 根据用户输入选择工具
prompt = f"""
你是一个智能助手，可以使用以下工具：
{tools_description}

用户问题：{user_input}
请选择合适的工具并执行。
"""

# 4. 执行工具并返回结果
action = llm.predict(prompt)
if action.tool == "search":
    result = search_tool.run(action.input)
```

---

## 五、三大概念的关系

```
┌─────────────────────────────────────────────┐
│              应用架构层级                    │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │         Agent (调度层)                 │ │
│  │  - 自主决策                            │ │
│  │  - 动态选择工具                        │ │
│  │  - 多轮推理                            │ │
│  └───────────────────────────────────────┘ │
│                    ↓ 调用                   │
│  ┌───────────────────────────────────────┐ │
│  │         Chain (编排层)                 │ │
│  │  - 流程编排                            │ │
│  │  - 数据流转                            │ │
│  │  - 组件组合                            │ │
│  └───────────────────────────────────────┘ │
│                    ↓ 使用                   │
│  ┌───────────────────────────────────────┐ │
│  │         Tool (能力层)                  │ │
│  │  - 搜索能力                            │ │
│  │  - 计算能力                            │ │
│  │  - 数据访问能力                        │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

---

## 六、实战最佳实践

### 1. 何时使用 Chain？
- ✅ 流程固定、可预测
- ✅ 步骤明确，无分支
- ✅ 性能要求高

### 2. 何时使用 Agent？
- ✅ 需要动态决策
- ✅ 工具选择不确定
- ✅ 任务复杂多变

### 3. 何时组合使用？
```python
# 示例：Agent 调用多个 Chain
from langchain.agents import AgentExecutor

# 定义多个 Chain
translation_chain = ...
summary_chain = ...

# Agent 根据用户意图选择 Chain
def route_chain(query):
    if "翻译" in query:
        return translation_chain
    elif "总结" in query:
        return summary_chain
```

---

## 七、关键要点总结

| 概念 | 核心作用 | 关键特性 | 适用场景 |
|------|---------|---------|---------|
| **Chain** | 流程编排 | 固定流程、组件组合 | 明确的任务流程 |
| **Agent** | 智能调度 | 动态决策、自主执行 | 复杂、不确定的任务 |
| **Tool** | 能力扩展 | 功能封装、即插即用 | 需要外部能力 |

---

## 八、延伸学习

- [LangChain 官方文档](https://python.langchain.com/)
- [LangChain Expression Language (LCEL)](https://python.langchain.com/docs/expression_language/)
- [Agent Types 深入理解](https://python.langchain.com/docs/modules/agents/agent_types/)