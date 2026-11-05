"""
DAG 模式 6：Human-in-the-Loop（人工介入）

图结构：
  [planner] → [writer] → [⏸️ 暂停] → [human_review] → END
                               ↑
                      interrupt_before 在此暂停
                      等待人工输入后继续

API 映射：
  builder.compile(checkpointer=..., interrupt_before=["human_review"])
  → 图在 human_review 节点前自动暂停
  → app.invoke(None, config) 继续执行（可传入人工决策）

运行：
  export DASHSCOPE_API_KEY="sk-..."
  python 6_human_in_loop.py
"""

import os, time
from typing import TypedDict
from datetime import datetime, timezone, timedelta
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

CST = timezone(timedelta(hours=8))


# ====== State ======
class State(TypedDict):
    topic: str
    plan: str
    draft: str
    human_decision: str     # 人工输入: "approve" | "reject" | "modify"
    human_feedback: str     # 人工反馈文本
    final: str


# ====== LLM ======
def _init_llm():
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None, "mock"
    from langchain_openai import ChatOpenAI
    if os.getenv("DASHSCOPE_API_KEY"):
        return ChatOpenAI(model="qwen-plus", api_key=key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", temperature=0.7), "bailian"
    return ChatOpenAI(model="gpt-4o-mini", api_key=key, temperature=0.7), "openai"


llm, mode = _init_llm()


def _call(prompt: str) -> str:
    if llm is None:
        time.sleep(0.2)
        return ""
    return llm.invoke(prompt).content


# ====== Nodes ======
def planner_node(s: State) -> dict:
    content = _call(f'为主题「{s["topic"]}」生成写作大纲。')
    plan = content or f"大纲：{s['topic']}"
    print(f"🔵 [planner] 完成")
    return {"plan": plan}


def writer_node(s: State) -> dict:
    content = _call(f'根据大纲写一篇 200 字短文：{s["plan"]}')
    draft = content or "模拟文章..."
    print(f"🟢 [writer] 完成 ({len(draft)}字)")
    return {"draft": draft}


def human_review_node(s: State) -> dict:
    """
    人工审核节点 — 图在执行此节点前会自动暂停
    LangGraph >=1.0: 通过 Command(resume=...) 注入人工决策
    """
    # 从 state 或 Command resume 获取人工决策
    decision = s.get("human_decision", "") or "approve"
    feedback = s.get("human_feedback", "")

    print(f"\n👤 [human_review] 人工决策: {decision}")
    if feedback:
        print(f"   反馈: {feedback}")

    if decision == "approve":
        return {"final": f"【已审核通过】\n{s.get('draft', '')}"}
    elif decision == "modify":
        modified = _call(f'按以下反馈修改文章：\n反馈：{feedback}\n原文：{s.get("draft", "")}')
        return {"final": f"【按反馈修改】\n{modified or s.get('draft', '')}"}
    else:
        return {"final": f"【已驳回】决策: {decision}"}


# ====== Build Graph（带 Checkpoint + Interrupt） ======
builder = StateGraph(State)
builder.add_node("planner", planner_node)
builder.add_node("writer", writer_node)
builder.add_node("human_review", human_review_node)

builder.set_entry_point("planner")
builder.add_edge("planner", "writer")
builder.add_edge("writer", "human_review")
builder.add_edge("human_review", END)

# 关键！启用 Checkpoint + 中断
checkpointer = MemorySaver()
app = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["human_review"],  # ← 在 human_review 前暂停
)


# ====== Run ======
if __name__ == "__main__":
    print("=" * 50)
    print(f"📐 DAG 模式 6：Human-in-the-Loop [{mode.upper()}]")
    print("=" * 50)
    print("图拓扑: [planner] → [writer] → ⏸️(暂停) → [human_review] → END")
    print("API: checkpointer + interrupt_before=[\"human_review\"]")
    print("机制: 图在 human_review 前自动暂停，等待人工输入")
    print()

    topic = "开源社区治理的挑战"
    print(f"📝 输入: {topic}\n")

    config = {"configurable": {"thread_id": "hil-demo-001"}}

    # === 第一轮：执行到 human_review 前自动暂停 ===
    print("━━━ 第一轮：执行到人工审核前 ━━━\n")
    result = app.invoke({"topic": topic}, config)

    # 状态快照
    snapshot = app.get_state(config)
    print(f"\n⏸️  图已暂停在: {snapshot.next}")
    print(f"   下一步节点: {list(snapshot.next) if snapshot.next else 'N/A'}")
    print(f"   当前 draft 预览: {snapshot.values.get('draft', '')[:100]}...")
    print(f"\n   [模拟人工决策] human_decision = 'modify'")
    print(f"   [模拟人工反馈] '请增加对社区治理工具链的讨论'\n")

    # === 第二轮：使用 Command(resume=...) 从断点恢复 ===
    print("━━━ 第二轮：人工决策后恢复 ━━━\n")
    result = app.invoke(
        Command(resume={"human_decision": "modify", "human_feedback": "请增加对社区治理工具链的讨论"}),
        config,
    )

    print(f"\n{'='*50}")
    print(f"📊 最终结果:")
    print(result.get("final", "无输出")[:300])

    # 查看完整历史
    history = list(app.get_state_history(config))
    print(f"\n💡 Checkpoint 历史: {len(history)} 个状态快照")
    for i, h in enumerate(history):
        print(f"   快照 {i}: step={h.metadata.get('step', '?')}")

    print(f"\n💡 interrupt_before 让 DAG 在指定节点前暂停")
    print(f"   人工输入通过 app.invoke({{...}}, config) 注入")
    print(f"   config['thread_id'] 保证同一会话的状态连续性")
