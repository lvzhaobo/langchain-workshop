"""
Step 2: Agent 图组装 — 5 节点 + 工具系统
"""

from __future__ import annotations
from typing import Optional, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
import os

from state import AgentState  # type: ignore[import-untyped]
from nodes import (  # type: ignore[import-untyped]
    set_llm,
    understand_intent,
    enrich_context,
    plan_tasks,
    execute_tool,
    generate_output,
)
from router import route_after_plan  # type: ignore[import-untyped]


def build_graph(model_name: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None):
    model_name = model_name or os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    base_url = base_url or os.getenv("OPENAI_BASE_URL")

    if not api_key:
        print("请设置 OPENAI_API_KEY 或通过 --api-key 传入")
        raise RuntimeError("缺少 API Key")

    import httpx
    http_client = httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0), trust_env=False)
    llm = ChatOpenAI(
        model=model_name, api_key=api_key, temperature=0,
        http_client=http_client, http_socket_options=(),
    )  # type: ignore
    if base_url:
        llm.base_url = base_url  # type: ignore[attr-defined]
    set_llm(llm)

    print(f"🤖 模型: {model_name}")
    if base_url:
        print(f"🌐 API: {base_url}")

    # ── 构建 Graph（5 节点，2 条件边） ──
    graph = StateGraph(AgentState)
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("enrich_context", enrich_context)
    graph.add_node("plan_tasks", plan_tasks)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("generate_output", generate_output)

    graph.set_entry_point("understand_intent")
    graph.add_edge("understand_intent", "enrich_context")
    graph.add_edge("enrich_context", "plan_tasks")

    # 条件边 1: plan 后 → 执行 or 直接生成
    graph.add_conditional_edges(
        "plan_tasks", route_after_plan,
        {"execute": "execute_tool", "generate": "generate_output"}
    )
    # 条件边 2: execute 后 → 继续执行 or 生成
    graph.add_conditional_edges(
        "execute_tool", _route_after_execute,
        {"continue": "execute_tool", "done": "generate_output"}
    )

    graph.add_edge("generate_output", END)

    compiled = graph.compile(checkpointer=MemorySaver())
    print("✅ Agent Graph 构建完成（5 节点 + 工具系统）")
    print("   节点: understand_intent → enrich_context → plan_tasks → execute_tool ⇄ generate_output")
    return compiled


def _route_after_execute(state: AgentState) -> str:
    """全部步骤执行完 → 生成产物，否则继续"""
    if state["current_step"] >= len(state.get("plan", [])):
        return "done"
    return "continue"
