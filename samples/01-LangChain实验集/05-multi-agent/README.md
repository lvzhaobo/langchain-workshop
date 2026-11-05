# 实验五：Supervisor 多 Agent 协作

> 三个专家 Agent + Supervisor 调度中心，共享状态协同完成故障诊断

## 运行

```bash
python multi_agent.py              # 在线模式（需要百炼 API）
python multi_agent.py --offline    # 离线模式（纯本地）
```

## 核心概念

### State 是什么？由谁设置？

State 是你自己用 Python `TypedDict` 定义的字典结构，不是 LangChain 预设的：

```python
class MultiAgentState(TypedDict):
    diagnosis_result: Optional[str]    # Diagnosis Agent 写入
    solution_plan: Optional[str]       # Solution Agent 写入
    execution_record: Optional[str]    # Execute Agent 写入
    next_action: str                   # Supervisor 写入，路由函数读取
    task_history: list                 # 每个 Agent 追加
```

创建 StateGraph 时传入这个结构 → 每个节点返回部分字段 → LangGraph 自动合并到同一个字典。

### Supervisor 检查哪三个字段决定路由？

`diagnosis_result`、`solution_plan`、`execution_record`。

| state 快照 | Supervisor 决策 |
|-----------|----------------|
| 三个全为空 | 路由到 Diagnosis Agent |
| diagnosis_result 有值，solution_plan 为空 | 路由到 Solution Agent |
| 前两个有值，execution_record 为空 | 路由到 Execute Agent |
| 三个全有值 | FINISH，输出汇总报告 |

### 多个 Agent 怎么读同一个 Agent 的输出？

Diagnosis Agent 写了 `diagnosis_result`。读它的有两个：
- **Solution Agent** — 用诊断结论生成维修方案
- **Execute Agent** — 用诊断结论生成巡检记录

同一个字段，两个下游各自消费。

Execute Agent 还同时读了 Solution Agent 的 `solution_plan`——所以 Execute 既是一对多读取的参与者，也是多对一聚合的节点。

## 多智能体共享状态的五种方式

| 方式 | 原理 | 本实验中的例子 |
|------|------|-------------|
| StateGraph 共享 State | 所有节点读写同一个 TypedDict，LangGraph 自动合并 | Diagnosis → Solution → Execute |
| 多个 Agent 读同一个 Agent 的输出 | Diagnosis 写入 → Solution 和 Execute 都读取 | `diagnosis_result` 被两个下游消费 |
| Supervisor 路由调度 | 中央调度器检查 state 字段 → 决定下一步 | Supervisor 检查三个字段决定路由 |
| Tool Call 消息传递 | 工具返回值追加到 messages，LLM 从对话历史中读取 | 01-agent-basic 的 ReAct 循环 |
| 外部存储 / MCP | Agent 通过 MCP 读写 JSON/数据库，跨会话持久化 | Sample 2 后端多个 API 端点共享 devices.json |

## 可视化

打开 `state_flow.html` 查看完整的状态流转图、Agent 读写矩阵和时序流程。
