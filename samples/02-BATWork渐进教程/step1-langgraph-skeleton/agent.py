"""
Step 1: Agent 图组装 — 3 节点直线拓扑
"""

from __future__ import annotations
import os
import httpx
from typing import Optional, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from state import AgentState  # type: ignore[import-untyped]
from nodes import set_llm, understand_intent, enrich_context, generate_output  # type: ignore[import-untyped]


def build_graph(model_name: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None):
    model_name = model_name or os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    base_url = base_url or os.getenv("OPENAI_BASE_URL")

    if not api_key:
        print("请设置 OPENAI_API_KEY 或通过 --api-key 传入")
        raise RuntimeError("缺少 API Key")

    http_client = httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0), trust_env=False)
    llm = ChatOpenAI(
        model=model_name, api_key=api_key, temperature=0,
        http_client=http_client, http_socket_options=(),
    )  # type: ignore
    if base_url:
        llm.base_url = base_url

    set_llm(llm)

    print(f"🤖 模型: {model_name}")
    if base_url:
        print(f"🌐 API: {base_url}")

    # ── 构建 Graph（3 节点，直线） ──
    graph = StateGraph(AgentState)
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("enrich_context", enrich_context)
    graph.add_node("generate_output", generate_output)

    graph.set_entry_point("understand_intent")
    graph.add_edge("understand_intent", "enrich_context")
    graph.add_edge("enrich_context", "generate_output")
    graph.add_edge("generate_output", END)

    compiled = graph.compile(checkpointer=MemorySaver())
    print("✅ Agent Graph 构建完成（3 节点直线拓扑）")
    return compiled
