"""
LangGraph 核心模块 — 三节点线性流水线
可被 Flask API 或命令行直接调用
"""

import os
import time
from datetime import datetime, timezone, timedelta
from typing import TypedDict
from langgraph.graph import StateGraph, END

# 北京时间
CST = timezone(timedelta(hours=8))


# ============================================================
# 状态定义
# ============================================================
class ArticleState(TypedDict):
    topic: str
    plan: str
    draft: str
    final: str
    # API 调用追踪 — 每个节点的 LLM 调用详情
    _trace_planner: dict | None
    _trace_writer: dict | None
    _trace_polisher: dict | None


# ============================================================
# LLM 初始化（延迟加载，首次调用时才初始化）
# ============================================================
_llm = None
_llm_mode = None
_llm_model = None
_llm_base_url = None


def _get_llm():
    """延迟初始化 LLM，避免 import 时就连 API"""
    global _llm, _llm_mode, _llm_model, _llm_base_url

    if _llm is not None:
        return _llm, _llm_mode

    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if dashscope_key:
        from langchain_openai import ChatOpenAI
        _llm_model = "qwen-plus"
        _llm_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        _llm = ChatOpenAI(
            model=_llm_model,
            api_key=dashscope_key,
            base_url=_llm_base_url,
            temperature=0.7,
        )
        _llm_mode = "bailian"
    elif openai_key:
        from langchain_openai import ChatOpenAI
        _llm_model = "gpt-4o-mini"
        _llm_base_url = "https://api.openai.com/v1"
        _llm = ChatOpenAI(model=_llm_model, temperature=0.7)
        _llm_mode = "openai"
    else:
        _llm_model = None
        _llm_base_url = None
        _llm = None
        _llm_mode = "mock"

    return _llm, _llm_mode


def get_llm_info() -> dict:
    """获取当前 LLM 配置信息"""
    _get_llm()
    return {
        "mode": _llm_mode,
        "model": _llm_model or "N/A",
        "base_url": _llm_base_url or "N/A",
        "provider": {
            "bailian": "阿里云百炼 (DashScope)",
            "openai": "OpenAI",
            "mock": "Mock 模拟",
        }.get(_llm_mode, "Unknown"),
    }


# ============================================================
# LLM 调用包装器 — 记录每次 API 调用的完整信息
# ============================================================

def _call_llm_with_trace(prompt: str, node_name: str) -> tuple[str, dict]:
    """
    调用 LLM 并返回 (响应内容, API调用追踪信息)
    """
    llm, mode = _get_llm()
    trace = {
        "node": node_name,
        "timestamp": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp_iso": datetime.now(CST).isoformat(),
        "mode": mode,
        "model": _llm_model or "mock",
        "base_url": _llm_base_url or "N/A",
        "prompt_length": len(prompt),
        "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
    }

    if llm is None:
        # Mock 模式 — 模拟延迟
        time.sleep(0.3)
        trace["response_length"] = 0
        trace["latency_ms"] = 300
        trace["token_usage"] = None
        trace["is_mock"] = True
        return "", trace

    # 真实 LLM 调用
    start = time.time()
    try:
        response = llm.invoke(prompt)
        latency = round((time.time() - start) * 1000)

        trace["response_length"] = len(response.content)
        trace["latency_ms"] = latency
        trace["is_mock"] = False

        # 尝试提取 token 用量（不同模型返回格式可能不同）
        try:
            usage = response.response_metadata.get("token_usage", {})
            trace["token_usage"] = {
                "prompt_tokens": usage.get("prompt_tokens", "?"),
                "completion_tokens": usage.get("completion_tokens", "?"),
                "total_tokens": usage.get("total_tokens", "?"),
            }
        except:
            trace["token_usage"] = None

        # 记录实际请求的 request_id（如果有）
        try:
            trace["request_id"] = response.response_metadata.get("request_id", "")
        except:
            trace["request_id"] = ""

        return response.content, trace

    except Exception as e:
        trace["error"] = str(e)
        trace["latency_ms"] = round((time.time() - start) * 1000)
        trace["is_mock"] = False
        raise


# ============================================================
# 节点函数
# ============================================================

def planner_node(state: ArticleState) -> dict:
    """节点1：根据主题生成写作大纲"""
    topic = state["topic"]
    prompt = f'请为主题「{topic}」生成一个 3 段式的写作大纲，每段一句话。直接输出大纲，不要废话。'

    content, trace = _call_llm_with_trace(prompt, "planner")
    if content:
        plan = content
    else:
        plan = (
            f"1. 引言段：阐述「{topic}」的背景与核心问题\n"
            f"2. 主体段：分析关键技术趋势与实践案例\n"
            f"3. 结论段：展望未来发展方向与潜在挑战"
        )

    return {"plan": plan, "_trace_planner": trace}


def writer_node(state: ArticleState) -> dict:
    """节点2：根据大纲撰写正文"""
    prompt = f'根据以下大纲写一篇 300 字左右的短文，语言流畅自然：\n\n{state["plan"]}'

    content, trace = _call_llm_with_trace(prompt, "writer")
    if content:
        draft = content
    else:
        draft = (
            f"随着人工智能技术的飞速发展，{state['topic']}正在成为业界关注的焦点。"
            f"传统的软件开发模式面临着效率瓶颈，而 AI Agent 的出现为行业带来了全新的可能性。"
            f"从需求分析到代码生成，从测试到运维，Agent 正在重新定义开发者的工作方式。\n\n"
            f"在实际应用中，基于大语言模型的 Agent 能够理解自然语言指令，"
            f"自主规划任务步骤，调用工具链完成复杂工程操作。"
            f"一些领先企业已经将 Agent 集成到 CI/CD 流水线中，实现了代码审查、"
            f"Bug 修复等环节的自动化，显著缩短了交付周期。\n\n"
            f"展望未来，Agent 将从辅助工具逐步演进为自主开发实体，"
            f"具备更强的推理能力和上下文理解能力。然而，可靠性、安全性以及"
            f"与现有人类工作流的融合仍然是需要持续攻克的挑战。"
        )

    return {"draft": draft, "_trace_writer": trace}


def polisher_node(state: ArticleState) -> dict:
    """节点3：润色正文"""
    prompt = f'请润色以下文章，修正语法和用词，使其更加优美，不要改变原意：\n\n{state["draft"]}'

    content, trace = _call_llm_with_trace(prompt, "polisher")
    if content:
        final = content
    else:
        final = (
            f"【润色版】\n\n"
            f"{state['draft']}\n\n"
            f"── 以上内容经过语法修正和用词优化 ✅"
        )

    return {"final": final, "_trace_polisher": trace}


# ============================================================
# 图构建与导出
# ============================================================

def build_graph() -> StateGraph:
    """构建图，返回编译后的 App"""
    builder = StateGraph(ArticleState)
    builder.add_node("planner", planner_node)
    builder.add_node("writer", writer_node)
    builder.add_node("polisher", polisher_node)

    builder.set_entry_point("planner")
    builder.add_edge("planner", "writer")
    builder.add_edge("writer", "polisher")
    builder.add_edge("polisher", END)

    return builder.compile()


def run_graph(topic: str) -> dict:
    """执行图，返回完整状态"""
    app = build_graph()
    result = app.invoke({"topic": topic})
    return dict(result)


def get_graph_structure() -> dict:
    """获取图结构元数据"""
    app = build_graph()
    g = app.get_graph()
    return {
        "nodes": [{"id": n, "label": _node_label(n)} for n in g.nodes.keys()],
        "edges": [{"source": e.source, "target": e.target} for e in g.edges],
    }


def _node_label(node_id: str) -> str:
    labels = {
        "__start__": "🚀 开始",
        "planner": "📋 计划节点",
        "writer": "✍️ 写作节点",
        "polisher": "✨ 润色节点",
        "__end__": "🏁 结束",
    }
    return labels.get(node_id, node_id)
