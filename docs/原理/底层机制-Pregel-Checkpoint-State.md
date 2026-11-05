# LangGraph 底层机制：Pregel · Checkpoint · State

> 从 sample-7/8 引申出的深度问答

---

## 一、Pregel 执行模型

### 1.1 来源

Google 2010 年论文《Pregel: A System for Large-Scale Graph Processing》。LangGraph 借了 Superstep 概念。

### 1.2 在 LangGraph 中的实现

三个核心文件：

```
langgraph/pregel/
├── _loop.py      # PregelLoop：主循环，控制 Superstep 节奏
├── _runner.py    # PregelRunner：执行单个 Superstep 内的节点
└── _algo.py      # apply_writes：Superstep 结束后合并 State
```

### 1.3 执行流程（简化版）

```python
class PregelLoop:
    def run(self):
        # ① 从 checkpoint 恢复，或从 input 初始化
        saved = self.checkpointer.get_tuple(config)
        if saved:
            self._restore(saved)
        else:
            self._apply_input(input)
        
        # ② 主循环：直到没有待办任务
        while self.tasks:
            superstep_tasks = self._tick()           # 取出一波可并发的节点
            PregelRunner.run(superstep_tasks)        # 并发执行
            self.after_tick()                        # 合并 State
            self.checkpointer.put(config, snapshot)  # 自动存档
        
        return self.channels.read()
```

### 1.4 LangChain 没有 Superstep

| | LangChain AgentExecutor | LangGraph Pregel |
|---|------------------------|-----------------|
| 执行方式 | while 循环（黑盒） | Superstep 批次（透明） |
| 每步存档 | ❌ | ✅ |
| 可中断 | ❌ | ✅ interrupt() |

---

## 二、Superstep 定义

### 2.1 怎么划分

`compile()` 时根据 edge 拓扑，把无依赖的节点打包成一个 Superstep：

```
START → A → B → C → END     → [A] [B] [C]     3 个 Superstep
START → A → {B, C} → D      → [A] [B∥C] [D]    3 个 Superstep
```

### 2.2 和 edge/state 的关系

- **edge** 决定依赖关系 → 决定哪些节点打包
- **node** 在 Superstep 内并发执行
- **state** 在 Superstep 结束时批量合并（调 reducer）

---

## 三、Checkpoint 存储机制

### 3.1 MemorySaver 本质

```python
class MemorySaver:
    def __init__(self):
        self._saves = {}  # {thread_id: [CheckpointTuple, ...]}
    
    def put(self, config, checkpoint, ...):
        thread_id = config["configurable"]["thread_id"]
        self._saves[thread_id].append(CheckpointTuple(...))
    
    def get_tuple(self, config):
        return self._saves[thread_id][-1]  # 返回最新的
```

### 3.2 存的格式

```python
MemorySaver._saves = {
    "session-abc": [
        CheckpointTuple(
            config={"configurable": {"thread_id": "session-abc", "checkpoint_id": "uuid-0"}},
            checkpoint={"channel_values": {"device_name": "SW01", "step": 0, ...}},
            metadata={"step": 0, "source": "input"},
        ),
        # ... 后续 Superstep 的快照
    ]
}
```

### 3.3 生命周期

```
compile(checkpointer=MEM)     MEM = {}（空）
invoke(input, thread_a)       MEM["session-abc"] = [cp0, cp1, cp2, cp3]
invoke(None, thread_a)        接着追加 cp4, cp5
invoke(input2, thread_b)      MEM["session-xyz"] = [cp0, cp1]
进程结束                        MEM 消失（只存在内存）
```

### 3.4 thread_id 隔离

两层 dict 结构天然隔离：

```python
self._saves = {
    "thread-a": [...],   # ← key 不同
    "thread-b": [...],   # ← 完全独立
}
```

invoke 时只查自己 thread_id 对应的链，看不到其他 thread 的数据。

### 3.5 谁控制 put/get

**PregelRunner 自动控制，不是用户代码：**

- put：每个 Superstep 结束后，`loop.after_tick()` 自动调
- get：`invoke()` 开始时，查是否有历史 checkpoint

---

## 四、State Channel

### 4.1 Channel 是什么

State 里的每个 key，LangGraph 内部分配一个 Channel 对象来管理这个 key 的值：

```python
class State(TypedDict):
    score: int                           # → LastValue channel
    total: Annotated[int, operator.add]  # → BinaryOperatorAggregate channel
```

### 4.2 Channel 类型

| Channel 类型 | 对应 State 写法 | 行为 |
|-------------|---------------|------|
| LastValue | `int` / `str` / 裸类型 | 后者覆盖前者 |
| BinaryOperatorAggregate | `Annotated[T, func]` | 用 func 合并新旧值 |
| Ephemeral（临时） | — | 值不跨 Superstep 持久化 |

### 4.3 Channel 做的事

```python
class LastValue:
    def update(self, values):
        self.value = values[-1]  # 取最后一个写入的值

class BinaryOperatorAggregate:
    def update(self, values):
        for v in values:
            self.value = self.reducer(self.value, v)  # 逐个合并
```

---

## 五、checkpoint 恢复

### 5.1 完全自动

```python
# 你写的代码：只需要传同一个 config
graph.invoke(input, {"configurable": {"thread_id": "session-abc"}})  # 第一次
graph.invoke(None,  {"configurable": {"thread_id": "session-abc"}})  # 第二次 ← 自动恢复
```

### 5.2 内部恢复流程

```python
# LangGraph 内部（PregelLoop.run）
def run(self):
    saved = self.checkpointer.get_tuple(config)
    if saved:
        # 从 checkpoint 恢复：State 回到上次存档的值，从未完成的节点继续
        self._restore(saved)
    else:
        # 新对话：用 input 初始化 State，从 START 开始
        self._apply_input(input)
```

### 5.3 你不需要手动恢复

你只要传同一个 thread_id，`invoke()` 内部自动走 `_restore()` 分支。`get_state()`、`list()` 这些也是读操作，不影响执行流程。

---

## 六、builder / graph / compile 关系

```
builder = StateGraph(State)   # 蓝图/设计图，不能跑
graph = builder.compile(...)  # 编译产物/可运行实例（CompiledStateGraph）
graph.invoke(...)             # 跑图
```

- `builder`：`StateGraph` 类的实例，你调 `add_node`/`add_edge` 画图
- `compile()`：验证拓扑、生成 Pregel 执行计划，返回可执行对象
- `graph`：`CompiledStateGraph` 实例，LangGraph 管它叫"编译后的图"
- 它不是"Agent"——Agent 是概念，CompiledStateGraph 是执行引擎

### compile 执行时机

只执行一次。在代码启动时运行，不在每次 invoke 时运行。

```python
graph = builder.compile()  # ← 编译一次
graph.invoke(...)          # 不编译，直接跑 Pregel 循环
graph.invoke(...)          # 不编译，直接跑
```

---

## 七、config 参数

### 7.1 configurable 支持的配置

| 配置项 | 类型 | 作用 |
|--------|------|------|
| `thread_id` | `str` | Checkpoint 隔离 key |
| `checkpoint_id` | `str` | 指定从哪个历史快照恢复 |
| `checkpoint_ns` | `str` | 子图命名空间隔离 |

### 7.2 config 完整结构

```python
config = {
    "configurable": {          # 影响 checkpoint 行为
        "thread_id": "session-abc",
        "checkpoint_id": "...",
    },
    "tags": ["prod"],          # LangSmith / 监控用
    "metadata": {"user": "张三"},  # 自定义信息
}
```

### 7.3 graph.invoke 完整签名

```python
graph.invoke(
    input,                 # 初始 State 或 None（从 checkpoint 恢复）
    config=None,           # checkpoint 配置
    *,
    interrupt_before=None, # 运行时覆盖：在指定节点前暂停
    interrupt_after=None,  # 运行时覆盖：在指定节点后暂停
    debug=False,           # 打印详细执行过程
)
```
