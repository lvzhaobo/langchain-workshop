"""
DAG 模式 7：子图嵌套（Subgraph）

图结构：
  [入口] → [子图A: 数据处理流水线] → [子图B: 分析流水线] → [出口] → END
                 │                           │
            planner→writer→polisher      analyzer→evaluator

API 映射：
  LangGraph 支持将已编译的图作为一个节点添加到父图中
  builder.add_node("subgraph_name", compiled_sub_app)
  子图内部的状态与父图状态通过字段映射关联

运行：
  export DASHSCOPE_API_KEY="sk-..."
  python 7_subgraph.py
"""

import os, time
from typing import TypedDict
from datetime import datetime, timezone, timedelta
from langgraph.graph import StateGraph, END

CST = timezone(timedelta(hours=8))


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
        time.sleep(0.15)
        return ""
    return llm.invoke(prompt).content


# ============================================================
# 子图 A：内容生成流水线（plan → write → polish）
# ============================================================
class SubStateA(TypedDict):
    raw_input: str
    plan: str
    draft: str
    polished: str


def plan_node(s: SubStateA) -> dict:
    print(f"    📋 [子图A/planner] ...")
    content = _call(f'为「{s["raw_input"]}」生成 3 句大纲。')
    return {"plan": content or f"大纲: {s['raw_input']}"}


def write_node(s: SubStateA) -> dict:
    print(f"    ✍️ [子图A/writer] ...")
    content = _call(f'根据大纲写 100 字: {s["plan"]}')
    return {"draft": content or "模拟内容"}


def polish_node(s: SubStateA) -> dict:
    print(f"    ✨ [子图A/polisher] ...")
    content = _call(f'润色: {s["draft"]}')
    return {"polished": content or s["draft"]}


sub_a = StateGraph(SubStateA)
sub_a.add_node("plan", plan_node)
sub_a.add_node("write", write_node)
sub_a.add_node("polish", polish_node)
sub_a.set_entry_point("plan")
sub_a.add_edge("plan", "write")
sub_a.add_edge("write", "polish")
sub_a.add_edge("polish", END)
sub_app_a = sub_a.compile()


# ============================================================
# 子图 B：分析流水线（analyze → evaluate）
# ============================================================
class SubStateB(TypedDict):
    content: str
    analysis: str
    score: str


def analyze_node(s: SubStateB) -> dict:
    print(f"    🔍 [子图B/analyzer] 分析内容...")
    content = _call(f'分析以下内容的优缺点（2句话）:\n{s["content"][:300]}')
    return {"analysis": content or "内容质量良好"}


def evaluate_node(s: SubStateB) -> dict:
    print(f"    📊 [子图B/evaluator] 评分...")
    content = _call(f'基于以下分析，给一个 1-10 的评分并说明理由：\n{s["analysis"]}')
    return {"score": content or "8/10 — 内容质量良好"}


sub_b = StateGraph(SubStateB)
sub_b.add_node("analyze", analyze_node)
sub_b.add_node("evaluate", evaluate_node)
sub_b.set_entry_point("analyze")
sub_b.add_edge("analyze", "evaluate")
sub_b.add_edge("evaluate", END)
sub_app_b = sub_b.compile()


# ============================================================
# 父图：编排子图 A → 子图 B
# ============================================================
class ParentState(TypedDict):
    topic: str
    # 子图 A 的字段
    raw_input: str
    plan: str
    draft: str
    polished: str
    # 子图 B 的字段
    content: str
    analysis: str
    score: str
    # 输出
    output: str


def entry_node(s: ParentState) -> dict:
    """父图入口节点 — 准备输入"""
    print(f"\n🏠 [父图/entry] 准备输入: {s['topic']}")
    return {"raw_input": s["topic"]}


def bridge_node(s: ParentState) -> dict:
    """桥接节点 — 将子图A的输出传给子图B"""
    print(f"\n🌉 [父图/bridge] 桥接输出...")
    return {"content": s.get("polished", s.get("draft", ""))}


def exit_node(s: ParentState) -> dict:
    """父图出口 — 汇总"""
    print(f"\n🏁 [父图/exit] 汇总结果...")
    output = (
        f"=== 内容生成结果 ===\n{s.get('polished', 'N/A')}\n\n"
        f"=== 分析结果 ===\n{s.get('analysis', 'N/A')}\n\n"
        f"=== 评分 ===\n{s.get('score', 'N/A')}"
    )
    return {"output": output}


# 构建父图
parent = StateGraph(ParentState)
parent.add_node("entry", entry_node)

# 关键！将已编译的子图作为节点添加
parent.add_node("pipeline_a", sub_app_a)   # ← 子图 A 作为节点
parent.add_node("bridge", bridge_node)
parent.add_node("pipeline_b", sub_app_b)   # ← 子图 B 作为节点
parent.add_node("exit_node", exit_node)

parent.set_entry_point("entry")
parent.add_edge("entry", "pipeline_a")      # 父图 → 子图A
parent.add_edge("pipeline_a", "bridge")     # 子图A → 桥接
parent.add_edge("bridge", "pipeline_b")     # 桥接 → 子图B
parent.add_edge("pipeline_b", "exit_node")  # 子图B → 出口
parent.add_edge("exit_node", END)

parent_app = parent.compile()


# ====== Run ======
if __name__ == "__main__":
    print("=" * 50)
    print(f"📐 DAG 模式 7：子图嵌套 [{mode.upper()}]")
    print("=" * 50)
    print("图拓扑（嵌套结构）:")
    print("  ┌──────────────────────────────────┐")
    print("  │ 父图                              │")
    print("  │  [entry] → [子图A] → [子图B] → [exit]")
    print("  │              │          │          │")
    print("  │         plan→write     analyze     │")
    print("  │            →polish   →evaluate    │")
    print("  └──────────────────────────────────┘")
    print("API: builder.add_node(\"name\", compiled_sub_app)")
    print()

    topic = "Rust 语言在系统编程中的优势"
    print(f"📝 输入: {topic}\n")

    result = parent_app.invoke({"topic": topic})

    print(f"\n{'='*50}")
    print(f"📊 父图执行完成！")
    print(f"{'='*50}")
    print(result.get("output", "无输出"))

    print(f"\n💡 子图嵌套让复杂流程模块化：")
    print(f"   每个子图有独立的状态空间和拓扑")
    print(f"   父图通过 add_node 将子图作为黑盒节点编排")
    print(f"   适用于：复杂 Agent 的分层设计")
