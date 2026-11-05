# Lab 7.6 — Human in the Loop

> 在 LangGraph 工作流中插入人工审批节点——Graph 跑到一半暂停，飞书发卡片，运维人员点按钮，Graph 继续或回退。

---

## 🎯 实验目标

1. 理解 `interrupt_before` 机制：在图编译时指定哪些节点执行前需要暂停
2. 实现审批循环：展示结果 → 等待审批 → `Command(resume=True)` 继续或 `update_state` 回退
3. 对接飞书：把审批从"终端输入"升级为"飞书卡片消息"
4. 理解 Checkpointer（检查点）的作用：暂停时保存状态，恢复时加载状态

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | LLM 调用需要 |
| 3 | 完成 Lab 7.5 | 有可运行的 StateGraph |
| 4 | 飞书 Webhook URL（选做） | 飞书审批需要 |

---

## 📦 实验数据

| 文件路径 | 用途 | 说明 |
|----------|------|------|
| `demo/langgraph_skeleton.py` | 基础图 | Lab 7.5 已实现的 4 节点工作流 |
| `demo/hitl_skeleton.py` | HITL 骨架 | interrupt + 审批循环框架 |

### 背景信息

#### HITL 在 LangGraph 中的实现方式

LangGraph 的 `interrupt_before` 让你在指定节点**执行前**暂停。暂停后，你可以检查当前状态，决定是继续还是修改。

```
正常流程：
  Router → Diagnosis → Solution → Execute → END

加入 HITL（在 Solution 前暂停）：
  Router → Diagnosis → ⏸️ 暂停 → 人审批 → Solution → Execute → END
                              ↓
                         展示诊断结论
                         人工判断：
                           [批准] → 继续 Solution
                           [驳回] → 修改状态 → 回到 Diagnosis
```

#### 两个关键概念

**Checkpointer（检查点）**：暂停时把当前 state 存下来。没有它，暂停后状态就丢了。

**Command（指令）**：恢复执行的方式。`Command(resume=True)` 表示"从暂停点继续"，`graph.update_state(config, new_values)` 表示"修改状态后再继续"。

#### 审批通道设计

实验提供两种审批方式：
1. **终端交互**（必做）：`input("[a]批准 / [r]驳回")` — 快速验证流程
2. **飞书卡片**（选做）：POST 到飞书 Webhook，发一张审批卡片，运维人员在飞书里点按钮

---

## 🔬 实验步骤

### Task 1：给图加 interrupt_before + Checkpointer

**目标**：改造 lab7.5 的图，在 solution 节点前加暂停点。

**步骤**：

1. 在 `build_graph` 的 `compile()` 调用中加两个参数：

```python
from langgraph.checkpoint.memory import MemorySaver

graph = workflow.compile(
    interrupt_before=["solution"],  # solution 节点执行前暂停
    checkpointer=MemorySaver(),     # 保存状态到内存
)
```

2. 运行一次——观察到图在 solution 节点前停下来：

```python
config = {"configurable": {"thread_id": "test-001"}}

for event in graph.stream(
    {"user_query": "EP-D-002 断路器拒分", "messages": []},
    config,
):
    for node_name, node_output in event.items():
        print(f"节点 [{node_name}] 完成")
        # 到 solution 时会停止，不会打印 solution

# 检查暂停状态
state = graph.get_state(config)
print(f"下一个节点: {state.next}")  # 应该是 ('solution',)
print(f"当前诊断结论: {state.values.get('diagnosis_result', 'N/A')}")
```

**预期结果**：`state.next` 显示 `('solution',)`，表示图在 solution 前等待。

---

### Task 2：实现终端审批循环

**目标**：暂停后，在终端展示诊断结果，等待人工输入 a（批准）或 r（驳回）。

**步骤**：

1. 实现审批逻辑：

```python
def hitl_approval_loop(graph, user_query, thread_id):
    config = {"configurable": {"thread_id": thread_id}}
    
    # 第一阶段：跑到暂停点
    print(f"\n🤖 开始执行...")
    for event in graph.stream(
        {"user_query": user_query, "messages": []},
        config,
    ):
        for node_name, node_output in event.items():
            print(f"  节点 [{node_name}] 完成")
    
    # 检查暂停状态
    state = graph.get_state(config)
    if not state.next:
        print("图已执行完毕，无需审批")
        return
    
    # 展示待审批内容
    print(f"\n{'='*50}")
    print(f"⏸️  等待审批 | 线程: {thread_id}")
    print(f"   设备: {state.values.get('device_id', 'N/A')}")
    print(f"   诊断结论: {state.values.get('diagnosis_result', 'N/A')}")
    print(f"   严重程度: {state.values.get('severity', 'N/A')}")
    
    choice = input("\n[a] 批准 — 继续生成方案\n[r] 驳回 — 回到诊断\n> ").strip().lower()
    
    if choice == "a":
        print("✅ 批准！继续执行...")
        for event in graph.stream(Command(resume=True), config):
            for node_name, node_output in event.items():
                print(f"  节点 [{node_name}] 完成")
    
    elif choice == "r":
        reason = input("驳回理由（可选）：")
        print(f"↩️ 驳回。理由: {reason or '未填写'}")
        # 修改状态，回退到 diagnosis 重新诊断
        graph.update_state(config, {
            "diagnosis_result": None,
            "severity": None,
            "messages": state.values["messages"] + [
                f"[HITL] 驳回，原因: {reason or '审批人未提供原因'}",
            ],
        })
        # 继续执行——会重新走 diagnosis → solution
        for event in graph.stream(Command(resume=True), config):
            for node_name, node_output in event.items():
                print(f"  节点 [{node_name}] 完成")
    
    # 输出最终状态
    final_state = graph.get_state(config)
    print(f"\n📋 最终结果:")
    print(f"   方案: {final_state.values.get('solution', 'N/A')[:120]}")
    print(f"   执行: {final_state.values.get('execution_result', 'N/A')[:120]}")

# 测试
graph = build_graph()
hitl_approval_loop(graph, "EP-D-002 断路器拒分，需要紧急处理", "thread-001")
```

2. 分别测试批准和驳回两条路径，观察流程差异。

**预期结果**：批准 → 继续 solution → execute。驳回 → 重新 diagnosis → 再次暂停。

---

### Task 3：对接飞书审批（选做）

**目标**：把终端交互改为飞书卡片消息。

**步骤**：

1. 利用已有的飞书 Webhook 能力（`demo/gateway/app.py` 中已实现 `POST /api/feishu/send`）
2. 暂停后发送飞书卡片：

```python
import requests

FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")

def send_approval_card(thread_id, diagnosis, severity):
    if not FEISHU_WEBHOOK_URL:
        print("⚠️ 未配置飞书 Webhook URL，使用终端审批")
        return None
    
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"content": "🔔 故障诊断待审批"}},
            "elements": [
                {"tag": "div", "text": {"content": f"**诊断结论**：{diagnosis}"}},
                {"tag": "div", "text": {"content": f"**严重程度**：{severity}"}},
                {"tag": "div", "text": {"content": f"**线程ID**：{thread_id}"}},
            ],
        },
    }
    
    resp = requests.post(FEISHU_WEBHOOK_URL, json=card)
    return resp.status_code == 200
```

3. 在审批循环中：暂停 → 发飞书卡片 → 等待回调 → 继续

**预期结果**：飞书收到审批卡片，审批人点击后流程图继续执行。

> 如果飞书不可用，继续使用终端审批方式。飞书审批的核心价值是"异步"——审批人不需要守在终端前。

---

### Task 4（选做）：对比有 HITL 和无 HITL 的工作流

**目标**：把 lab7.5 的无 HITL 图和本实验的 HITL 图放在一起对比。

**步骤**：

1. 用同一个任务分别跑两个图
2. 对比维度：

| 维度 | 无 HITL | 有 HITL |
|------|:---:|:---:|
| 执行是否一气呵成 | ✅ | ❌ 中间暂停 |
| 能否人工修正诊断结果 | ❌ | ✅ 驳回后重新诊断 |
| 适合什么场景 | 自动巡检、批量处理 | 关键设备诊断、停机决策 |

**预期结果**：理解 HITL 不是"把流程变慢"，而是"在关键节点给人决策权"。

---

## 📊 结果产出

| 产出 | 格式 | 位置 | 说明 |
|------|------|------|------|
| HITL 完整实现 | `.py` | `demo/hitl_skeleton.py` | interrupt + 审批循环 |
| 批准/驳回两条路径截图 | 终端输出 | 终端 | 展示两条路径的差异 |

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 | 检查 |
|------|--------|----------|------|
| 1 | **interrupt 暂停截图** | `state.next` 显示待执行节点名 | ☐ |
| 2 | **批准路径截图** | 输入 a 后完整执行 solution → execute | ☐ |
| 3 | **驳回路径截图** | 输入 r 后重新 diagnosis → 再次暂停 | ☐ |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| `interrupt_before` 不生效 | 没有传 Checkpointer | `compile()` 必须同时传 `interrupt_before` 和 `checkpointer` |
| `state.next` 是空元组 | 图已运行完毕 | 检查是否所有路径都走到了 END |
| `update_state` 后状态没变 | 没传正确的 config | 必须传与 stream 相同的 `config` |
| 驳回后走了错误路径 | `route_by_severity` 的返回值不匹配 | 修改 state 时要同时更新 `severity` 字段 |

---

**🎉 恭喜完成实验！**
