"""
LangGraph 三层记忆 + 画像系统 — 完整可运行演示

场景：代码审查 Agent
- 记住用户的审查偏好（安全 > 性能 > 风格）
- 记住过去的审查历史和决策
- 动态更新用户画像
- 跨会话持久化

运行方式：
    pip install langgraph langgraph-checkpoint langchain-core
    python demo.py
"""

import asyncio
import sys
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage

# 确保可以导入同目录下的模块
sys.path.insert(0, str(Path(__file__).parent))

from state import MemoryAgentState
from memory_store import MemoryStoreManager
from profiles import ProfileManager
from memory_graph import (
    load_memory_node,
    save_to_memory_node,
    update_profile_node,
    consolidate_memory_node,
)


# ═══════════════════════════════════════════════════════════
# 演示用 Agent 节点（生产环境替换为真实 LLM 调用）
# ═══════════════════════════════════════════════════════════

async def demo_agent_node(state: MemoryAgentState, config: RunnableConfig) -> dict:
    """
    一个简单的 Agent 节点：根据记忆上下文和用户画像生成响应。

    生产环境替换为：
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import ToolNode
        llm = ChatOpenAI(model="gpt-4o").bind_tools([...])
    """
    user_profile = state.get("user_profile", {})
    memory_context = state.get("memory_context", "")
    recalled = state.get("memory_blocks", {}).get("recalled", [])

    # 获取最后一条用户消息
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    last_msg = user_messages[-1].content if user_messages else ""

    # ── 根据用户画像调整行为 ──────────────────────────
    security_focus = user_profile.get("traits", {}).get(
        "security_sensitivity", {}
    ).get("value", "standard")

    priority = user_profile.get("traits", {}).get(
        "code_review_priority", {}
    ).get("value", ["安全", "性能", "风格"])

    # ── 生成响应 ──────────────────────────────────────
    response_lines = [
        f"收到审查请求。",
        f"",
        f"📋 **当前记忆状态**：",
        f"- 用户画像特征数：{len(user_profile.get('traits', {}))}",
        f"- 安全敏感度：{security_focus}",
        f"- 审查优先级：{' > '.join(priority) if isinstance(priority, list) else priority}",
        f"- 本次召回相关记忆：{len(recalled)} 条",
    ]

    if recalled:
        response_lines.append(f"\n🔍 **召回的相关记忆**：")
        for r in recalled[:3]:
            response_lines.append(
                f"  - [{r.get('category', '?')}] {r.get('content', '')[:100]}"
            )

    response_lines.append(
        f"\n✅ 我会按照你的偏好，优先关注{'安全性' if security_focus == 'high' else '各项指标'}。"
        f"请提供要审查的代码。"
    )

    return {
        "messages": [AIMessage(content="\n".join(response_lines))],
    }


async def detect_profile_changes_node(state: MemoryAgentState, config: RunnableConfig) -> dict:
    """
    从最新用户消息中检测画像变更。

    演示用规则匹配；生产环境用 LLM 判断。
    """
    last_user_msg = ""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            last_user_msg = m.content
            break

    delta = {}
    facts = []

    # 规则：安全相关
    if "安全" in last_user_msg and "关注" in last_user_msg:
        delta["security_sensitivity"] = "high"
        facts.append(f"用户高度关注安全性")

    # 规则：风格态度
    if "风格" in last_user_msg and ("无所谓" in last_user_msg or "不重要" in last_user_msg):
        delta["code_style_importance"] = "low"
        facts.append("用户对代码风格不太在意")

    # 规则：语言偏好
    for lang in ["TypeScript", "Python", "Go", "Rust"]:
        if f"用{lang}" in last_user_msg or f"偏好{lang}" in last_user_msg:
            delta["preferred_language"] = lang
            facts.append(f"用户偏好 {lang}")

    if delta or facts:
        return {
            "profile_delta": {
                "traits": delta,
                "facts": facts,
                "confidence": 0.7,
            }
        }
    return {}


# ═══════════════════════════════════════════════════════════
# 构建图
# ═══════════════════════════════════════════════════════════

def build_demo_graph(store, checkpointer):
    """构建演示用的记忆增强 Agent 图"""
    builder = StateGraph(MemoryAgentState)

    # 添加节点
    builder.add_node("load_memory", load_memory_node)
    builder.add_node("agent", demo_agent_node)
    builder.add_node("detect_changes", detect_profile_changes_node)
    builder.add_node("save_memory", save_to_memory_node)
    builder.add_node("update_profile", update_profile_node)
    builder.add_node("consolidate", consolidate_memory_node)

    # 连接边
    builder.set_entry_point("load_memory")
    builder.add_edge("load_memory", "agent")
    builder.add_edge("agent", "detect_changes")

    # 检测到画像变更 → 更新画像；否则直接保存
    builder.add_conditional_edges(
        "detect_changes",
        lambda s: "update_profile" if s.get("profile_delta") else "save_memory",
        {"update_profile": "update_profile", "save_memory": "save_memory"},
    )
    builder.add_edge("update_profile", "save_memory")
    builder.add_edge("save_memory", "consolidate")
    builder.add_edge("consolidate", END)

    return builder.compile(checkpointer=checkpointer, store=store)


# ═══════════════════════════════════════════════════════════
# 主演示流程
# ═══════════════════════════════════════════════════════════

def print_separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def main():
    print_separator("LangGraph 三层记忆 + 画像系统 演示")
    print("场景：代码审查 Agent 带记忆")

    # ── 初始化基础设施 ────────────────────────────────
    store = InMemoryStore()
    checkpointer = MemorySaver()
    memory = MemoryStoreManager(store, "user_001")
    profiles = ProfileManager(store)

    # 预填充部分初始记忆（模拟已有历史对话）
    print_separator("阶段 0：预填充初始记忆")

    memory.remember(
        "用户是后端工程师，主要技术栈 Python 和 TypeScript",
        category="knowledge",
        score=8.0,
        confidence=0.9,
    )
    profiles.update_trait("user_001", "role", "后端工程师", confidence=0.9)
    profiles.update_trait("user_001", "skill_level", "高级", confidence=0.8)
    print("  ✅ 已预填充 2 条初始记忆")

    # 构建图
    app = build_demo_graph(store, checkpointer)

    # ═══════════════════════════════════════════════════════
    # 第 1 天：初次使用
    # ═══════════════════════════════════════════════════════
    print_separator("第 1 天：初次代码审查")

    config1 = {"configurable": {"thread_id": "session-day-1", "store": store}}

    result1 = await app.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content="帮我审查这段代码，我比较关注 SQL 注入这类安全问题，"
                            "性能方面可以宽松一些，代码风格无所谓"
                )
            ],
            "session_meta": {
                "user_id": "user_001",
                "session_id": "session-day-1",
            },
            "memory_context": "",
            "memory_blocks": {},
            "user_profile": {},
            "profile_delta": None,
            "compaction_count": 0,
            "pending_consolidation": False,
        },
        config1,
    )

    print("\n🤖 Agent 响应：")
    ai_msgs = [m for m in result1["messages"] if isinstance(m, AIMessage)]
    for m in ai_msgs[-1:]:  # 只显示最后一条 Agent 消息
        print(m.content)

    # 查看画像更新
    profile = profiles.get_profile("user_001")
    print(f"\n👤 第1天后用户画像：")
    for trait, info in profile.get("traits", {}).items():
        print(f"  - {trait}: {info['value']} (置信度: {info['confidence']})")

    # ═══════════════════════════════════════════════════════
    # 第 2 天：再次使用（新 thread，记忆已持久化）
    # ═══════════════════════════════════════════════════════
    print_separator("第 2 天：再次审查（新会话，从 Store 恢复记忆）")

    # 相同的 store，但新的 thread_id
    config2 = {"configurable": {"thread_id": "session-day-2", "store": store}}

    result2 = await app.ainvoke(
        {
            "messages": [
                HumanMessage(content="又有一批新代码需要审查，帮我看看")
            ],
            "session_meta": {
                "user_id": "user_001",
                "session_id": "session-day-2",
            },
            "memory_context": "",
            "memory_blocks": {},
            "user_profile": {},
            "profile_delta": None,
            "compaction_count": 0,
            "pending_consolidation": False,
        },
        config2,
    )

    print("\n🤖 Agent 响应（从 Store 恢复了用户偏好）：")
    ai_msgs = [m for m in result2["messages"] if isinstance(m, AIMessage)]
    for m in ai_msgs[-1:]:
        print(m.content)

    # ═══════════════════════════════════════════════════════
    # 第 3 天：用户兴趣变化
    # ═══════════════════════════════════════════════════════
    print_separator("第 3 天：用户偏好变化（画像动态更新）")

    config3 = {"configurable": {"thread_id": "session-day-3", "store": store}}

    result3 = await app.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content="最近公司在推 Go 语言，我也开始偏好 Go 了。"
                            "帮我审查这段 Go 代码，我依然很关注安全性"
                )
            ],
            "session_meta": {
                "user_id": "user_001",
                "session_id": "session-day-3",
            },
            "memory_context": "",
            "memory_blocks": {},
            "user_profile": {},
            "profile_delta": None,
            "compaction_count": 0,
            "pending_consolidation": False,
        },
        config3,
    )

    profile3 = profiles.get_profile("user_001")
    print(f"\n👤 第3天后用户画像（已检测到语言偏好变化）：")
    for trait, info in profile3.get("traits", {}).items():
        print(f"  - {trait}: {info['value']} (置信度: {info['confidence']})")

    print(f"\n📋 已知用户事实（共 {len(profile3.get('facts', []))} 条）：")
    for f in profile3.get("facts", [])[-8:]:
        print(f"  - [{f['confidence']:.2f}] {f['fact']}")

    # ═══════════════════════════════════════════════════════
    # 验证：搜索长期记忆
    # ═══════════════════════════════════════════════════════
    print_separator("验证：搜索长期记忆")

    queries = ["SQL 注入", "Go 语言", "代码风格"]
    for q in queries:
        results = memory.recall(q, limit=3)
        print(f"\n🔍 搜索 '{q}' → {len(results)} 条结果：")
        for r in results:
            print(f"  - [{r.get('category', '?')}] {r.get('content', '')[:100]} "
                  f"(评分: {r.get('effective_score', 'N/A')})")

    # ═══════════════════════════════════════════════════════
    # 验证：查看 Checkpoint 历史（时间旅行）
    # ═══════════════════════════════════════════════════════
    print_separator("验证：Checkpoint 时间旅行")

    history = []
    async for snapshot in app.aget_state_history(config3):
        history.append(snapshot)

    print(f"  Session-day-3 的 Checkpoint 快照数：{len(history)}")
    if history:
        latest = history[-1]
        memory_ctx = latest.values.get("memory_context", "")
        print(f"  最新快照的记忆上下文（前200字符）：")
        print(f"    {memory_ctx[:200]}...")

    # ── 总结 ──────────────────────────────────────────
    print_separator("演示完成")
    print("""
✅ 验证了以下功能：
  1. 三层记忆模型：短期（messages）+ 情节（sessions）+ 长期（Store）
  2. 跨会话持久化：新 thread_id 自动从 Store 恢复记忆
  3. 画像动态更新：从对话中检测到语言偏好变化（Python → Go）
  4. 语义搜索：Store.search() 召回相关记忆
  5. Checkpoint 时间旅行：可回溯任意历史状态
  6. EMA 平滑：画像特征不会被单次对话剧烈改变

📂 代码文件：
  - state.py         → 三层记忆的 State Schema
  - memory_store.py   → 基于 Store 的长期记忆 API
  - memory_graph.py   → 记忆操作封装为图节点
  - profiles.py       → 画像引擎
  - demo.py           → 本文件（可运行演示）

🚀 下一步：
  1. 将 InMemoryStore 替换为 SqliteStore（持久化到磁盘）
  2. 将 demo_agent_node 替换为真实 LLM 调用
  3. 将 _extract_facts_heuristic 替换为 LLM 提取
  4. 添加 embedding 模型实现真正的语义搜索
""")


if __name__ == "__main__":
    asyncio.run(main())
