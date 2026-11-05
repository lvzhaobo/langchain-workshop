# Agent 模式 / LangGraph vs LangChain / State 设计

> 从 sample-5/6 延伸出的概念辨析

---

## 一、Agent 模式全集

| 模式 | 全称 | 核心思路 | 适合场景 |
|------|------|---------|---------|
| ReAct | Reasoning + Acting | Think → Act → Observe 循环 | 需要查资料、调工具的问答 |
| Plan-and-Execute | 先计划后执行 | 先列步骤清单 → 逐步执行 | 复杂多步骤任务 |
| ReWOO | Reason Without Observation | 一次性规划工具调用 → 批量执行 | 工具互不依赖 |
| Reflection | 自我反思 | 执行 → 自我批评 → 改进 → 再执行 | 写作、代码生成 |
| LLMCompiler | 并行编译 | DAG 编排工具调用依赖 | 工具间有依赖关系 |
| Multi-Agent | 多智能体协作 | 多个 Agent 分工 | 大型复杂系统 |

### ReAct vs Plan-Execute 执行对比

```
ReAct：              LLM→Tool→LLM→Tool→LLM→Answer   （一步一步）
Plan-Execute：       Plan→[Step1,Step2,Step3]→Check   （先列计划）
ReWOO：              Plan→[Tool1∥Tool2∥Tool3]→Answer  （并行调）
Reflection：         Write→SelfReview→Rewrite→Done     （写→批→改）
```

---

## 二、LangGraph 和 LangChain 关系

### 2.1 层级关系

```
LangChain 高层 API
  create_react_agent()  一行搞定
  create_tool_calling_agent()
        │ 底层调用
        ▼
LangGraph
  StateGraph + Nodes + Edges
  Checkpoint / Stream / Interrupt
        │ 模型调用
        ▼
LangChain Core
  ChatModel / Tool / Message 抽象
```

### 2.2 LangChain 预置 Agent 对应

| LangChain API | 模式 | 本质 |
|---|---|---|
| create_react_agent | ReAct | LangGraph 图 |
| create_tool_calling_agent | Tool Calling | LangGraph 图 |
| create_structured_chat_agent | 结构化对话 | LangGraph 图 |

### 2.3 LangChain 为什么写不了 Agent 循环

1. **Chain 只有单向链表**：A → B → C，不能循环
2. **没有共享 State**：上一步输出 = 下一步输入，无法跨步共享状态
3. **AgentExecutor 用 while 循环硬跑**：黑盒，不可中断、不可恢复

### 2.4 状态管理对比

| | LangChain | LangGraph |
|---|-----------|-----------|
| 状态存哪 | 函数参数 / while 临时变量 | State + Checkpoint |
| 跨步可见 | ❌ | ✅ |
| 暂停恢复 | ❌ | ✅ |
| 跨会话 | ❌ | ✅ thread_id |
| 多节点写同一字段 | ❌ 覆盖 | ✅ reducer 自动合并 |

### 2.5 时间线

```
2022.10  LangChain 发布（Chain 线性串联）
2023     爆火，Agent 循环问题暴露
2024.01  LangGraph 发布（图执行模型）
2024-25  LangGraph 逐渐独立，无需完整 langchain 包
```

现在只需 `langgraph` + `langchain-core`。

---

## 三、State 设计

### 3.1 State 里存什么

State = 图上所有节点共享的"工作台"。常见分类：

| 类别 | 字段示例 | reducer |
|------|---------|---------|
| 消息 | `messages` | `add_messages` |
| 进度 | `current_step`, `remaining_retries` | 覆盖 |
| 数据收集 | `collected_data`, `found_issues` | `operator.add` |
| 标志 | `need_escalate`, `is_complete` | `operator.or_` |
| 业务 | `device_ip`, `alarm_list` | 覆盖 |

### 3.2 Reducer 全集

#### operator 内置

| reducer | 效果 | 适合 |
|---------|------|------|
| `operator.add` | 累加 / 列表拼接 | 计数、汇总 |
| `operator.mul` | 累乘 | 概率 |
| `operator.or_` | 逻辑或 | 开关标志 |
| `operator.and_` | 逻辑与 | 全部满足 |

#### LangGraph 内置

| reducer | 效果 |
|---------|------|
| `add_messages` | 消息追加 + 同名 ToolMessage 替换 |

#### 自定义模板

```python
def reducer(left, right):   # 旧值, 新写入
    return 合并结果

def keep_max(left, right):      return max(left, right)
def keep_unique(left, right):   return list(set(left + right))
def merge_dict(left, right):    return {**left, **right}
```

### 3.3 State 更新机制

- 唯一途径：节点 `return` dict
- `return {}` → 不改任何东西
- `return {"key": val}` → 只改这个 key
- 是部分更新，不是全量覆盖

### 3.4 State 更新时机

节点 `return` 的那一刻。LangGraph 在每个 Superstep 结束时批量合并。

### 3.5 State 存储与丢失

| | 不加 checkpointer | 加 MemorySaver | 加 SqliteSaver |
|---|---------|-------------|------|
| invoke 期间 | ✅ | ✅ | ✅ |
| invoke 结束后 | ❌ | ❌ 重启丢 | ✅ 持久化 |
| 断点续跑 | ❌ | ✅ 同进程 | ✅ 跨进程 |

---

## 四、config 详解

### 4.1 graph.invoke 签名

```python
graph.invoke(input, config=None, *, interrupt_before=None, interrupt_after=None, debug=False)
```

### 4.2 configurable 配置

| 配置 | 类型 | 作用 |
|------|------|------|
| `thread_id` | `str` | checkpoint 隔离 key |
| `checkpoint_id` | `str` | 指定历史快照恢复 |
| `checkpoint_ns` | `str` | 子图命名空间 |

### 4.3 config 完整结构

```python
{
    "configurable": {"thread_id": "...", "checkpoint_id": "...", "checkpoint_ns": "..."},
    "tags": ["prod"],
    "metadata": {"user_id": "zhangsan"}
}
```

### 4.4 thread_id 隔离

MemorySaver 内部用 thread_id 做二层 dict 的 key，不同 thread 读不到对方数据，天然隔离。

### 4.5 thread_id 自定义

可以是任意字符串：`"a-01"`、`"user-zhangsan-conv-42"`、`"2026-07-25-望京SOHO"`，只要能区分不同对话即可。

### 4.6 checkpoint_id 生成

MemorySaver 每次 `put()` 时自动 `uuid.uuid4()` 生成，不需要你管。除非做时间旅行——特指回退到某个历史快照。

---

## 五、MemorySaver 详解

### 5.1 本质

一个大 dict：`{thread_id: [CheckpointTuple列表]}`

### 5.2 存的内容

每个 CheckpointTuple 包含：

- `config`：thread_id + checkpoint_id
- `checkpoint`：`{"channel_values": State完整快照}`
- `metadata`：step序号、source来源、parents上游

### 5.3 put/get 控制

- put：PregelRunner 在每波 Superstep 结束后自动调
- get：invoke 开始时自动检查是否有历史
- 不是手动调的

### 5.4 存的不是节点函数、不是图结构，是 State 快照

---

## 六、Command 动态路由

### 6.1 和 add_conditional_edges 的区别

| | add_conditional_edges | Command |
|---|---------------------|---------|
| 路由逻辑在哪 | 节点外的独立函数 | 节点内的 return |
| 维护 | 改节点要同步改路由 | 改一处就行 |
| 适合 | 多个节点共用同一路由 | 每个节点自己决定去向 |

### 6.2 用法

```python
def diagnose(state):
    if state["severity"] == "P0":
        return Command(goto="escalate", update={"need_escalate": True})
    return Command(goto="auto_fix")
```
