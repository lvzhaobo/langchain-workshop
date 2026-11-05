"""
Agent 图组装 — 用 LangGraph StateGraph 把节点和路由连成完整 Agent Loop

Step 4 新增：接受 Memory 实例，注入到 nodes 模块
Step 5 新增：接受 Skills 列表，注入到 nodes 模块
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
    set_memory,
    set_skills,
    understand_intent,
    enrich_context,
    plan_tasks,
    execute_tool,
    validate_result,
    generate_output,
    handle_error,
)
from router import route_after_plan, route_after_execute, route_after_validate  # type: ignore[import-untyped]


def build_graph(model_name: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None, memory: Any = None, skills: list = None):
    """
    构建并编译 Agent Graph

    参数:
        model_name: 模型名，默认从环境变量 LLM_MODEL 读取，fallback 到 gpt-4o-mini
        api_key: API Key，默认从环境变量 OPENAI_API_KEY 读取
        base_url: API 地址，默认从环境变量 OPENAI_BASE_URL 读取
        memory: AgentMemory 实例（Step 4 新增）
        skills: Skill 列表（Step 5 新增）
    """

    model_name = model_name or os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    base_url = base_url or os.getenv("OPENAI_BASE_URL")

    if not api_key:
        print("⚠️  未设置 OPENAI_API_KEY，将尝试使用本地模型...")
        print("   设置方法: export OPENAI_API_KEY=your-key")
        print("   或使用: python main.py --api-key your-key --base-url http://localhost:11434/v1 --model qwen2.5:7b")
        raise RuntimeError("请设置 OPENAI_API_KEY 环境变量，或通过 --api-key 参数传入")

    # 初始化 LLM
    import httpx
    # trust_env=False: 绕过系统 HTTP 代理（如 Clash），避免 localhost 请求被代理拦截
    http_client = httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0), trust_env=False)
    llm_kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": api_key,
        "temperature": 0,
        "http_client": http_client,
        "http_socket_options": (),  # 禁止 langchain-openai 覆盖我们的 http_client
    }
    if base_url:
        llm_kwargs["base_url"] = base_url
    llm = ChatOpenAI(**llm_kwargs)  # type: ignore[arg-type]

    set_llm(llm)  # 注入到 nodes 模块

    # ── Step 4 新增：注入 Memory 到 nodes ──
    if memory is not None:
        set_memory(memory)
        print(f"🧠 Memory 已启用: {memory.stats()}")

    # ── Step 5 新增：注入 Skills 到 nodes ──
    if skills:
        set_skills(skills)
        print(f"🎯 已加载 {len(skills)} 个 Skill")

    print(f"🤖 模型: {model_name}")
    if base_url:
        print(f"🌐 API: {base_url}")

    # ── 构建 Graph ──
    graph = StateGraph(AgentState)

    # 添加所有节点
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("enrich_context", enrich_context)
    graph.add_node("plan_tasks", plan_tasks)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("validate_result", validate_result)
    graph.add_node("generate_output", generate_output)
    graph.add_node("handle_error", handle_error)

    # 入口
    graph.set_entry_point("understand_intent")

    # 固定边
    graph.add_edge("understand_intent", "enrich_context")
    graph.add_edge("enrich_context", "plan_tasks")

    # 条件边 1: plan_tasks → execute_tool 或 generate_output
    graph.add_conditional_edges(
        "plan_tasks",
        route_after_plan,
        {
            "execute": "execute_tool",
            "generate": "generate_output",
        }
    )

    # 条件边 2: execute_tool → validate_result 或 handle_error
    graph.add_conditional_edges(
        "execute_tool",
        route_after_execute,
        {
            "validate": "validate_result",
            "error": "handle_error",
        }
    )

    # 条件边 3: validate_result → execute_tool / generate_output / plan_tasks / handle_error
    graph.add_conditional_edges(
        "validate_result",
        route_after_validate,
        {
            "continue": "execute_tool",
            "generate": "generate_output",
            "retry": "execute_tool",
            "replan": "plan_tasks",
        }
    )

    # 终点
    graph.add_edge("generate_output", END)
    graph.add_edge("handle_error", END)

    # 编译（带 Checkpointer，支持会话持久化）
    checkpointer = MemorySaver()
    compiled = graph.compile(checkpointer=checkpointer)

    print("✅ Agent Graph 构建完成")
    print(f"   节点: understand_intent → enrich_context → plan_tasks → execute_tool ⇄ validate_result → generate_output")
    print(f"   兜底: handle_error")

    return compiled
