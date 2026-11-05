"""
Step 1: 3 个节点 — 意图理解 → 上下文补齐 → 产物生成
"""

from __future__ import annotations
import os
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage
from state import AgentState  # noqa: E402

_llm: Any = None


def set_llm(llm: Any) -> None:
    global _llm
    _llm = llm


def _call_llm(prompt: str) -> str:
    if _llm is None:
        raise RuntimeError("LLM 未初始化")
    return _llm.invoke(prompt).content


# ══════════════════════════════════════════════
#  Node 1: 意图理解
# ══════════════════════════════════════════════

def understand_intent(state: AgentState) -> dict:
    prompt = f"""分析以下用户输入，提炼为结构化意图。

用户输入：{state['user_input']}
工作目录：{state['workspace_path']}

请说明：
1. 核心目标
2. 需要什么资源
3. 期望输出"""

    intent = _call_llm(prompt)
    print(f"\n📋 [Node 1] 意图理解\n{intent}")

    return {
        "intent": intent,
        "messages": [HumanMessage(content=state["user_input"])],
    }


# ══════════════════════════════════════════════
#  Node 2: 上下文补齐
# ══════════════════════════════════════════════

def enrich_context(state: AgentState) -> dict:
    ws = state["workspace_path"]
    files = []
    if os.path.exists(ws):
        for f in sorted(os.listdir(ws)):
            full = os.path.join(ws, f)
            if os.path.isfile(full) and not f.startswith("."):
                files.append(f)

    context = f"工作目录文件: {files if files else '(空)'}\n路径: {ws}"
    print(f"\n🔍 [Node 2] 上下文补齐\n{context}")

    return {"enriched_context": context}


# ══════════════════════════════════════════════
#  Node 3: 产物生成
# ══════════════════════════════════════════════

def generate_output(state: AgentState) -> dict:
    prompt = f"""根据意图和上下文，生成最终回复。

意图：{state['intent']}
上下文：{state['enriched_context']}

用 Markdown 格式输出。"""

    output = _call_llm(prompt)

    filepath = os.path.join(state["workspace_path"], "output.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"\n📦 [Node 3] 产物生成 → output.md ({len(output)} 字符)")

    return {
        "final_output": output,
        "messages": [AIMessage(content=output)],
    }
