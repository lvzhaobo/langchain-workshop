"""
DAG 模式 4：循环/重试（Loop / Retry）

图结构：
  [writer] → [quality_checker] ──"good"──→ [polisher] → END
                        ↑                    │
                        └──"retry"── 回到 writer 重写

API 映射：
  add_conditional_edges 中，route_map 可以指向已在拓扑中执行过的节点
  LangGraph 检测到循环 → 使用 recursion_limit 控制最大循环次数

运行：
  export DASHSCOPE_API_KEY="sk-..."
  python 4_loop_retry.py
"""

import os, time
from typing import TypedDict
from datetime import datetime, timezone, timedelta
from langgraph.graph import StateGraph, END

CST = timezone(timedelta(hours=8))


# ====== State ======
class State(TypedDict):
    topic: str
    plan: str
    draft: str
    retry_count: int       # 重试计数器（防止无限循环）
    quality_result: str    # "good" | "retry" | "fail"
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
MAX_RETRIES = 3


def _call(prompt: str) -> str:
    if llm is None:
        time.sleep(0.3)
        return ""
    return llm.invoke(prompt).content


# ====== Nodes ======
def planner_node(s: State) -> dict:
    content = _call(f'请为主题「{s["topic"]}」生成一个 3 段写作大纲。')
    plan = content or f"1. {s['topic']}背景\n2. 分析\n3. 展望"
    print(f"🔵 [planner] 大纲生成完成 ({len(plan)}字)")
    return {"plan": plan, "retry_count": 0}


def writer_node(s: State) -> dict:
    retry = s.get("retry_count", 0)
    label = f"第{retry+1}次尝试" if retry > 0 else "首次写作"
    print(f"\n🟢 [writer] {label}... (retry_count={retry})")

    if retry > 0:
        prompt = f'之前的草稿质量不合格。请重新写一篇 300 字短文，这次要提高质量：\n\n大纲：{s["plan"]}\n\n之前的草稿：{s.get("draft", "")[:100]}...'
    else:
        prompt = f'根据大纲写一篇 300 字短文：\n\n{s["plan"]}'

    content = _call(prompt)
    draft = content or f"模拟文章内容..."
    print(f"   ✅ 完成 ({len(draft)}字)")
    return {"draft": draft}


def quality_checker_node(s: State) -> dict:
    """质量检查 — 决定是继续还是重试"""
    retry = s.get("retry_count", 0)
    print(f"\n🔍 [quality_checker] 评估中... (已重试 {retry}/{MAX_RETRIES})")

    if retry >= MAX_RETRIES:
        print(f"   → FAIL: 达到最大重试次数，强行放行")
        return {"quality_result": "good"}  # 不再重试，放行

    if llm:
        content = _call(f'评审以下草稿。只回复一个词：good（优秀）或 retry（需重写）\n\n{s["draft"][:500]}')
        result = content.strip().lower()[:10]
        if "good" in result:
            result = "good"
        else:
            result = "retry"
    else:
        # Mock 模拟：前 2 次 retry，第 3 次 good
        result = "good" if retry >= 2 else "retry"

    print(f"   → {result.upper()}")
    return {"quality_result": result}


def polisher_node(s: State) -> dict:
    print(f"\n🟡 [polisher] 润色最终稿...")
    content = _call(f'润色：{s["draft"]}')
    final = content or s["draft"]
    return {"final": final}


# ====== 路由函数 ======
def quality_router(s: State) -> str:
    """good → 继续润色 | retry → 回到 writer | fail → 降级结束"""
    result = s.get("quality_result", "good")
    retry = s.get("retry_count", 0)
    if result == "good":
        return "good"
    elif result == "retry" and retry < MAX_RETRIES:
        return "retry"
    else:
        return "fail"


# ====== Build Graph（包含循环边） ======
builder = StateGraph(State)
builder.add_node("planner", planner_node)
builder.add_node("writer", writer_node)
builder.add_node("quality_checker", quality_checker_node)
builder.add_node("polisher", polisher_node)

builder.set_entry_point("planner")
builder.add_edge("planner", "writer")
builder.add_edge("writer", "quality_checker")

# 关键！条件边：retry → 回到 writer（形成循环）
builder.add_conditional_edges(
    "quality_checker",
    quality_router,
    {
        "good": "polisher",   # 质量好 → 润色
        "retry": "writer",    # ← 循环边！回到 writer
        "fail": END,          # 超过最大重试 → 降级结束
    }
)
builder.add_edge("polisher", END)

app = builder.compile()


# ====== Run ======
if __name__ == "__main__":
    print("=" * 50)
    print(f"📐 DAG 模式 4：循环/重试 [{mode.upper()}]")
    print("=" * 50)
    print("图拓扑:")
    print("  [planner] → [writer] → [quality_checker]")
    print("                               ├─ good ──→ [polisher] → END")
    print("                               ├─ retry ─→ [writer] ← 循环边！")
    print("                               └─ fail ──→ END")
    print(f"边类型: add_conditional_edges + 回指边（最大 {MAX_RETRIES} 次重试）")
    print()

    topic = "TypeScript 入门教程"
    print(f"📝 输入: {topic}\n")

    # recursion_limit 必须 > 最大可能的步骤数
    result = app.invoke({"topic": topic}, {"recursion_limit": 20})

    retries = result.get("retry_count", 0)
    print(f"\n{'='*50}")
    print(f"📊 执行完成: 最终重试次数 = {retries}")
    print(f"📊 最终结果判定: {result.get('quality_result', 'N/A')}")
    if result.get("final"):
        print(f"\n✨ 最终稿:\n{result['final'][:200]}...")
    print(f"\n💡 循环通过 conditional_edges 实现，通过 recursion_limit 防止无限循环")
