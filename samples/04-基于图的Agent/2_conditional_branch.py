"""
DAG 模式 2：条件分支（Conditional Branching）

图结构：
                                 ┌─→ [polisher] ──→ END （"need_polish"）
  [writer] ──→ [quality_checker] ─┤
                                 └─→ END          （"good"，跳过润色）

API 映射：
  builder.add_conditional_edges(
      "quality_checker",       # 路由起点
      router_func,             # 路由函数：state → 路由键
      {                        # 路由键 → 目标节点
          "good": END,
          "need_polish": "polisher"
      }
  )

运行：
  export DASHSCOPE_API_KEY="sk-..."
  python 2_conditional_branch.py
"""

import os, time
from typing import TypedDict, Annotated
from datetime import datetime, timezone, timedelta
from langgraph.graph import StateGraph, END

CST = timezone(timedelta(hours=8))


# ====== State ======
class State(TypedDict):
    topic: str
    plan: str
    draft: str
    quality_result: str  # "good" | "need_polish" | "need_rewrite"
    final: str


# ====== LLM ======
def _init_llm():
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None, "mock", None, None
    from langchain_openai import ChatOpenAI
    if os.getenv("DASHSCOPE_API_KEY"):
        return ChatOpenAI(model="qwen-plus", api_key=key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", temperature=0.7), "bailian", "qwen-plus", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    return ChatOpenAI(model="gpt-4o-mini", api_key=key, temperature=0.7), "openai", "gpt-4o-mini", "https://api.openai.com/v1"


llm, mode, model, base_url = _init_llm()


def _call(prompt: str, label: str = "") -> str:
    if llm is None:
        time.sleep(0.2)
        return ""
    return llm.invoke(prompt).content


# ====== Nodes ======
def planner_node(s: State) -> dict:
    print(f"\n🔵 [planner] ...")
    content = _call(f'请为主题「{s["topic"]}」生成一个 3 段写作大纲。每段一句话，直接输出。')
    plan = content or f"1. {s['topic']}背景\n2. 趋势分析\n3. 展望"
    return {"plan": plan}


def writer_node(s: State) -> dict:
    print(f"\n🟢 [writer] 撰写中...")
    content = _call(f'根据以下大纲写一篇 300 字短文：\n\n{s["plan"]}')
    draft = content or f"关于「{s['topic']}」的模拟文章。"
    return {"draft": draft}


def quality_checker_node(s: State) -> dict:
    """质量检查 — 关键节点：输出将决定后续路由"""
    print(f"\n🔍 [quality_checker] 评估草稿质量...")
    if llm:
        content = _call(
            f'评估以下文章草稿的质量。只回复一个词：good 或 need_polish 或 need_rewrite\n\n'
            f'标准：逻辑清晰、无语法错误 → good | 有小问题 → need_polish | 严重问题 → need_rewrite\n\n'
            f'草稿：{s["draft"]}'
        )
        result = content.strip().lower()
        if result not in ("good", "need_polish", "need_rewrite"):
            result = "need_polish"  # fallback
    else:
        result = "need_polish"  # Mock：总是需要润色
    print(f"   → 质量判断: {result.upper()}")
    return {"quality_result": result}


def polisher_node(s: State) -> dict:
    print(f"\n🟡 [polisher] 润色中...")
    content = _call(f'润色以下文章：\n\n{s["draft"]}')
    final = content or f"【润色版】{s['draft']}"
    return {"final": final}


def rewriter_node(s: State) -> dict:
    """重写节点 — 仅 need_rewrite 时进入"""
    print(f"\n🔴 [rewriter] 质量太差，重写中...")
    content = _call(f'以下文章质量不合格，请完全重写：\n\n{s["draft"]}')
    draft = content or f"重写后的文章..."
    return {"final": draft}


# ====== 路由函数 — 条件边的核心 ======
def quality_router(s: State) -> str:
    """
    返回值必须是 route_map 中的 key
    add_conditional_edges 会根据此 key 选择下一个节点
    """
    result = s.get("quality_result", "need_polish")
    print(f"   🔀 路由决策: '{result}' → route_map['{result}']")
    return result


# ====== Build Graph ======
builder = StateGraph(State)
builder.add_node("planner", planner_node)
builder.add_node("writer", writer_node)
builder.add_node("quality_checker", quality_checker_node)
builder.add_node("polisher", polisher_node)
builder.add_node("rewriter", rewriter_node)

builder.set_entry_point("planner")
builder.add_edge("planner", "writer")                        # 直接边
builder.add_edge("writer", "quality_checker")                # 直接边 → 检查

# 关键！条件边：根据 quality_router 的返回值决定流向
builder.add_conditional_edges(
    "quality_checker",          # 从哪个节点出发
    quality_router,             # 路由函数
    {                           # 路由表
        "good": END,            # 质量好 → 直接结束
        "need_polish": "polisher",  # 需润色 → polisher
        "need_rewrite": "rewriter", # 需重写 → rewriter
    }
)
# polisher 和 rewriter 完成后都结束
builder.add_edge("polisher", END)
builder.add_edge("rewriter", END)

app = builder.compile()


# ====== Run ======
if __name__ == "__main__":
    print("=" * 50)
    print(f"📐 DAG 模式 2：条件分支 [{mode.upper()}]")
    print("=" * 50)
    print("图拓扑:")
    print("  [planner] → [writer] → [quality_checker]")
    print("                                ├─ good ──────────→ END")
    print("                                ├─ need_polish ──→ [polisher] → END")
    print("                                └─ need_rewrite ──→ [rewriter] → END")
    print("边类型: add_edge + add_conditional_edges（条件路由）")
    print()

    topic = "Python 入门教程"
    print(f"📝 输入: {topic}\n")

    for step in app.stream({"topic": topic}):
        node_id = list(step.keys())[0]
        data = step[node_id]
        if "final" in data:
            print(f"\n✨ 最终输出:\n{data['final'][:200]}...")
        if "quality_result" in data:
            print(f"\n🔀 路由结果: {data['quality_result']}")
