# 🧠 多 Agent 协作 CheatSheet

> Lab 7.5b 速查 · Supervisor 模式 · 状态共享 · 工具分配

---

## 核心概念（3 句话）

```
1. 每个 Agent = 专属 System Prompt + 专属 Tool 集合 → 它是某个领域的"专家"
2. Supervisor = 一个 LLM 节点，读 State → 决定调谁 → Agent 回来 → 再决定
3. 所有 Agent 共享一份 TypedDict State，Agent A 写入 → Agent B 读取
```

---

## 三种编排模式速查

```
┌─────────────────┬────────────────────┬──────────────────────┐
│   ReAct Agent   │     StateGraph     │     Supervisor       │
│   (lab7.1)      │     (lab7.5)       │     (lab7.5b)        │
├─────────────────┼────────────────────┼──────────────────────┤
│ AI 自主决策     │ 编译时确定的路径     │ LLM 半动态调度       │
│ LLM → Tool → LLM│ R → D → S → E     │ S ⇄ A ⇄ S ⇄ B ⇄ S   │
│ 探索型任务      │ 固化流程型任务      │ 多专家协作型任务      │
└─────────────────┴────────────────────┴──────────────────────┘
```

---

## Supervisor 模式关键代码

```python
# 1. 共享状态
class MultiAgentState(TypedDict):
    diagnosis_result: Optional[str]  # Diagnosis 写入
    solution_plan: Optional[str]     # Solution 写入
    execution_record: Optional[str]  # Execute 写入
    next_agent: str                  # Supervisor 写入
    task_history: List[str]          # Supervisor 写入

# 2. 每个 Agent 只拿自己的工具
diagnosis_tools  = [search_equipment_by_id, search_knowledge_base]
solution_tools   = [generate_repair_plan, send_alert]
execute_tools    = [create_inspection_record, push_notification]

# 3. Supervisor 决策 → 路由
workflow.add_conditional_edges("supervisor", route_to_agent, {
    "diagnosis_agent": "diagnosis_agent",
    "solution_agent": "solution_agent",
    "execute_agent": "execute_agent",
    "FINISH": "summarize",
})

# 4. 每个 Agent 回到 Supervisor（核心差异！）
workflow.add_edge("diagnosis_agent", "supervisor")
workflow.add_edge("solution_agent", "supervisor")
workflow.add_edge("execute_agent", "supervisor")
```

---

## 状态共享：Agent 间怎么传数据

```
Diagnosis Agent 写入:
  state["diagnosis_result"] = "分闸线圈电阻异常"
  state["severity"]         = "critical"
         │
         ▼ 回到 Supervisor → Supervisor 决定调 Solution Agent
         │
         ▼
Solution Agent 读取:
  diag = state["diagnosis_result"]   # ✅ "分闸线圈电阻异常"
  sev  = state["severity"]           # ✅ "critical"
  → 生成紧急处置方案（不需要重新诊断！）
```

**关键原则**：用 JSON 字段传递，不用自然语言。`diagnosis_result` 是字符串字段，不是"把诊断结论写成一段话塞给下一个 Agent"。

---

## Agent 设计检查清单

```
□ 每个 Agent 的 System Prompt 是否明确说了"你只负责 XXX"？
□ 每个 Agent 的工具列表是否只包含它职责范围内的工具？
□ Agent A 写入的 State 字段，Agent B 的 System Prompt 是否指引了"从 State 中读取"？
□ Supervisor 的调度逻辑是否考虑了"某个 Agent 失败时怎么办"？
□ task_history 是否在每次 Agent 执行时更新？
```

---

## 常见错误速查

| 错误现象 | 根因 | 修复 |
|----------|------|------|
| Supervisor 无限循环 | Agent 回到 Supervisor 后 task_history 没更新 | Agent 函数第一行加 `state["task_history"].append("xxx")` |
| 两个 Agent 给出矛盾结论 | 数据用自然语言传递，被 LLM 改写 | 用结构化字段，不用自然语言串联 |
| Agent 用了不该用的工具 | 工具列表没按 Agent 隔离 | 每个 Agent 只传自己的 `tools` 列表 |
| Solution Agent 重新诊断 | System Prompt 没告诉它"直接读诊断结论" | Prompt 中写："你不需要重新诊断，使用已有的 diagnosis_result" |

---

## 何时用哪种模式

```
任务有确定的1→2→3→4步骤？
  → 用 lab7.5 StateGraph（简单直接）

任务需要多个专家各司其职、灵活调度？
  → 用 lab7.5b Supervisor（本实验）

任务完全开放、不知道需要几步？
  → 用 lab7.1 ReAct Agent（自由探索）
```
