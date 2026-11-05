"""
记忆操作封装为 LangGraph 图的节点

每个记忆操作 = 图上的一个节点，受 Checkpointer 保护：
1. load_memory    → 会话开始时加载记忆上下文
2. save_memory    → Agent 响应后自动提取并保存记忆
3. update_profile → 检测到画像变更时更新 Store
4. consolidate    → 定期运行巩固管道
5. search_memory  → Agent 主动调用的按需搜索

图结构:
    [load_memory] → [agent] → [save_to_memory]
                                   |
                    ┌──────────────┤
                    ▼              ▼
            [update_profile]   [consolidate]
                    │              │
                    └──────┬───────┘
                           ▼
                          END
"""

import hashlib
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from state import MemoryAgentState
from memory_store import MemoryStoreManager


# ═══════════════════════════════════════════════════════════
# 记忆节点函数
# ═══════════════════════════════════════════════════════════

async def load_memory_node(state: MemoryAgentState, config: RunnableConfig) -> dict:
    """
    会话开始时加载相关记忆。

    1. 获取用户画像
    2. 用当前用户消息搜索相关长期记忆
    3. 组装记忆块注入 SystemMessage
    """
    store = config["configurable"]["store"]
    user_id = state["session_meta"].get("user_id", "default")
    memory = MemoryStoreManager(store, user_id)

    # 获取画像
    profile = memory.get_profile()

    # 用最近一条用户消息搜索记忆
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    query = user_messages[-1].content if user_messages else ""
    recalled = memory.recall(query, limit=5) if query else []

    # 组装记忆上下文
    parts = []

    if recalled:
        parts.append("## 相关长期记忆")
        for r in recalled:
            parts.append(
                f"- [{r.get('category', '?')}] {r['content'][:120]} "
                f"(评分: {r.get('effective_score', r.get('score', 5)):.1f}, "
                f"被回忆: {r.get('recall_count', 0)}次)"
            )

    high_conf_traits = {
        k: v for k, v in profile.get("traits", {}).items()
        if v.get("confidence", 0) >= 0.7
    }
    if high_conf_traits:
        parts.append("\n## 用户画像（高置信度）")
        for trait, info in high_conf_traits.items():
            parts.append(f"- {trait}: {info['value']} (置信度: {info['confidence']:.2f})")

    memory_context = "\n".join(parts)

    # 注入 SystemMessage
    system_msg = SystemMessage(
        content=f"[MEMORY CONTEXT]\n\n{memory_context}"
        if memory_context else "[MEMORY CONTEXT]\n\n（暂无相关记忆）"
    )

    return {
        "memory_context": memory_context or "（无）",
        "memory_blocks": {
            "profile": profile,
            "recalled": recalled,
        },
        "messages": [system_msg],
        "user_profile": profile,
    }


async def save_to_memory_node(state: MemoryAgentState, config: RunnableConfig) -> dict:
    """
    在 Agent 响应后提取并保存记忆。

    类似 OpenClaw 的 Pre-compaction Flush：
    在上下文压缩前将关键信息持久化。
    """
    store = config["configurable"]["store"]
    user_id = state["session_meta"].get("user_id", "default")
    memory = MemoryStoreManager(store, user_id)

    # 取最近 3 轮对话（6 条消息）
    recent = state["messages"][-6:]
    text = "\n".join(
        f"{'USER' if isinstance(m, HumanMessage) else 'AGENT'}: {m.content[:200]}"
        for m in recent
    )

    # 用规则提取事实（生产环境替换为 LLM 调用）
    facts_to_save = _extract_facts_heuristic(text)

    saved_count = 0
    for fact in facts_to_save:
        memory.remember(
            content=fact["content"],
            category=fact.get("category", "knowledge"),
            score=fact.get("score", 5.0),
            confidence=fact.get("confidence", 0.5),
        )
        saved_count += 1

    return {"pending_consolidation": saved_count > 0}


async def update_profile_node(state: MemoryAgentState, config: RunnableConfig) -> dict:
    """
    从最新对话中提取画像更新。

    检查 state.profile_delta，如果有变更则写入 Store。
    """
    delta = state.get("profile_delta")
    if not delta:
        return {}

    store = config["configurable"]["store"]
    user_id = state["session_meta"].get("user_id", "default")
    memory = MemoryStoreManager(store, user_id)

    # 更新特征
    traits = delta.get("traits", {})
    if traits:
        memory.update_profile(
            trait_updates=traits,
            confidence=delta.get("confidence", 0.5),
        )

    # 保存画像相关的事实
    for fact in delta.get("facts", []):
        memory.add_profile_fact(
            fact=fact,
            confidence=delta.get("confidence", 0.5),
        )

    return {"profile_delta": None}


async def consolidate_memory_node(state: MemoryAgentState, config: RunnableConfig) -> dict:
    """
    巩固管道（类似 OpenClaw 的 Dreaming 三步过程）。

    触发条件：pending_consolidation == True

    轻睡眠 → REM 睡眠 → 深睡眠：
    1. 扫描最近对话，提取候选事实
    2. 检查冲突、去重
    3. 满足门控条件的提升到长期记忆
    """
    if not state.get("pending_consolidation"):
        return {}

    store = config["configurable"]["store"]
    user_id = state["session_meta"].get("user_id", "default")
    memory = MemoryStoreManager(store, user_id)

    # 获取最近 7 天的所有消息文本
    recent_text = ""
    for m in state["messages"][-20:]:
        recent_text += f"{'USER' if isinstance(m, HumanMessage) else 'AGENT'}: {m.content[:200]}\n"

    if recent_text:
        # 提取候选事实
        facts = _extract_facts_heuristic(recent_text)
        for fact in facts:
            # 门控：评分阈值
            if fact.get("score", 5) >= 5.0:
                memory.remember(
                    content=fact["content"],
                    category=fact.get("category", "knowledge"),
                    score=fact.get("score", 5.0),
                    confidence=fact.get("confidence", 0.5),
                )

    return {"pending_consolidation": False}


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def _extract_facts_heuristic(text: str) -> list[dict]:
    """规则启发式提取事实（生产环境替换为 LLM 提取）"""
    facts = []
    patterns = [
        (["偏好", "喜欢", "习惯", "常用", "倾向于"], "preference", 6.0),
        (["决定", "选择", "采用", "选择", "选了"], "decision", 7.0),
        (["是", "使用", "基于", "运行在"], "knowledge", 5.0),
    ]

    for line in text.split("\n"):
        line = line.strip()
        if len(line) < 10:
            continue
        for keywords, category, base_score in patterns:
            if any(kw in line.lower() for kw in keywords):
                facts.append({
                    "fact_id": hashlib.md5(line.encode()).hexdigest()[:16],
                    "content": line,
                    "category": category,
                    "score": base_score,
                    "confidence": 0.5,
                })
                break

    return facts


# ═══════════════════════════════════════════════════════════
# 构建记忆增强的 Agent 图
# ═══════════════════════════════════════════════════════════

def build_memory_augmented_graph(
    agent_node_func,
    store: InMemoryStore = None,
    checkpointer: MemorySaver = None,
):
    """
    构建带三层记忆的 Agent 图。

    参数:
        agent_node_func: 实际的 Agent 节点函数（LLM + 工具调用）
        store: LangGraph Store 实例（长期记忆后端）
        checkpointer: LangGraph Checkpointer 实例（短期记忆持久化）

    返回:
        编译后的 CompiledGraph，可直接 invoke/ainvoke
    """
    store = store or InMemoryStore()
    checkpointer = checkpointer or MemorySaver()

    builder = StateGraph(MemoryAgentState)

    # 添加记忆节点
    builder.add_node("load_memory", load_memory_node)
    builder.add_node("agent", agent_node_func)
    builder.add_node("save_memory", save_to_memory_node)
    builder.add_node("update_profile", update_profile_node)
    builder.add_node("consolidate", consolidate_memory_node)

    # 连接边
    builder.set_entry_point("load_memory")
    builder.add_edge("load_memory", "agent")
    builder.add_edge("agent", "save_memory")

    # 保存记忆后 → 检查是否需要更新画像
    builder.add_conditional_edges(
        "save_memory",
        lambda s: "update_profile" if s.get("profile_delta") else "consolidate",
        {
            "update_profile": "update_profile",
            "consolidate": "consolidate",
        },
    )
    builder.add_edge("update_profile", "consolidate")
    builder.add_edge("consolidate", END)

    return builder.compile(
        checkpointer=checkpointer,
        store=store,
    )
